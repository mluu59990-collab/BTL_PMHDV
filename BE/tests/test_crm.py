import uuid

BASE = "/api/v1/crm"


def create(client, headers, path, data, user="admin"):
    response = client.post(BASE + path, json=data, headers=headers[user])
    assert response.status_code == 201, response.text
    return response.json()


def test_crm_ownership_and_filters(client, headers):
    sale = client.get("/api/v1/users/me", headers=headers["sale01"]).json()["id"]
    customer = create(
        client,
        headers,
        "/customers",
        {"code": uuid.uuid4().hex, "name": "Khách của Sale"},
        "sale01",
    )
    assert customer["sale_id"] == sale
    other = create(
        client,
        headers,
        "/customers",
        {"code": uuid.uuid4().hex, "name": "Khách chưa giao"},
    )
    assert (
        client.get(
            f"{BASE}/customers/{other['id']}", headers=headers["sale01"]
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"{BASE}/customers/{customer['id']}",
            json={"sale_id": None},
            headers=headers["sale01"],
        ).status_code
        == 403
    )
    assert (
        client.post(
            BASE + "/customers",
            json={"code": uuid.uuid4().hex, "name": "Sai quyền", "credit_limit": "100"},
            headers=headers["sale01"],
        ).status_code
        == 403
    )
    ids = [
        x["id"]
        for x in client.get(BASE + "/customers", headers=headers["sale01"]).json()[
            "items"
        ]
    ]
    assert customer["id"] in ids and other["id"] not in ids
    tracking = create(
        client,
        headers,
        "/trackings",
        {
            "customer_id": customer["id"],
            "tracking_code": uuid.uuid4().hex,
            "shipped_on": "2026-09-27",
        },
        "sale01",
    )
    response = client.get(
        BASE + "/trackings",
        params={
            "customer_id": customer["id"],
            "sale_id": sale,
            "date_from": "2026-09-27",
            "date_to": "2026-09-27",
        },
        headers=headers["sale01"],
    )
    assert [x["id"] for x in response.json()["items"]] == [tracking["id"]]
    assert (
        client.get(
            BASE + "/trackings",
            params={"date_from": "2026-09-28", "date_to": "2026-09-27"},
            headers=headers["admin"],
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"{BASE}/trackings/{tracking['id']}",
            json={"customer_id": other["id"]},
            headers=headers["sale01"],
        ).status_code
        == 403
    )
    assert (
        client.get(BASE + "/customers", headers=headers["khach01"]).status_code == 403
    )


def test_care_vip_and_validation(client, headers):
    customer = create(
        client, headers, "/customers", {"code": uuid.uuid4().hex, "name": "VIP"}
    )
    care = create(
        client,
        headers,
        "/care-tasks",
        {
            "customer_id": customer["id"],
            "title": "Gọi xác nhận",
            "due_on": "2026-10-01",
        },
    )
    url = f"{BASE}/care-tasks/{care['id']}"
    assert (
        client.patch(
            url, json={"status": "COMPLETED"}, headers=headers["admin"]
        ).status_code
        == 422
    )
    for status in ("CONTACTED", "FOLLOW_UP", "COMPLETED"):
        assert (
            client.patch(
                url, json={"status": status}, headers=headers["admin"]
            ).status_code
            == 200
        )
    assert (
        client.patch(url, json={"status": "NEW"}, headers=headers["admin"]).status_code
        == 422
    )
    package = create(
        client,
        headers,
        "/vip-packages",
        {
            "code": uuid.uuid4().hex,
            "name": "VIP30",
            "conditions": "Đăng ký",
            "benefits": "Ưu tiên",
            "duration_days": 30,
        },
    )
    membership = {
        "customer_id": customer["id"],
        "package_id": package["id"],
        "valid_from": "2026-10-01",
        "valid_until": "2026-10-30",
    }
    created = create(client, headers, "/vip-memberships", membership)
    assert (
        client.post(
            BASE + "/vip-memberships", json=membership, headers=headers["admin"]
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"{BASE}/vip-memberships/{created['id']}",
            json={"valid_until": "2026-10-31"},
            headers=headers["admin"],
        ).status_code
        == 422
    )
    assert (
        client.post(
            BASE + "/service-reviews",
            json={
                "customer_id": customer["id"],
                "period_start": "2026-10-02",
                "period_end": "2026-10-01",
                "rating": 5,
            },
            headers=headers["admin"],
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"{BASE}/customers/{customer['id']}",
            json={"name": None},
            headers=headers["admin"],
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"{BASE}/customers/{customer['id']}",
            json={"credit_limit": "-1"},
            headers=headers["admin"],
        ).status_code
        == 422
    )
    assert (
        client.delete(
            f"{BASE}/customers/{customer['id']}", headers=headers["admin"]
        ).status_code
        == 204
    )
    assert (
        client.post(
            BASE + "/care-tasks",
            json={
                "customer_id": customer["id"],
                "title": "Gọi",
                "due_on": "2026-10-01",
            },
            headers=headers["admin"],
        ).status_code
        == 422
    )


def test_sales_plans(client, headers):
    sale = client.get("/api/v1/users/me", headers=headers["sale01"]).json()["id"]
    body = {
        "sale_id": sale,
        "period_type": "QUARTER",
        "period_start": "2027-02-01",
        "target_amount": "100000",
    }
    assert (
        client.post(
            BASE + "/sales-plans", json=body, headers=headers["admin"]
        ).status_code
        == 422
    )
    body["period_start"] = "2027-01-01"
    plan = create(client, headers, "/sales-plans", body, "sale01")
    assert (
        client.post(
            BASE + "/sales-plans", json=body, headers=headers["admin"]
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"{BASE}/sales-plans/{plan['id']}",
            json={"actual_amount": "20000"},
            headers=headers["sale01"],
        ).status_code
        == 200
    )


def test_care_must_start_at_new(client, headers):
    customer = create(
        client, headers, "/customers", {"code": uuid.uuid4().hex, "name": "Khách mới"}
    )
    response = client.post(
        BASE + "/care-tasks",
        json={
            "customer_id": customer["id"],
            "title": "Chưa liên hệ",
            "due_on": "2026-10-01",
            "status": "COMPLETED",
        },
        headers=headers["admin"],
    )
    assert response.status_code == 422, response.text


def test_registration_rejects_whitespace_name(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "blank_" + uuid.uuid4().hex[:12],
            "password": "Test@123456",
            "full_name": "   ",
        },
    )
    assert response.status_code == 422, response.text


def test_concurrent_vip_registration_has_one_winner(client, headers):
    from concurrent.futures import ThreadPoolExecutor

    customer = create(
        client,
        headers,
        "/customers",
        {"code": uuid.uuid4().hex, "name": "Khách đăng ký đồng thời"},
    )
    package = create(
        client,
        headers,
        "/vip-packages",
        {
            "code": uuid.uuid4().hex,
            "name": "VIP",
            "conditions": "Đăng ký",
            "benefits": "Ưu tiên",
            "duration_days": 30,
        },
    )
    data = {
        "customer_id": customer["id"],
        "package_id": package["id"],
        "valid_from": "2026-11-01",
        "valid_until": "2026-11-30",
    }

    def send():
        return client.post(
            BASE + "/vip-memberships", json=data, headers=headers["admin"]
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: send(), range(2)))
    assert sorted(results) == [201, 422]
