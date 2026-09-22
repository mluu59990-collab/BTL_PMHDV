import runpy
import uuid
from pathlib import Path

import httpx
import pytest

API = "/api/v1"


def unique_code():
    return "TEST_" + uuid.uuid4().hex[:12].upper()


def create(client, headers, path, body, user="admin"):
    response = client.post(API + path, headers=headers[user], json=body)
    assert response.status_code == 201, response.text
    return response.json()


def product_body(**changes):
    return {
        "sku": unique_code(),
        "name": "Sản phẩm test",
        "reference_price": "12.3456",
        **changes,
    }


@pytest.mark.parametrize(
    "kind,code",
    [
        ("countries", "JP"),
        ("units", "CUSTOM_UNIT"),
        ("package-types", "CUSTOM_PACKAGE"),
        ("categories", "CUSTOM_CATEGORY"),
    ],
)
def test_reference_crud(client, headers, kind, code):
    path = f"/catalog/{kind}"
    row = create(
        client, headers, path, {"code": code.lower(), "name": " Danh mục mới "}
    )
    assert row["code"] == code and row["name"] == "Danh mục mới"
    duplicate = client.post(
        API + path, headers=headers["admin"], json={"code": code, "name": "Trùng"}
    )
    assert duplicate.status_code == 409
    detail = f"{API}{path}/{row['id']}"
    assert client.get(detail, headers=headers["khach01"]).json()["id"] == row["id"]
    response = client.patch(
        detail,
        headers=headers["admin"],
        json={"name": "Tên mới", "description": "Mô tả"},
    )
    assert response.status_code == 200 and response.json()["name"] == "Tên mới"
    response = client.get(
        API + path, headers=headers["admin"], params={"search": code, "limit": 1}
    )
    assert response.json()["total"] == 1
    assert client.delete(detail, headers=headers["admin"]).status_code == 204
    assert (
        client.get(
            API + path, headers=headers["admin"], params={"search": code}
        ).json()["total"]
        == 0
    )
    assert client.get(detail, headers=headers["admin"]).json()["is_active"] is False
    assert (
        client.patch(
            detail, headers=headers["admin"], json={"is_active": True}
        ).status_code
        == 200
    )


def test_product_crud_links_and_filters(client, headers):
    refs = {}
    for kind in ("countries", "units", "package-types", "categories"):
        refs[kind] = client.get(
            API + f"/catalog/{kind}", headers=headers["admin"]
        ).json()["items"][0]["id"]
    body = product_body(
        origin_country_id=refs["countries"],
        shipping_country_id=refs["countries"],
        unit_id=refs["units"],
        package_type_id=refs["package-types"],
        category_id=refs["categories"],
        source_url="https://detail.1688.com/offer/123.html",
        image_url="https://example.com/image.jpg",
    )
    row = create(client, headers, "/products", body, "muahang01")
    assert row["reference_price"] == "12.3456"
    path = f"{API}/products/{row['id']}"
    assert client.get(path, headers=headers["khach01"]).status_code == 200
    response = client.get(
        API + "/products",
        headers=headers["sale01"],
        params={"category_id": refs["categories"], "search": body["sku"]},
    )
    assert response.json()["total"] == 1
    assert (
        client.post(
            API + "/products",
            headers=headers["admin"],
            json={**body, "sku": body["sku"].lower()},
        ).status_code
        == 409
    )
    response = client.patch(
        path,
        headers=headers["muahang01"],
        json={"reference_price": "99.1234", "image_url": None},
    )
    assert (
        response.status_code == 200 and response.json()["reference_price"] == "99.1234"
    )
    assert response.json()["image_url"] is None
    # Failed updates must leave the saved product unchanged.
    assert (
        client.patch(
            path,
            headers=headers["admin"],
            json={"name": "Không lưu", "category_id": 9999999},
        ).status_code
        == 422
    )
    assert client.get(path, headers=headers["admin"]).json()["name"] == body["name"]
    assert client.delete(path, headers=headers["muahang01"]).status_code == 204
    assert (
        client.get(
            API + "/products", headers=headers["admin"], params={"search": body["sku"]}
        ).json()["total"]
        == 0
    )
    assert (
        client.get(
            API + "/products",
            headers=headers["admin"],
            params={"search": body["sku"], "active_only": False},
        ).json()["total"]
        == 1
    )
    assert (
        client.patch(
            path, headers=headers["admin"], json={"is_active": True}
        ).status_code
        == 200
    )


def test_inactive_references(client, headers):
    unit = create(
        client, headers, "/catalog/units", {"code": unique_code(), "name": "Đơn vị"}
    )
    product = create(client, headers, "/products", product_body(unit_id=unit["id"]))
    client.delete(f"{API}/catalog/units/{unit['id']}", headers=headers["admin"])
    assert (
        client.post(
            API + "/products",
            headers=headers["admin"],
            json=product_body(unit_id=unit["id"]),
        ).status_code
        == 422
    )
    path = f"{API}/products/{product['id']}"
    # Historical links survive; unrelated edits remain possible.
    assert client.get(path, headers=headers["admin"]).json()["unit_id"] == unit["id"]
    assert (
        client.patch(
            path, headers=headers["admin"], json={"name": "Tên khác"}
        ).status_code
        == 200
    )
    assert (
        client.patch(path, headers=headers["admin"], json={"unit_id": None}).status_code
        == 200
    )


def test_rights_targets_dates_and_crud(client, headers):
    product = create(client, headers, "/products", product_body())
    category = create(
        client, headers, "/catalog/categories", {"code": unique_code(), "name": "Ngành"}
    )
    body = {
        "brand_name": "Thương hiệu",
        "holder_name": "Công ty",
        "right_type": "DISTRIBUTION_AUTHORIZATION",
        "product_id": product["id"],
        "valid_from": "2026-01-01",
        "valid_until": "2026-12-31",
        "document_url": "https://example.com/authorization.pdf",
    }
    row = create(client, headers, "/brand-rights", body)
    path = f"{API}/brand-rights/{row['id']}"
    for changes in (
        {"category_id": category["id"]},
        {"product_id": None},
        {"valid_until": "2025-01-01"},
        {"valid_from": "2027-01-01"},
    ):
        assert (
            client.patch(path, headers=headers["admin"], json=changes).status_code
            == 422
        )
    assert (
        client.get(path, headers=headers["sale01"]).json()["valid_until"]
        == "2026-12-31"
    )
    response = client.patch(
        path,
        headers=headers["admin"],
        json={"product_id": None, "category_id": category["id"], "document_url": None},
    )
    assert response.status_code == 200 and response.json()["product_id"] is None
    result = client.get(
        API + "/brand-rights",
        headers=headers["muahang01"],
        params={"category_id": category["id"]},
    ).json()
    assert result["total"] == 1 and result["items"][0]["id"] == row["id"]
    assert client.delete(path, headers=headers["admin"]).status_code == 204
    assert (
        client.get(
            API + "/brand-rights",
            headers=headers["admin"],
            params={"category_id": category["id"]},
        ).json()["total"]
        == 0
    )
    assert client.get(path, headers=headers["admin"]).json()["is_active"] is False
    assert (
        client.patch(
            path, headers=headers["admin"], json={"is_active": True}
        ).status_code
        == 200
    )
    for invalid in (
        {**body, "product_id": None},
        {**body, "category_id": category["id"]},
        {**body, "product_id": 99999999},
        {**body, "valid_until": "2025-01-01"},
    ):
        assert (
            client.post(
                API + "/brand-rights", headers=headers["admin"], json=invalid
            ).status_code
            == 422
        )


@pytest.mark.parametrize("user", ["sale01", "kho01", "ketoan01", "khach01"])
def test_product_write_rbac(client, headers, user):
    assert (
        client.post(
            API + "/products", headers=headers[user], json=product_body()
        ).status_code
        == 403
    )
    assert (
        client.patch(
            API + "/products/999999", headers=headers[user], json={"name": "X"}
        ).status_code
        == 403
    )
    assert (
        client.delete(API + "/products/999999", headers=headers[user]).status_code
        == 403
    )


@pytest.mark.parametrize(
    "user", ["sale01", "muahang01", "kho01", "ketoan01", "khach01"]
)
def test_admin_only_writes(client, headers, user):
    for path, body in (
        ("/catalog/units", {"code": unique_code(), "name": "X"}),
        (
            "/brand-rights",
            {
                "brand_name": "X",
                "holder_name": "Y",
                "right_type": "COPYRIGHT",
                "product_id": 1,
            },
        ),
    ):
        assert (
            client.post(API + path, headers=headers[user], json=body).status_code == 403
        )
        assert (
            client.patch(
                API + path + "/999999", headers=headers[user], json={"is_active": False}
            ).status_code
            == 403
        )
        assert (
            client.delete(API + path + "/999999", headers=headers[user]).status_code
            == 403
        )


@pytest.mark.parametrize("user", ["khach01", "kho01", "ketoan01"])
def test_rights_read_rbac(client, headers, user):
    assert client.get(API + "/brand-rights", headers=headers[user]).status_code == 403
    assert client.get(API + "/brand-rights/1", headers=headers[user]).status_code == 403


@pytest.mark.parametrize("path", ["/products", "/catalog/units", "/brand-rights"])
def test_auth_missing_and_not_found(client, headers, path):
    assert client.get(API + path).status_code == 401
    assert (
        client.get(API + path + "/999999999", headers=headers["admin"]).status_code
        == 404
    )
    assert (
        client.delete(API + path + "/999999999", headers=headers["admin"]).status_code
        == 404
    )
    assert (
        client.get(
            API + path, headers=headers["admin"], params={"limit": 101}
        ).status_code
        == 422
    )
    assert (
        client.get(
            API + path, headers=headers["admin"], params={"offset": -1}
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"name": "   "},
        {"sku": "a b"},
        {"reference_price": "-1"},
        {"reference_price": "NaN"},
        {"reference_price": "1.12345"},
        {"currency_code": "XXX"},
        {"source_url": "https://1688.com.attacker.test/x"},
        {"source_url": "javascript:alert(1)"},
        {"image_url": "file:///tmp/x"},
        {"category_id": 999999999},
        {"unit_id": 0},
        {"unknown": True},
    ],
)
def test_product_validation(client, headers, changes):
    assert (
        client.post(
            API + "/products", headers=headers["admin"], json=product_body(**changes)
        ).status_code
        == 422
    )


def test_patch_null_and_empty_name(client, headers):
    row = create(client, headers, "/products", product_body())
    path = f"{API}/products/{row['id']}"
    for changes in (
        {"name": None},
        {"name": "  "},
        {"reference_price": None},
        {"is_active": None},
    ):
        assert (
            client.patch(path, headers=headers["admin"], json=changes).status_code
            == 422
        )
    assert (
        client.post(
            API + "/catalog/countries",
            headers=headers["admin"],
            json={"code": "ABC", "name": "Sai mã"},
        ).status_code
        == 422
    )
    assert (
        client.get(API + "/catalog/invalid", headers=headers["admin"]).status_code
        == 422
    )


def test_session_one_regression(client, monkeypatch):
    """Run the original 69 smoke checks through ASGI against the isolated DB."""
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: client)
    monkeypatch.setattr("sys.argv", ["scripts/smoke_test.py", "http://testserver"])
    with pytest.raises(SystemExit) as result:
        runpy.run_path(
            str(Path(__file__).resolve().parents[1] / "scripts/smoke_test.py"),
            run_name="__main__",
        )
    assert result.value.code == 0
