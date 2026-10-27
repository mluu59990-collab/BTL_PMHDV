"""Chạy từ gốc repo: BE/.venv/bin/python BE/tests/check_payments.py.
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
    name = "cms_payment_test_" + uuid.uuid4().hex
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
                    "cms_logistics_fulfillment.sql",
                    "cms_logistics_payments.sql",
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
                ("accountant", "ACCOUNTANT"),
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
            customer_body = {"name": "Khách A", "phone": "0912345678", "address": "Hà Nội"}
            r = await check(
                "POST",
                "/customers",
                201,
                "admin",
                json={**customer_body, "user_id": ids["customer_a"], "sale_id": ids["sale_a"]},
            )
            ca = r.json()["id"]
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
            cb = r.json()["id"]
            order_body = {
                "customer_id": ca,
                "recipient_name": "Người nhận",
                "recipient_phone": "0912345678",
                "recipient_address": "Hà Nội",
                "shipping_fee": "100.50",
                "items": [{"name": "Hàng gửi", "quantity": 1}],
            }

            async def new_order(customer=ca, fee="100.50", confirm=True):
                r = await check(
                    "POST",
                    "/orders",
                    201,
                    "admin",
                    json={**order_body, "customer_id": customer, "shipping_fee": fee},
                )
                oid = r.json()["id"]
                if confirm:
                    await check(
                        "PATCH",
                        f"/orders/{oid}/status",
                        200,
                        "admin",
                        json={"status": "CONFIRMED"},
                    )
                return oid

            oa = await new_order(confirm=False)
            ob = await new_order(customer=cb)
            body = {
                "order_id": oa,
                "amount": "40.25",
                "method": "CASH",
                "reference_code": "pay_a_001",
            }
            await check("GET", "/payments", 401)
            await check("POST", "/payments", 401, json=body)
            await check("POST", "/payments", 409, "accountant", json=body)
            await check(
                "POST",
                "/payments/refunds",
                409,
                "accountant",
                json={**body, "reference_code": "REFUND_EMPTY"},
            )
            r = await check("GET", f"/orders/{oa}/payment-summary", 200, "accountant")
            assert r.json()["payment_status"] == "UNPAID" and r.json()["amount_due"] == "100.50"
            await check("GET", f"/orders/{oa}", 200, "accountant")
            await check("PATCH", f"/orders/{oa}", 403, "accountant", json={"shipping_fee": "0"})
            await check("PATCH", f"/orders/{oa}/status", 200, "admin", json={"status": "CONFIRMED"})
            r = await check("POST", "/payments", 201, "accountant", json=body)
            first = r.json()["id"]
            assert r.json()["amount"] == "40.25" and r.json()["reference_code"] == "PAY_A_001"
            assert r.json()["created_by"] == ids["accountant"] and r.json()["replayed"] is False
            r = await check("POST", "/payments", 200, "admin", json=body)
            assert (
                r.json()["id"] == first
                and r.json()["replayed"] is True
                and r.json()["created_by"] == ids["accountant"]
            )
            for patch in [{"amount": "40.26"}, {"method": "BANK_TRANSFER"}, {"order_id": ob}]:
                await check("POST", "/payments", 409, "admin", json={**body, **patch})
            await check("POST", "/payments/refunds", 409, "admin", json=body)
            for who in ("admin", "accountant", "sale_a", "customer_a"):
                await check("GET", f"/payments/{first}", 200, who)
                r = await check("GET", f"/payments?order_id={oa}", 200, who)
                assert len(r.json()["items"]) == 1
                r = await check("GET", f"/orders/{oa}/payment-summary", 200, who)
                assert (
                    r.json()["net_paid"] == "40.25"
                    and r.json()["amount_due"] == "60.25"
                    and r.json()["payment_status"] == "PARTIAL"
                )
            for who in ("sale_b", "customer_b"):
                await check("GET", f"/payments/{first}", 404, who)
                await check("GET", f"/orders/{oa}/payment-summary", 404, who)
                r = await check("GET", f"/payments?order_id={oa}", 200, who)
                assert r.json()["items"] == []
            for who in ("sale_a", "customer_a", "warehouse"):
                await check("POST", "/payments", 403, who, json=body)
                await check("POST", "/payments/refunds", 403, who, json=body)
            for path in ["/payments", f"/payments/{first}", f"/orders/{oa}/payment-summary"]:
                await check("GET", path, 403, "warehouse")
            await check(
                "POST",
                "/payments",
                409,
                "accountant",
                json={**body, "amount": "60.26", "reference_code": "TOO_MUCH"},
            )
            r = await check(
                "POST",
                "/payments",
                201,
                "admin",
                json={
                    **body,
                    "amount": "60.25",
                    "method": "BANK_TRANSFER",
                    "reference_code": "PAY_A_002",
                },
            )
            second = r.json()["id"]
            r = await check("GET", f"/orders/{oa}/payment-summary", 200, "customer_a")
            assert (
                r.json()["total_paid"] == "100.50"
                and r.json()["amount_due"] == "0.00"
                and r.json()["payment_status"] == "PAID"
            )
            await check(
                "POST",
                "/payments",
                409,
                "admin",
                json={**body, "amount": "0.01", "reference_code": "OVER"},
            )
            await check("PATCH", f"/orders/{oa}/status", 409, "admin", json={"status": "CANCELLED"})
            refund = {
                "order_id": oa,
                "amount": "20.25",
                "method": "BANK_TRANSFER",
                "reference_code": "REF_A_001",
            }
            r = await check("POST", "/payments/refunds", 201, "accountant", json=refund)
            refund_id = r.json()["id"]
            assert r.json()["transaction_type"] == "REFUND"
            r = await check("POST", "/payments/refunds", 200, "admin", json=refund)
            assert r.json()["id"] == refund_id
            r = await check("GET", f"/orders/{oa}/payment-summary", 200, "admin")
            assert (
                r.json()["total_refunded"] == "20.25"
                and r.json()["net_paid"] == "80.25"
                and r.json()["amount_due"] == "20.25"
            )
            await check(
                "POST",
                "/payments/refunds",
                409,
                "admin",
                json={**refund, "amount": "80.26", "reference_code": "REF_TOO_MUCH"},
            )
            await check(
                "POST",
                "/payments/refunds",
                201,
                "admin",
                json={**refund, "amount": "80.25", "reference_code": "REF_A_002"},
            )
            r = await check("GET", f"/orders/{oa}/payment-summary", 200, "admin")
            assert (
                r.json()["net_paid"] == "0.00"
                and r.json()["payment_status"] == "REFUNDED"
                and r.json()["amount_due"] == "100.50"
            )
            # Full refund allows cancellation without deleting accounting history.
            await check("PATCH", f"/orders/{oa}/status", 200, "admin", json={"status": "CANCELLED"})
            r = await check("GET", f"/orders/{oa}/payment-summary", 200, "customer_a")
            assert r.json()["amount_due"] == "0.00" and r.json()["payment_status"] == "CANCELLED"
            await check(
                "POST",
                "/payments",
                409,
                "admin",
                json={**body, "reference_code": "NEW_ON_CANCELLED"},
            )
            await check("POST", "/payments", 200, "accountant", json=body)
            await check("POST", "/payments/refunds", 200, "accountant", json=refund)
            r = await check("GET", f"/payments?order_id={oa}", 200, "accountant")
            assert len(r.json()["items"]) == 4
            await check("PATCH", f"/payments/{first}", 405, "admin", json={"amount": "0"})
            await check("DELETE", f"/payments/{first}", 405, "admin")
            # Financial validation and unknown fields are rejected before SQL.
            for field, value in [
                ("amount", "0"),
                ("amount", "-1"),
                ("amount", "1.001"),
                ("amount", "NaN"),
                ("amount", True),
                ("amount", "10000000000000000"),
                ("method", "CARD"),
                ("order_id", 0),
                ("reference_code", " "),
                ("reference_code", "x" * 81),
                ("reference_code", "bad code"),
                ("transaction_type", "REFUND"),
                ("created_by", ids["admin"]),
            ]:
                await check("POST", "/payments", 422, "admin", json={**body, field: value})
            incomplete = {**body}
            incomplete.pop("reference_code")
            await check("POST", "/payments", 422, "admin", json=incomplete)
            await check(
                "POST",
                "/payments",
                404,
                "admin",
                json={**body, "order_id": 999999, "reference_code": "MISSING_ORDER"},
            )
            await check("GET", "/payments/999999", 404, "admin")
            await check("GET", "/orders/999999/payment-summary", 404, "admin")
            for path in [
                "/payments/0",
                "/orders/0/payment-summary",
                "/payments?limit=0",
                "/payments?offset=-1",
                "/payments?transaction_type=BAD",
                "/payments?method=CARD",
                "/payments?order_id=0",
                "/payments?date_from=2026-01-01T00:00:00",
                "/payments?date_from=2026-12-31T00:00:00Z&date_to=2026-01-01T00:00:00Z",
            ]:
                await check("GET", path, 422, "admin")
            r = await check(
                "GET",
                f"/payments?order_id={oa}&transaction_type=PAYMENT&method=BANK_TRANSFER&search=PAY_A_002",
                200,
                "admin",
            )
            assert [i["id"] for i in r.json()["items"]] == [second]
            r = await check("GET", f"/payments?order_id={oa}&limit=1&offset=1", 200, "admin")
            assert len(r.json()["items"]) == 1
            r = await check("GET", "/payments?date_from=2999-01-01T00:00:00Z", 200, "admin")
            assert r.json()["items"] == []
            r = await check("GET", f"/payments/{first}", 200, "admin")
            created_at = r.json()["created_at"]
            r = await check(
                "GET",
                "/payments",
                200,
                "admin",
                params={"order_id": oa, "date_from": created_at, "date_to": created_at},
            )
            assert [i["id"] for i in r.json()["items"]] == [first]
            # Changing the customer assignment/link changes transaction visibility immediately.
            await check(
                "PATCH",
                f"/customers/{ca}",
                200,
                "admin",
                json={"sale_id": ids["sale_b"], "user_id": None},
            )
            await check("GET", f"/payments/{first}", 404, "sale_a")
            await check("GET", f"/payments/{first}", 200, "sale_b")
            await check("GET", f"/payments/{first}", 404, "customer_a")
            await check(
                "PATCH",
                f"/customers/{ca}",
                200,
                "admin",
                json={"sale_id": ids["sale_a"], "user_id": ids["customer_a"]},
            )
            # Two distinct receipts race to collect the same balance: exactly one can succeed.
            race = await new_order(fee="100.00")
            race_body = {
                "order_id": race,
                "amount": "80.00",
                "method": "CASH",
                "reference_code": "RACE_A",
            }
            responses = await asyncio.gather(
                *[
                    client.post(
                        "/payments",
                        headers=tokens[who],
                        json={**race_body, "reference_code": ref},
                    )
                    for who, ref in [("admin", "RACE_A"), ("accountant", "RACE_B")]
                ]
            )
            assert sorted(r.status_code for r in responses) == [201, 409], [
                (r.status_code, r.text) for r in responses
            ]
            count += 2
            # Concurrent refunds cannot exceed net collected.
            responses = await asyncio.gather(
                *[
                    client.post(
                        "/payments/refunds",
                        headers=tokens[who],
                        json={**race_body, "amount": "60.00", "reference_code": ref},
                    )
                    for who, ref in [("admin", "REF_RACE_A"), ("accountant", "REF_RACE_B")]
                ]
            )
            assert sorted(r.status_code for r in responses) == [201, 409]
            count += 2
            r = await check("GET", f"/orders/{race}/payment-summary", 200, "admin")
            assert r.json()["net_paid"] == "20.00"
            # Same reference racing is idempotent, not two receipts or a false overpayment.
            replay_order = await new_order(fee="80.00")
            replay_body = {**race_body, "order_id": replay_order, "reference_code": "SAME_REF"}
            responses = await asyncio.gather(
                *[
                    client.post("/payments", headers=tokens[who], json=replay_body)
                    for who in ("admin", "accountant")
                ]
            )
            assert sorted(r.status_code for r in responses) == [200, 201], [
                (r.status_code, r.text) for r in responses
            ]
            assert len({r.json()["id"] for r in responses}) == 1
            count += 2
            r = await check("GET", f"/payments?order_id={replay_order}", 200, "admin")
            assert len(r.json()["items"]) == 1
            # Replayed refunds are also safe when two operators submit them concurrently.
            refund_replay = {**replay_body, "amount": "30.00", "reference_code": "SAME_REFUND"}
            responses = await asyncio.gather(
                *[
                    client.post("/payments/refunds", headers=tokens[who], json=refund_replay)
                    for who in ("admin", "accountant")
                ]
            )
            assert sorted(r.status_code for r in responses) == [200, 201]
            assert len({r.json()["id"] for r in responses}) == 1
            count += 2
            # A global reference cannot be committed against two different orders.
            conflict_order = await new_order(fee="80.00")
            conflict_other = await new_order(fee="80.00")
            responses = await asyncio.gather(
                *[
                    client.post(
                        "/payments",
                        headers=tokens[who],
                        json={**race_body, "order_id": oid, "reference_code": "GLOBAL_REF"},
                    )
                    for who, oid in [("admin", conflict_order), ("accountant", conflict_other)]
                ]
            )
            assert sorted(r.status_code for r in responses) == [201, 409]
            count += 2
            # Payment and cancellation share the parent order lock.
            cancel_race = await new_order(fee="100.00")
            paid, cancelled = await asyncio.gather(
                client.post(
                    "/payments",
                    headers=tokens["accountant"],
                    json={
                        **race_body,
                        "order_id": cancel_race,
                        "amount": "100.00",
                        "reference_code": "CANCEL_RACE",
                    },
                ),
                client.patch(
                    f"/orders/{cancel_race}/status",
                    headers=tokens["admin"],
                    json={"status": "CANCELLED"},
                ),
            )
            assert (paid.status_code, cancelled.status_code) in ((201, 409), (409, 200)), (
                paid.text,
                cancelled.text,
            )
            count += 2
            # Free orders are settled without a zero-valued ledger row.
            free = await new_order(fee="0")
            r = await check("GET", f"/orders/{free}/payment-summary", 200, "accountant")
            assert r.json()["payment_status"] == "PAID"
            await check(
                "POST",
                "/payments",
                409,
                "admin",
                json={**body, "order_id": free, "amount": "0.01", "reference_code": "FREE"},
            )
            # DECIMAL calculations remain exact near the storage limit and across repeat cycles.
            huge = await new_order(fee="9999999999999999.99")
            for index in range(3):
                await check(
                    "POST",
                    "/payments",
                    201,
                    "accountant",
                    json={
                        **body,
                        "order_id": huge,
                        "amount": "9999999999999999.99",
                        "reference_code": f"HUGE_PAY_{index}",
                    },
                )
                await check(
                    "POST",
                    "/payments/refunds",
                    201,
                    "accountant",
                    json={
                        **body,
                        "order_id": huge,
                        "amount": "9999999999999999.99",
                        "reference_code": f"HUGE_REF_{index}",
                    },
                )
            r = await check("GET", f"/orders/{huge}/payment-summary", 200, "admin")
            assert (
                r.json()["total_paid"] == "29999999999999999.97" and r.json()["net_paid"] == "0.00"
            )
            # Existing legacy overpayments/cancelled balances can be audited and refunded.
            legacy = await new_order(fee="100.00")
            async with db.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO thanh_toan(ma_don_hang,so_tien,loai_giao_dich,phuong_thuc,ma_tham_chieu,nguoi_tao) VALUES(:id,120,'PAYMENT','CASH','LEGACY_OVER',:actor)"
                    ),
                    {"id": legacy, "actor": ids["admin"]},
                )
            r = await check("GET", f"/orders/{legacy}/payment-summary", 200, "admin")
            assert r.json()["payment_status"] == "OVERPAID" and r.json()["refund_due"] == "20.00"
            await check(
                "POST",
                "/payments/refunds",
                201,
                "accountant",
                json={
                    **body,
                    "order_id": legacy,
                    "amount": "20.00",
                    "reference_code": "REF_LEGACY_OVER",
                },
            )
            async with db.begin() as conn:
                await conn.execute(
                    text("UPDATE don_hang SET trang_thai='CANCELLED' WHERE ma=:id"),
                    {"id": legacy},
                )
            r = await check("GET", f"/orders/{legacy}/payment-summary", 200, "admin")
            assert (
                r.json()["payment_status"] == "REFUND_DUE"
                and r.json()["refund_due"] == "100.00"
                and r.json()["amount_due"] == "0.00"
            )
            await check(
                "POST",
                "/payments/refunds",
                201,
                "accountant",
                json={
                    **body,
                    "order_id": legacy,
                    "amount": "100.00",
                    "reference_code": "REF_LEGACY_CANCELLED",
                },
            )
            r = await check("GET", f"/orders/{legacy}/payment-summary", 200, "admin")
            assert r.json()["payment_status"] == "CANCELLED"
            # Invalid legacy balances are visible for audit, but cannot accept new mutations.
            invalid_legacy = await new_order(fee="100.00")
            async with db.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO thanh_toan(ma_don_hang,so_tien,loai_giao_dich,phuong_thuc,ma_tham_chieu,nguoi_tao) VALUES(:id,10,'REFUND','CASH','INVALID_LEGACY',:actor)"
                    ),
                    {"id": invalid_legacy, "actor": ids["admin"]},
                )
            r = await check("GET", f"/orders/{invalid_legacy}/payment-summary", 200, "admin")
            assert r.json()["payment_status"] == "INVALID" and r.json()["net_paid"] == "-10.00"
            for path in ("/payments", "/payments/refunds"):
                await check(
                    "POST",
                    path,
                    409,
                    "accountant",
                    json={
                        **body,
                        "order_id": invalid_legacy,
                        "reference_code": "INVALID_LEDGER",
                    },
                )
            await check(
                "PATCH",
                f"/orders/{invalid_legacy}/status",
                409,
                "admin",
                json={"status": "CANCELLED"},
            )
            # SQL layer independently rejects unauthorized writes and bad values.
            from sqlalchemy.exc import DBAPIError

            async with db.connect() as conn:
                for actor, amount, expected in [
                    (ids["sale_a"], "1", "FORBIDDEN"),
                    (ids["admin"], "-1", "INVALID_PAYMENT"),
                ]:
                    try:
                        await conn.execute(
                            text(
                                "CALL sp_record_payment(:actor,:order,:amount,'PAYMENT','CASH','SQL_DENIED')"
                            ),
                            {"actor": actor, "order": ob, "amount": amount},
                        )
                        raise AssertionError("SQL accepted forbidden/invalid transaction")
                    except DBAPIError as exc:
                        assert exc.orig.args[0] == 1644 and exc.orig.args[1] == expected
                        await conn.rollback()
            async with db.begin() as conn:
                await conn.execute(
                    text("UPDATE nguoi_dung SET vai_tro='CUSTOMER' WHERE ma=:id"),
                    {"id": ids["accountant"]},
                )
            await check("POST", "/payments", 403, "accountant", json=body)
            r = await check("GET", "/auth/permissions", 200, "customer_a")
            assert "payments:read:own" in r.json()["permissions"]
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=backend), base_url="http://backend"
            ) as direct:
                assert (await direct.get("/payments", headers=tokens["admin"])).status_code == 403
            print(
                f"PASS: {count} HTTP checks; MySQL receipt/refund balances, idempotency, races, RBAC and precision; 10 tables."
            )
        if "--postman" in sys.argv:
            await run_postman("Logistics-Payments.postman_collection.json")
    finally:
        if backend_engine is not None:
            await backend_engine.dispose()
        await db.dispose()
        if created:
            assert (
                name.startswith("cms_payment_test_") and len(name) == len("cms_payment_test_") + 32
            )
            async with admin.begin() as conn:
                await conn.exec_driver_sql(f"DROP DATABASE `{name}`")
        await admin.dispose()


if __name__ == "__main__":
    asyncio.run(main())
