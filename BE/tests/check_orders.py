"""Chạy từ gốc repo: BE/.venv/bin/python BE/tests/check_orders.py.
Tạo DB MySQL tạm, chạy API thật qua Gateway, không ghi vào DB ứng dụng.
Thêm --postman để chạy collection với hai server HTTP tạm.
"""

import asyncio
import os
import sys
import uuid
from pathlib import Path

import httpx
from dotenv import dotenv_values
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from support import BackendTransport, run_postman, statements

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "BE"), str(ROOT / "Gateway")]


async def main():
    url = make_url(dotenv_values(ROOT / "BE/.env")["DATABASE_URL"])
    name = "cms_order_test_" + uuid.uuid4().hex
    admin = create_async_engine(url)
    db = create_async_engine(url.set(database=name))
    backend_engine = None
    created = False
    count = 0
    try:
        async with admin.begin() as conn:
            await conn.exec_driver_sql(
                f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            created = True
        os.environ.update(
            DATABASE_URL=url.set(database=name).render_as_string(hide_password=False),
            DEBUG="false",
            JWT_SECRET_KEY="customer-test-jwt-" * 4,
            GATEWAY_SHARED_SECRET="customer-test-gateway-" * 4,
        )
        async with db.begin() as conn:
            await conn.exec_driver_sql("SET sql_notes=0")
            for stmt in statements(ROOT / "sql/cms_logistics_schema.sql"):
                await conn.exec_driver_sql(stmt)
            for _ in range(2):
                for file in (
                    "cms_logistics_procedures.sql",
                    "cms_logistics_customers.sql",
                    "cms_logistics_orders.sql",
                ):
                    for stmt in statements(ROOT / "sql" / file):
                        await conn.exec_driver_sql(stmt)
            assert len((await conn.exec_driver_sql("SHOW TABLES")).all()) == 10
            from app.infrastructure.security.password import Argon2PasswordHasher

            hashed = await Argon2PasswordHasher().hash("Strong@123456")
            ids = {}
            for username, role in [
                ("admin", "ADMIN"),
                ("sale_a", "SALE"),
                ("sale_b", "SALE"),
                ("customer_a", "CUSTOMER"),
                ("customer_b", "CUSTOMER"),
                ("warehouse", "WAREHOUSE"),
            ]:
                result = await conn.execute(
                    text(
                        "INSERT INTO nguoi_dung(ten_dang_nhap,ho_ten,mat_khau_bam,vai_tro) VALUES(:name,:name,:hash,:role)"
                    ),
                    {"name": username, "hash": hashed, "role": role},
                )
                ids[username] = result.lastrowid
        from app.infrastructure.db.session import engine as backend_engine
        from app.main import app as backend
        from gateway_app.app import create_app
        from gateway_app.config import Settings

        gateway = create_app(Settings(_env_file=None), BackendTransport(backend))
        async with (
            gateway.router.lifespan_context(gateway),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=gateway), base_url="http://gateway"
            ) as client,
        ):

            async def check(method, path, expected, who=None, **kwargs):
                nonlocal count
                if who:
                    kwargs["headers"] = tokens[who]
                response = await client.request(method, path, **kwargs)
                assert response.status_code == expected, (
                    method,
                    path,
                    response.status_code,
                    response.text,
                )
                count += 1
                return response

            tokens = {}
            for username in ids:
                r = await check(
                    "POST",
                    "/auth/login",
                    200,
                    json={"username": username, "password": "Strong@123456"},
                )
                tokens[username] = {"Authorization": "Bearer " + r.json()["access_token"]}
            await check("GET", "/health", 200)
            await check("GET", "/customers", 401)
            # Create two linked customer profiles through the real API.
            customer_body = {"name": "Khách A", "phone": "0912345678", "address": "Hà Nội"}
            r = await check(
                "POST",
                "/customers",
                201,
                "admin",
                json={**customer_body, "user_id": ids["customer_a"], "sale_id": ids["sale_a"]},
            )
            customer_a = r.json()["id"]
            r = await check(
                "POST",
                "/customers",
                201,
                "admin",
                json={
                    **customer_body,
                    "name": "Khách B",
                    "user_id": ids["customer_b"],
                    "sale_id": ids["sale_b"],
                },
            )
            customer_b = r.json()["id"]
            body = {
                "customer_id": customer_a,
                "recipient_name": "Nguyễn Văn A",
                "recipient_phone": "0912345678",
                "recipient_address": "Đà Nẵng",
                "shipping_fee": "12345.67",
                "note": "Giao giờ hành chính",
                "items": [
                    {"name": "Áo thun", "quantity": 20, "note": "Dễ ướt"},
                    {"name": "Giày", "quantity": 5},
                ],
            }
            await check("GET", "/orders", 401)
            r = await check("POST", "/orders", 201, "sale_a", json=body)
            first = r.json()["id"]
            assert r.json()["status"] == "PENDING" and r.json()["shipping_fee"] == "12345.67"
            assert len(r.json()["items"]) == 2 and r.json()["created_by"] == ids["sale_a"]
            assert r.json()["items"][1]["note"] is None
            r = await check(
                "POST",
                "/orders",
                201,
                "admin",
                json={**body, "customer_id": customer_b, "order_code": "test_b"},
            )
            second = r.json()["id"]
            assert r.json()["order_code"] == "TEST_B"
            for who in ("admin", "sale_a", "customer_a"):
                await check("GET", f"/orders/{first}", 200, who)
            for who in ("sale_b", "customer_b"):
                await check("GET", f"/orders/{first}", 404, who)
            for who, expected in [
                ("admin", {first, second}),
                ("sale_a", {first}),
                ("sale_b", {second}),
                ("customer_a", {first}),
                ("customer_b", {second}),
            ]:
                r = await check("GET", "/orders", 200, who)
                assert {i["id"] for i in r.json()["items"]} == expected
            for who in ("customer_a", "warehouse"):
                for method, path, kwargs in [
                    ("POST", "/orders", {"json": body}),
                    ("PATCH", f"/orders/{first}", {"json": {"note": "Denied"}}),
                    ("PATCH", f"/orders/{first}/status", {"json": {"status": "CONFIRMED"}}),
                ]:
                    await check(method, path, 403, who, **kwargs)
            await check("GET", "/orders", 200, "warehouse")
            await check("GET", f"/orders/{first}", 200, "warehouse")
            await check("POST", "/orders", 404, "sale_b", json=body)
            await check("PATCH", f"/orders/{first}", 404, "sale_b", json={"note": "Denied"})
            await check(
                "PATCH", f"/orders/{first}/status", 404, "sale_b", json={"status": "CONFIRMED"}
            )
            await check("POST", "/orders", 404, "admin", json={**body, "customer_id": 999999})
            await check("POST", "/orders", 409, "admin", json={**body, "order_code": "TEST_B"})
            for patch in [
                {},
                {"recipient_name": None},
                {"recipient_address": "  "},
                {"recipient_phone": "abc"},
                {"shipping_fee": None},
                {"shipping_fee": "-1"},
                {"shipping_fee": "1.001"},
                {"items": None},
                {"items": []},
                {"status": "CONFIRMED"},
                {"customer_id": customer_b},
                {"created_by": ids["admin"]},
                {"note": "x" * 2001},
            ]:
                await check("PATCH", f"/orders/{first}", 422, "admin", json=patch)
            invalid_items = [
                [],
                [{"name": "", "quantity": 1}],
                [{"name": "A", "quantity": 0}],
                [{"name": "A", "quantity": -1}],
                [{"name": "A", "quantity": True}],
                [{"name": "A", "quantity": "2"}],
                [{"name": "A", "quantity": 1.5}],
                [{"name": "A", "quantity": 2147483648}],
                [{"name": "A", "quantity": 1, "extra": "x"}],
                [{"name": "x" * 256, "quantity": 1}],
                [{"name": "A", "quantity": 1}] * 101,
            ]
            for items in invalid_items:
                await check("POST", "/orders", 422, "admin", json={**body, "items": items})
            for field, value in [
                ("shipping_fee", "NaN"),
                ("shipping_fee", "-1"),
                ("shipping_fee", "1.001"),
                ("shipping_fee", "10000000000000000"),
                ("customer_id", 0),
                ("recipient_name", "  "),
                ("recipient_phone", "bad"),
                ("recipient_address", ""),
                ("order_code", "bad code"),
                ("unknown", "x"),
            ]:
                await check("POST", "/orders", 422, "admin", json={**body, field: value})
            r = await check(
                "PATCH",
                f"/orders/{first}",
                200,
                "sale_a",
                json={
                    "recipient_address": "TP HCM",
                    "note": "null",
                    "items": [{"name": "Hàng mới", "quantity": 3}],
                },
            )
            assert r.json()["note"] == "null" and r.json()["recipient_address"] == "TP HCM"
            assert len(r.json()["items"]) == 1 and r.json()["items"][0]["quantity"] == 3
            assert r.json()["shipping_fee"] == "12345.67"
            r = await check(
                "PATCH",
                f"/orders/{first}",
                200,
                "admin",
                json={"note": None, "shipping_fee": "0"},
            )
            assert r.json()["note"] is None and r.json()["shipping_fee"] == "0.00"
            # SQL error AFTER inserting an order/item must roll back the entire transaction.
            from sqlalchemy.exc import DBAPIError

            bad_items = '[{"name":"First","quantity":1},{"name":"Broken","quantity":0}]'
            async with db.connect() as conn:
                before = (await conn.exec_driver_sql("SELECT COUNT(*) FROM don_hang")).scalar_one()
                try:
                    await conn.execute(
                        text(
                            "CALL sp_create_order(:actor,:code,:customer,:name,:phone,:address,:fee,:note,:items)"
                        ),
                        {
                            "actor": ids["admin"],
                            "code": "ROLLBACK_CREATE",
                            "customer": customer_a,
                            "name": "A",
                            "phone": "0912345678",
                            "address": "VN",
                            "fee": 0,
                            "note": None,
                            "items": bad_items,
                        },
                    )
                    raise AssertionError("Invalid items accepted by SQL")
                except DBAPIError as exc:
                    assert exc.orig.args[0] == 1644 and exc.orig.args[1] == "INVALID_ITEMS"
                    await conn.rollback()
                assert (
                    await conn.exec_driver_sql("SELECT COUNT(*) FROM don_hang")
                ).scalar_one() == before
                await conn.rollback()
                try:
                    await conn.execute(
                        text("CALL sp_update_order(:actor,:id,:patch)"),
                        {
                            "actor": ids["admin"],
                            "id": first,
                            "patch": '{"items":' + bad_items + "}",
                        },
                    )
                    raise AssertionError("Invalid replacement accepted by SQL")
                except DBAPIError as exc:
                    assert exc.orig.args[0] == 1644
                    await conn.rollback()
            r = await check("GET", f"/orders/{first}", 200, "admin")
            assert r.json()["items"][0]["name"] == "Hàng mới" and len(r.json()["items"]) == 1
            # Filtering must never expand the caller's scope.
            r = await check("GET", f"/orders?customer_id={customer_b}", 200, "customer_a")
            assert r.json()["items"] == []
            r = await check(
                "GET", "/orders?search=TEST_B&status=PENDING&limit=1&offset=0", 200, "admin"
            )
            assert [i["id"] for i in r.json()["items"]] == [second]
            r = await check("GET", "/orders?limit=1&offset=1", 200, "admin")
            assert len(r.json()["items"]) == 1
            for path in [
                "/orders/0",
                "/orders?limit=0",
                "/orders?offset=-1",
                "/orders?status=BAD",
                "/orders?customer_id=0",
            ]:
                await check("GET", path, 422, "admin")
            await check("GET", "/orders/999999", 404, "admin")
            await check("PATCH", "/orders/999999", 404, "admin", json={"note": "x"})
            await check(
                "PATCH", "/orders/999999/status", 404, "admin", json={"status": "CONFIRMED"}
            )
            await check("PATCH", f"/orders/{first}/status", 422, "admin", json={"status": "BAD"})
            await check(
                "PATCH",
                f"/orders/{first}/status",
                422,
                "admin",
                json={"status": "CONFIRMED", "extra": 1},
            )
            await check(
                "PATCH", f"/orders/{first}/status", 409, "admin", json={"status": "SHIPPING"}
            )
            await check(
                "PATCH", f"/orders/{first}/status", 200, "sale_a", json={"status": "CONFIRMED"}
            )
            await check(
                "PATCH", f"/orders/{first}/status", 200, "admin", json={"status": "CONFIRMED"}
            )
            await check("PATCH", f"/orders/{first}", 409, "admin", json={"note": "Frozen"})
            await check(
                "PATCH", f"/orders/{first}/status", 409, "admin", json={"status": "PENDING"}
            )
            await check(
                "PATCH", f"/orders/{first}/status", 409, "admin", json={"status": "DELIVERED"}
            )
            await check(
                "PATCH", f"/orders/{first}/status", 200, "admin", json={"status": "SHIPPING"}
            )
            await check(
                "PATCH", f"/orders/{first}/status", 409, "admin", json={"status": "CANCELLED"}
            )
            await check(
                "PATCH", f"/orders/{first}/status", 200, "admin", json={"status": "DELIVERED"}
            )
            for status in ("PENDING", "CONFIRMED", "SHIPPING", "CANCELLED"):
                await check(
                    "PATCH", f"/orders/{first}/status", 409, "admin", json={"status": status}
                )
            await check(
                "PATCH", f"/orders/{second}/status", 200, "admin", json={"status": "CANCELLED"}
            )
            await check(
                "PATCH", f"/orders/{second}/status", 409, "admin", json={"status": "CONFIRMED"}
            )
            await check("PATCH", f"/orders/{second}", 409, "admin", json={"note": "Frozen"})
            # Reassignment changes permissions immediately, regardless of order creator.
            await check(
                "PATCH",
                f"/customers/{customer_a}",
                200,
                "admin",
                json={"sale_id": ids["sale_b"]},
            )
            await check("GET", f"/orders/{first}", 404, "sale_a")
            await check("GET", f"/orders/{first}", 200, "sale_b")
            await check("POST", "/orders", 404, "sale_a", json=body)
            await check(
                "PATCH",
                f"/customers/{customer_a}",
                200,
                "admin",
                json={"sale_id": ids["sale_a"]},
            )
            # Inactive customers cannot receive new orders, historical orders remain readable.
            await check("DELETE", f"/customers/{customer_b}", 204, "admin")
            await check("POST", "/orders", 409, "admin", json={**body, "customer_id": customer_b})
            await check("GET", f"/orders/{second}", 200, "customer_b")
            # Concurrent branches: CONFIRMED -> SHIPPING or CANCELLED, never both.
            r = await check("POST", "/orders", 201, "admin", json=body)
            race_id = r.json()["id"]
            await check(
                "PATCH", f"/orders/{race_id}/status", 200, "admin", json={"status": "CONFIRMED"}
            )
            responses = await asyncio.gather(
                client.patch(
                    f"/orders/{race_id}/status",
                    headers=tokens["admin"],
                    json={"status": "SHIPPING"},
                ),
                client.patch(
                    f"/orders/{race_id}/status",
                    headers=tokens["sale_a"],
                    json={"status": "CANCELLED"},
                ),
            )
            assert sorted(r.status_code for r in responses) == [200, 409], [
                (r.status_code, r.text) for r in responses
            ]
            count += 2
            # Concurrent identical order codes: exactly one order and its items are committed.
            requests = [
                client.post(
                    "/orders", headers=tokens[who], json={**body, "order_code": "RACE_CODE"}
                )
                for who in ("admin", "sale_a")
            ]
            responses = await asyncio.gather(*requests)
            assert sorted(r.status_code for r in responses) == [201, 409]
            count += 2
            async with db.connect() as conn:
                assert (
                    await conn.scalar(
                        text("SELECT COUNT(*) FROM don_hang WHERE ma_don='RACE_CODE'")
                    )
                    == 1
                )
                assert (
                    await conn.scalar(
                        text(
                            "SELECT COUNT(*) FROM chi_tiet_don_hang d JOIN don_hang o ON o.ma=d.ma_don_hang WHERE o.ma_don='RACE_CODE'"
                        )
                    )
                    == 2
                )
            # Prevent edits and cancellation when existing package/payment records make them unsafe.
            for dependency in ("package", "payment"):
                r = await check("POST", "/orders", 201, "admin", json=body)
                oid = r.json()["id"]
                async with db.begin() as conn:
                    if dependency == "package":
                        await conn.execute(
                            text(
                                "INSERT INTO kien_hang(ma_don_hang,ma_van_don,khoi_luong_kg,chieu_dai_cm,chieu_rong_cm,chieu_cao_cm) VALUES(:id,:code,1,1,1,1)"
                            ),
                            {"id": oid, "code": f"PACK-{oid}"},
                        )
                    else:
                        await conn.execute(
                            text(
                                "INSERT INTO thanh_toan(ma_don_hang,so_tien,loai_giao_dich,phuong_thuc,ma_tham_chieu,nguoi_tao) VALUES(:id,1,'PAYMENT','CASH',:code,:actor)"
                            ),
                            {"id": oid, "code": f"PAY-{oid}", "actor": ids["admin"]},
                        )
                await check("PATCH", f"/orders/{oid}", 409, "admin", json={"note": "Blocked"})
                await check(
                    "PATCH", f"/orders/{oid}/status", 409, "admin", json={"status": "CANCELLED"}
                )
            # SQL layer also rejects CUSTOMER writes.
            async with db.connect() as conn:
                try:
                    await conn.execute(
                        text("CALL sp_update_order_status(:actor,:id,'CONFIRMED')"),
                        {"actor": ids["customer_a"], "id": race_id},
                    )
                    raise AssertionError("CUSTOMER SQL write accepted")
                except DBAPIError as exc:
                    assert exc.orig.args[0] == 1644 and exc.orig.args[1] == "FORBIDDEN"
                    await conn.rollback()
            async with db.begin() as conn:
                await conn.execute(
                    text("UPDATE nguoi_dung SET vai_tro='CUSTOMER' WHERE ma=:id"),
                    {"id": ids["sale_a"]},
                )
            await check("POST", "/orders", 403, "sale_a", json=body)
            r = await check("GET", "/auth/permissions", 200, "customer_a")
            assert "orders:read:own" in r.json()["permissions"]
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=backend), base_url="http://backend"
            ) as direct:
                assert (await direct.get("/orders", headers=tokens["admin"])).status_code == 403
            print(
                f"PASS: {count} HTTP checks; real MySQL, order/items atomicity, RBAC, transitions, concurrent writes; 10 tables."
            )
        if "--postman" in sys.argv:
            await run_postman("Logistics-Orders.postman_collection.json")
    finally:
        if backend_engine is not None:
            await backend_engine.dispose()
        await db.dispose()
        if created:
            assert name.startswith("cms_order_test_") and len(name) == len("cms_order_test_") + 32
            async with admin.begin() as conn:
                await conn.exec_driver_sql(f"DROP DATABASE `{name}`")
        await admin.dispose()


if __name__ == "__main__":
    asyncio.run(main())
