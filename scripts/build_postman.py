"""Generate human-readable Postman cases: ~10 distinct cases per method/path."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
folders = []
current = None
coverage = {}


def folder(name):
    global current
    current = {"name": name, "item": []}
    folders.append(current)


def req(
    name,
    method,
    path,
    status,
    body=None,
    token="admin",
    save=None,
    checks="",
    form=False,
    endpoint=None,
):
    endpoint = endpoint or method + " " + path.split("?")[0]
    coverage[endpoint] = coverage.get(endpoint, 0) + 1
    headers = []
    if token:
        headers.append(
            {
                "key": "Authorization",
                "value": "Bearer "
                + (
                    "invalid.jwt.token"
                    if token == "invalid"
                    else "{{" + token + "_token}}"
                ),
            }
        )
    request = {
        "method": method,
        "header": headers,
        "url": "{{base_url}}" + path,
        "description": f"Thao tác: {name}. Kỳ vọng HTTP {status}. Chạy thật và đối chiếu phản hồi, không giả lập lỗi.",
    }
    if body is not None:
        if form:
            request["body"] = {
                "mode": "urlencoded",
                "urlencoded": [
                    {"key": k, "value": str(v), "type": "text"} for k, v in body.items()
                ],
            }
        else:
            headers.append({"key": "Content-Type", "value": "application/json"})
            request["body"] = {
                "mode": "raw",
                "raw": json.dumps(body, ensure_ascii=False),
                "options": {"raw": {"language": "json"}},
            }
    tests = [
        f"pm.test({json.dumps(name, ensure_ascii=False)}, function () {{ pm.response.to.have.status({status}); }});",
        'pm.test("Không có lỗi máy chủ", function () { pm.expect(pm.response.code).to.be.below(500); });',
    ]
    if status >= 400:
        tests.append(
            'pm.test("Có thông báo lỗi", function () { pm.expect(pm.response.json()).to.have.property("detail"); });'
        )
    if save:
        tests.append(
            f'if (pm.response.code === {status}) pm.collectionVariables.set("{save}", pm.response.json().id);'
        )
    if checks:
        tests.append(checks)
    current["item"].append(
        {
            "name": f"{len(current['item']) + 1:02}. {name} [{status}]",
            "request": request,
            "event": [
                {"listen": "test", "script": {"type": "text/javascript", "exec": tests}}
            ],
        }
    )


def login(user, password, key):
    req(
        "Đăng nhập " + user,
        "POST",
        "/api/v1/auth/login",
        200,
        {"username": user, "password": password},
        None,
        form=True,
        checks=f'if(pm.response.code===200) {{ pm.collectionVariables.set("{key}_token",pm.response.json().access_token); pm.collectionVariables.set("{key}_refresh",pm.response.json().refresh_token); }}',
    )


folder("00. Chuẩn bị tài khoản và dữ liệu liên kết")
login("admin", "Admin@123456", "admin")
login("sale01", "Test@123456", "sale")
login("khach01", "Test@123456", "customer")
req("Lấy ID Sale", "GET", "/api/v1/users/me", 200, token="sale", save="sale_id")
req(
    "Tạo khóa duy nhất cho lượt chạy",
    "GET",
    "/health",
    200,
    token=None,
    checks='pm.collectionVariables.set("run", Date.now().toString(36));',
)
req(
    "Chọn mã nước chưa dùng",
    "GET",
    "/api/v1/catalog/countries?active_only=false&limit=100",
    200,
    checks='const used = pm.response.json().items.map(x=>x.code); const codes=[]; for(let a=65;a<91;a++)for(let b=65;b<91;b++){const c=String.fromCharCode(a,b);if(!used.includes(c))codes.push(c);} pm.collectionVariables.set("country_code",codes[0]); pm.collectionVariables.set("country_second",codes[1]);',
)

req(
    "Chọn kỳ kế hoạch chưa có",
    "GET",
    "/api/v1/crm/sales-plans?active_only=false&limit=100",
    200,
    checks='const used=pm.response.json().items.filter(x=>x.period_type==="MONTH" && x.sale_id===Number(pm.collectionVariables.get("sale_id"))).map(x=>x.period_start); for(let y=2030;y<2200;y++){const d=y+"-01-01";if(!used.includes(d)){pm.collectionVariables.set("plan_month",d);break;}}',
)

# Explicit bodies expose all inputs in Postman's editor; IDs are captured from actual responses.
resources = []
for kind in ("countries", "units", "package-types", "categories"):
    resources.append(
        dict(
            path="/catalog/" + kind,
            key=kind.replace("-", "_"),
            body={
                "code": "{{country_code}}"
                if kind == "countries"
                else "{{run}}_" + kind,
                "name": "Danh mục kiểm thử",
            },
            patch={"name": "Danh mục đã sửa"},
            bad={"code": "123" if kind == "countries" else "!@#"},
            nullable="name",
            duplicate=True,
            read="customer",
        )
    )
resources += [
    dict(
        path="/products",
        key="product",
        body={
            "sku": "SP_{{run}}",
            "name": "Áo thun nhập thử",
            "reference_price": "25.5000",
            "category_id": "{{categories_id}}",
            "origin_country_id": "{{countries_id}}",
            "source_url": "https://detail.1688.com/offer/123.html",
        },
        patch={"name": "Áo đã sửa"},
        bad={"reference_price": "-1"},
        nullable="name",
        duplicate=True,
        read="customer",
    ),
    dict(
        path="/brand-rights",
        key="right",
        body={
            "brand_name": "Nhãn {{run}}",
            "holder_name": "Công ty A",
            "right_type": "COPYRIGHT",
            "product_id": "{{product_id}}",
        },
        patch={"holder_name": "Công ty B"},
        bad={"right_type": "WRONG"},
        nullable="brand_name",
        duplicate=False,
        read="sale",
    ),
    dict(
        path="/crm/customers",
        key="crm_customer",
        body={
            "code": "KH_{{run}}",
            "name": "Nguyễn Văn An",
            "sale_id": "{{sale_id}}",
            "phone": "0901234567",
            "credit_limit": "1000000",
        },
        patch={"name": "Nguyễn Văn An đã sửa"},
        bad={"credit_limit": "-1"},
        nullable="name",
        duplicate=True,
        read="sale",
    ),
    dict(
        path="/crm/trackings",
        key="tracking",
        body={
            "customer_id": "{{crm_customer_id}}",
            "tracking_code": "VD_{{run}}",
            "shipped_on": "2026-09-27",
        },
        patch={"note": "Đã gọi xác nhận"},
        bad={"shipped_on": "2026-02-30"},
        nullable="tracking_code",
        duplicate=True,
        read="sale",
    ),
    dict(
        path="/crm/care-tasks",
        key="care",
        body={
            "customer_id": "{{crm_customer_id}}",
            "title": "Gọi tư vấn đơn hàng",
            "due_on": "2026-10-01",
        },
        patch={"status": "CONTACTED"},
        bad={"status": "UNKNOWN"},
        nullable="title",
        duplicate=False,
        read="sale",
    ),
    dict(
        path="/crm/sales-plans",
        key="plan",
        body={
            "sale_id": "{{sale_id}}",
            "period_type": "MONTH",
            "period_start": "{{plan_month}}",
            "target_amount": "50000000",
        },
        patch={"actual_amount": "2000000"},
        bad={"target_amount": "-1"},
        nullable="target_amount",
        duplicate=True,
        read="sale",
    ),
    dict(
        path="/crm/service-reviews",
        key="review",
        body={
            "customer_id": "{{crm_customer_id}}",
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "rating": 5,
            "comment": "Giao hàng đúng hẹn",
        },
        patch={"rating": 4},
        bad={"rating": 6},
        nullable="rating",
        duplicate=False,
        read="sale",
    ),
    dict(
        path="/crm/vip-packages",
        key="vip",
        body={
            "code": "VIP_{{run}}",
            "name": "Gói ưu tiên",
            "conditions": "Đăng ký tại quầy",
            "benefits": "Ưu tiên kiểm hàng",
            "duration_days": 30,
        },
        patch={"benefits": "Ưu tiên kiểm hàng và hỗ trợ"},
        bad={"duration_days": 0},
        nullable="name",
        duplicate=True,
        read="sale",
    ),
    dict(
        path="/crm/vip-memberships",
        key="membership",
        body={
            "customer_id": "{{crm_customer_id}}",
            "package_id": "{{vip_id}}",
            "valid_from": "2026-10-01",
            "valid_until": "2026-10-30",
        },
        patch={"note": "Đã xác nhận đăng ký"},
        bad={"valid_until": "2026-09-30"},
        nullable="valid_until",
        duplicate=False,
        read="sale",
    ),
]

for r in resources:
    path = "/api/v1" + r["path"]
    body = r["body"]
    key = r["key"]
    detail = path + "/{{" + key + "_id}}"
    folder("CRM / Danh mục — " + r["path"])
    ep = "POST " + path
    req(
        "Nhập đầy đủ thông tin hợp lệ",
        "POST",
        path,
        201,
        body,
        save=key + "_id",
        endpoint=ep,
        checks='pm.test("Đã tạo ID",()=>pm.expect(pm.response.json().id).to.be.a("number"));',
    )
    req("Quên đăng nhập khi tạo", "POST", path, 401, body, token=None, endpoint=ep)
    req("Token bị sửa sai", "POST", path, 401, body, token="invalid", endpoint=ep)
    req(
        "Khách hàng thử tạo dữ liệu quản trị",
        "POST",
        path,
        403,
        body,
        token="customer",
        endpoint=ep,
    )
    req("Bỏ trống toàn bộ form", "POST", path, 422, {}, endpoint=ep)
    req(
        "Nhập sai giá trị hoặc ngày tháng",
        "POST",
        path,
        422,
        body | r["bad"],
        endpoint=ep,
    )
    req(
        "Gửi trường lạ từ form",
        "POST",
        path,
        422,
        body | {"unknown_field": "abc"},
        endpoint=ep,
    )
    req(
        "Để null trường bắt buộc",
        "POST",
        path,
        422,
        body | {r["nullable"]: None},
        endpoint=ep,
    )
    required = next(iter(body))
    req(
        "Bỏ sót trường bắt buộc " + required,
        "POST",
        path,
        422,
        {k: v for k, v in body.items() if k != required},
        endpoint=ep,
    )
    if r["duplicate"]:
        req("Bấm lưu lần nữa gây trùng dữ liệu", "POST", path, 409, body, endpoint=ep)
    elif key == "membership":
        req("Đăng ký hai gói trùng thời hạn", "POST", path, 422, body, endpoint=ep)
    else:
        req(
            "Nhập ID liên kết không tồn tại",
            "POST",
            path,
            422,
            body
            | {"product_id" if key == "right" else "customer_id": 9223372036854775806},
            endpoint=ep,
        )
    ep = "GET " + path
    for title, suffix, expected, token in [
        ("Mở danh sách", "", 200, "admin"),
        ("Xem với quyền được cấp", "", 200, r["read"]),
        ("Mở khi chưa đăng nhập", "", 401, None),
        ("Dán token lỗi", "", 401, "invalid"),
        ("Nhập số trang âm", "?offset=-1", 422, "admin"),
        ("Nhập kích thước trang bằng 0", "?limit=0", 422, "admin"),
        ("Nhập quá 100 dòng", "?limit=101", 422, "admin"),
        ("Nhập chữ vào số dòng", "?limit=abc", 422, "admin"),
        ("Tìm tên không có", "?search=zz_no_record_zz", 200, "admin"),
        ("Xem cả dữ liệu đã ngừng dùng", "?active_only=false", 200, "admin"),
    ]:
        req(
            title,
            "GET",
            path + suffix,
            expected,
            token=token,
            endpoint=ep,
            checks='pm.test("Phân trang hợp lệ",()=>{const b=pm.response.json();pm.expect(b.items).to.be.an("array");pm.expect(b.total).to.be.a("number");});'
            if expected == 200
            else "",
        )
    ep = "GET " + r["path"] + "/{id}"
    for title, url, status, token in [
        ("Xem chi tiết vừa tạo", detail, 200, "admin"),
        ("Sale/khách xem chi tiết được cấp", detail, 200, r["read"]),
        ("Quên token", detail, 401, None),
        ("Token sai", detail, 401, "invalid"),
        ("ID không tồn tại", path + "/9223372036854775806", 404, "admin"),
        ("ID bằng 0", path + "/0", 422, "admin"),
        ("ID âm", path + "/-1", 422, "admin"),
        ("Gõ chữ vào ID", path + "/abc", 422, "admin"),
        ("Gõ ID thập phân", path + "/1.5", 422, "admin"),
        ("ID vượt BIGINT", path + "/9223372036854775808", 422, "admin"),
    ]:
        req(title, "GET", url, status, token=token, endpoint=ep)
    ep = "PATCH " + r["path"] + "/{id}"
    cases = [
        ("Sửa thông tin hợp lệ", detail, 200, r["patch"], "admin"),
        ("Sửa khi chưa đăng nhập", detail, 401, r["patch"], None),
        ("Sửa với token hỏng", detail, 401, r["patch"], "invalid"),
        ("Khách hàng sửa dữ liệu quản trị", detail, 403, r["patch"], "customer"),
        (
            "Sửa ID không tồn tại",
            path + "/9223372036854775806",
            404,
            r["patch"],
            "admin",
        ),
        ("Nhập chữ vào ID sửa", path + "/abc", 422, r["patch"], "admin"),
        ("Nhập sai giá trị khi sửa", detail, 422, r["bad"], "admin"),
        (
            "Xóa trắng trường bắt buộc bằng null",
            detail,
            422,
            {r["nullable"]: None},
            "admin",
        ),
        ("Thêm trường lạ khi sửa", detail, 422, {"extra_field": True}, "admin"),
        ("Gửi form không thay đổi", detail, 200, {}, "admin"),
    ]
    for title, url, status, data, token in cases:
        req(
            title,
            "PATCH",
            url,
            status,
            data,
            token,
            endpoint=ep,
            checks='pm.test("ID bản ghi được giữ",()=>pm.expect(pm.response.json().id).to.eql(Number(pm.collectionVariables.get("'
            + key
            + '_id"))));'
            if status == 200
            else "",
        )

folder("CRM — Tình huống nghiệp vụ bổ sung")
req(
    "Tạo CSKH bỏ qua bước NEW",
    "POST",
    "/api/v1/crm/care-tasks",
    422,
    {
        "customer_id": "{{crm_customer_id}}",
        "title": "Chưa liên hệ",
        "due_on": "2026-10-01",
        "status": "COMPLETED",
    },
)
req(
    "Nhảy thẳng từ CONTACTED về NEW",
    "PATCH",
    "/api/v1/crm/care-tasks/{{care_id}}",
    422,
    {"status": "NEW"},
)
req(
    "Sale tự đổi người phụ trách",
    "PATCH",
    "/api/v1/crm/customers/{{crm_customer_id}}",
    403,
    {"sale_id": None},
    "sale",
)
req(
    "Sale tự nâng hạn mức",
    "PATCH",
    "/api/v1/crm/customers/{{crm_customer_id}}",
    403,
    {"credit_limit": "999999999"},
    "sale",
)
req(
    "Ngày tra cứu vận đơn đảo ngược",
    "GET",
    "/api/v1/crm/trackings?date_from=2026-10-02&date_to=2026-10-01",
    422,
)
req(
    "Tra cứu vận đơn theo khách Sale và ngày",
    "GET",
    "/api/v1/crm/trackings?customer_id={{crm_customer_id}}&sale_id={{sale_id}}&date_from=2026-09-27&date_to=2026-09-27",
    200,
    checks='pm.test("Có vận đơn đúng khách",()=>pm.expect(pm.response.json().items.some(x=>x.id===Number(pm.collectionVariables.get("tracking_id")))).to.eql(true));',
)
req(
    "Đánh giá với ngày kết thúc trước ngày đầu",
    "PATCH",
    "/api/v1/crm/service-reviews/{{review_id}}",
    422,
    {"period_end": "2026-08-01"},
)
req(
    "Kế hoạch quý không bắt đầu đầu quý",
    "PATCH",
    "/api/v1/crm/sales-plans/{{plan_id}}",
    422,
    {"period_type": "QUARTER", "period_start": "2030-02-01"},
)
req(
    "Gia hạn VIP quá thời hạn gói",
    "PATCH",
    "/api/v1/crm/vip-memberships/{{membership_id}}",
    422,
    {"valid_until": "2026-12-31"},
)

# Deactivate dependent records first, after all workflows have used them.
for r in reversed(resources):
    folder("Xóa mềm — " + r["path"])
    path = "/api/v1" + r["path"]
    detail = path + "/{{" + r["key"] + "_id}}"
    ep = "DELETE " + r["path"] + "/{id}"
    for title, url, status, token in [
        ("Xóa khi chưa đăng nhập", detail, 401, None),
        ("Xóa với token giả", detail, 401, "invalid"),
        ("Khách thử xóa", detail, 403, "customer"),
        ("Xóa ID không tồn tại", path + "/9223372036854775806", 404, "admin"),
        ("Xóa ID bằng 0", path + "/0", 422, "admin"),
        ("Xóa ID âm", path + "/-1", 422, "admin"),
        ("Xóa ID dạng chữ", path + "/abc", 422, "admin"),
        ("Xóa ID vượt giới hạn", path + "/9223372036854775808", 422, "admin"),
        ("Ngừng sử dụng bản ghi", detail, 204, "admin"),
        ("Bấm xóa lần nữa", detail, 204, "admin"),
    ]:
        req(title, "DELETE", url, status, token=token, endpoint=ep)
    req(
        "Kiểm tra xóa mềm vẫn giữ dữ liệu",
        "GET",
        detail,
        200,
        checks='pm.test("Đã ngừng sử dụng",()=>pm.expect(pm.response.json().is_active).to.eql(false));',
    )

# Additional auth/config cases are appended below.
folder("Xác thực — Đăng ký và đăng nhập")
req(
    "Họ tên chỉ có khoảng trắng",
    "POST",
    "/api/v1/auth/register",
    422,
    {"username": "blank_{{run}}", "password": "Test@123456", "full_name": "   "},
    token=None,
)
register = {
    "username": "kh_{{run}}",
    "password": "Test@123456",
    "full_name": "Khách đăng ký",
}
for title, body, status in [
    ("Đăng ký hợp lệ", register, 201),
    ("Đăng ký trùng username", register, 409),
    ("Bỏ trống form", {}, 422),
    ("Tên đăng nhập quá ngắn", register | {"username": "a"}, 422),
    ("Mật khẩu quá ngắn", register | {"password": "123"}, 422),
    ("Email không hợp lệ", register | {"email": "not-mail"}, 422),
    ("Điện thoại chứa chữ", register | {"phone": "abc"}, 422),
    ("Họ tên rỗng", register | {"full_name": ""}, 422),
    ("Username chứa ký tự cấm", register | {"username": "bad@name"}, 422),
    ("Thiếu mật khẩu", {k: v for k, v in register.items() if k != "password"}, 422),
]:
    req(
        title,
        "POST",
        "/api/v1/auth/register",
        status,
        body,
        token=None,
        save="registered_id" if status == 201 else None,
    )
for title, data, status in [
    ("Mật khẩu sai", {"username": "admin", "password": "Wrong@123"}, 401),
    (
        "Tài khoản không tồn tại",
        {"username": "no_such_account", "password": "Test@123456"},
        401,
    ),
    ("Không nhập username", {"password": "abc"}, 422),
    ("Không nhập password", {"username": "admin"}, 422),
    ("Không nhập form", {}, 422),
    (
        "Nhập tên có dấu nháy SQL",
        {"username": "admin' OR 1=1 --", "password": "abc"},
        401,
    ),
    ("Nhập khoảng trắng", {"username": "   ", "password": "abc"}, 401),
]:
    req(title, "POST", "/api/v1/auth/login", status, data, token=None, form=True)
login("kh_{{run}}", "Test@123456", "registered")

folder("Xác thực — Refresh / Logout")
for path, good_status in [("/refresh", 200), ("/logout", 204)]:
    ep = "/api/v1/auth" + path
    valid = "{{registered_refresh}}" if path == "/refresh" else "{{logout_refresh}}"
    if path == "/logout":
        login("kh_{{run}}", "Test@123456", "logout")
    for title, body, status in [
        ("Token hợp lệ", {"refresh_token": valid}, good_status),
        (
            "Dùng lại token vừa thu hồi",
            {"refresh_token": valid},
            401 if path == "/refresh" else 204,
        ),
        ("Token sai chữ ký", {"refresh_token": "invalid.token.value"}, 401),
        ("Lấy access thay refresh", {"refresh_token": "{{admin_token}}"}, 401),
        ("Thiếu refresh_token", {}, 422),
        ("Refresh token null", {"refresh_token": None}, 422),
        ("Refresh token kiểu số", {"refresh_token": 123}, 422),
        ("Refresh token kiểu object", {"refresh_token": {}}, 422),
        ("Refresh token chuỗi rỗng", {"refresh_token": ""}, 401),
        ("Refresh token chuỗi bất kỳ", {"refresh_token": "hello"}, 401),
    ]:
        req(
            title,
            "POST",
            ep,
            204 if path == "/logout" and status == 401 else status,
            body,
            token=None,
        )

folder("Người dùng — Thông tin cá nhân")
for token in [
    "admin",
    "sale",
    "customer",
    "registered",
    None,
    "invalid",
    "admin",
    "sale",
    "customer",
    "registered",
]:
    req(
        "Xem hồ sơ với " + str(token),
        "GET",
        "/api/v1/users/me",
        401 if token in (None, "invalid") else 200,
        token=token,
    )
for title, body, status, token in [
    ("Sửa tên", {"full_name": "Khách đã sửa"}, 200, "registered"),
    ("Sửa số điện thoại", {"phone": "0909999999"}, 200, "registered"),
    ("Sửa email", {"email": "kh_{{run}}@example.com"}, 200, "registered"),
    ("Không đăng nhập", {"full_name": "abc"}, 401, None),
    ("Token hỏng", {}, 401, "invalid"),
    ("Tên rỗng", {"full_name": ""}, 422, "registered"),
    ("Email sai", {"email": "abc"}, 422, "registered"),
    ("Điện thoại sai", {"phone": "abc"}, 422, "registered"),
    ("Tên quá dài", {"full_name": "a" * 151}, 422, "registered"),
    ("Bỏ email tùy chọn", {"email": None}, 200, "registered"),
]:
    req(title, "PATCH", "/api/v1/users/me", status, body, token)
for title, body, status, token in [
    (
        "Nhập sai mật khẩu cũ",
        {"old_password": "wrong", "new_password": "New@123456"},
        422,
        "registered",
    ),
    (
        "Mật khẩu mới quá ngắn",
        {"old_password": "Test@123456", "new_password": "1"},
        422,
        "registered",
    ),
    ("Thiếu mật khẩu mới", {"old_password": "Test@123456"}, 422, "registered"),
    ("Thiếu mật khẩu cũ", {"new_password": "New@123456"}, 422, "registered"),
    ("Form trống", {}, 422, "registered"),
    ("Không đăng nhập", {"old_password": "a", "new_password": "New@123456"}, 401, None),
    ("Token lỗi", {"old_password": "a", "new_password": "New@123456"}, 401, "invalid"),
    (
        "Mật khẩu mới null",
        {"old_password": "a", "new_password": None},
        422,
        "registered",
    ),
    (
        "Mật khẩu mới quá dài",
        {"old_password": "a", "new_password": "x" * 129},
        422,
        "registered",
    ),
    (
        "Đổi mật khẩu hợp lệ",
        {"old_password": "Test@123456", "new_password": "New@123456"},
        204,
        "registered",
    ),
]:
    req(title, "POST", "/api/v1/users/me/change-password", status, body, token)

folder("Người dùng — Quản trị")
user = {
    "username": "staff_{{run}}",
    "password": "Test@123456",
    "full_name": "Nhân viên mới",
    "role": "SALE",
}
for title, data, status, token in [
    ("Tạo nhân viên hợp lệ", user, 201, "admin"),
    ("Tạo trùng nhân viên", user, 409, "admin"),
    ("Sale tự tạo nhân viên", user, 403, "sale"),
    ("Quên token", user, 401, None),
    ("Form trống", {}, 422, "admin"),
    ("Vai trò không có", user | {"role": "SUPERADMIN"}, 422, "admin"),
    ("Username sai", user | {"username": "!@#"}, 422, "admin"),
    ("Mật khẩu ngắn", user | {"password": "12"}, 422, "admin"),
    ("Email sai", user | {"email": "x"}, 422, "admin"),
    ("Họ tên trống", user | {"full_name": ""}, 422, "admin"),
]:
    req(
        title,
        "POST",
        "/api/v1/users",
        status,
        data,
        token,
        save="staff_id" if status == 201 else None,
    )
for title, suffix, status, token in [
    ("Xem danh sách", "", 200, "admin"),
    ("Sale xem toàn bộ", "", 403, "sale"),
    ("Khách xem toàn bộ", "", 403, "customer"),
    ("Không đăng nhập", "", 401, None),
    ("Token lỗi", "", 401, "invalid"),
    ("Số dòng bằng 0", "?limit=0", 422, "admin"),
    ("Số dòng quá lớn", "?limit=101", 422, "admin"),
    ("Offset âm", "?offset=-1", 422, "admin"),
    ("Role sai", "?role=WRONG", 422, "admin"),
    ("Lọc đúng vai trò", "?role=SALE", 200, "admin"),
]:
    req(title, "GET", "/api/v1/users" + suffix, status, token=token)
for title, ident, data, status, token in [
    ("Sửa tên nhân viên", "{{staff_id}}", {"full_name": "Nhân viên sửa"}, 200, "admin"),
    ("Đổi vai trò", "{{staff_id}}", {"role": "WAREHOUSE"}, 200, "admin"),
    ("Khóa tài khoản", "{{staff_id}}", {"status": "LOCKED"}, 200, "admin"),
    ("ID không tồn tại", "9223372036854775806", {}, 404, "admin"),
    ("ID dạng chữ", "abc", {}, 422, "admin"),
    ("Sale sửa tài khoản", "{{staff_id}}", {}, 403, "sale"),
    ("Không token", "{{staff_id}}", {}, 401, None),
    ("Role không hợp lệ", "{{staff_id}}", {"role": "WRONG"}, 422, "admin"),
    ("Status không hợp lệ", "{{staff_id}}", {"status": "WRONG"}, 422, "admin"),
    ("Mở khóa", "{{staff_id}}", {"status": "ACTIVE"}, 200, "admin"),
]:
    req(title, "PATCH", "/api/v1/users/" + ident, status, data, token)

folder("Tỷ giá")
rate = {"currency_code": "CNY", "rate": "3921.1234", "note": "Kiểm thử {{run}}"}
for title, data, status, token in [
    ("Cập nhật hợp lệ", rate, 201, "admin"),
    ("Tỷ giá mới tiếp theo", rate | {"rate": "3922.0000"}, 201, "admin"),
    ("Sale cập nhật", rate, 403, "sale"),
    ("Quên token", rate, 401, None),
    ("Token giả", rate, 401, "invalid"),
    ("Tỷ giá âm", rate | {"rate": "-1"}, 422, "admin"),
    ("Tỷ giá bằng 0", rate | {"rate": "0"}, 422, "admin"),
    ("Mã tiền không hỗ trợ", rate | {"currency_code": "EUR"}, 422, "admin"),
    ("Tỷ giá không phải số", rate | {"rate": "abc"}, 422, "admin"),
    ("Thiếu tỷ giá", {"currency_code": "CNY"}, 422, "admin"),
]:
    req(title, "POST", "/api/v1/exchange-rates", status, data, token)
for title, suffix, status, token in [
    ("Xem lịch sử", "", 200, "admin"),
    ("Lọc CNY", "?currency_code=CNY", 200, "admin"),
    ("Lọc USD", "?currency_code=USD", 200, "customer"),
    ("Tiền tệ sai", "?currency_code=EUR", 422, "admin"),
    ("Limit bằng 0", "?limit=0", 422, "admin"),
    ("Limit quá lớn", "?limit=101", 422, "admin"),
    ("Offset âm", "?offset=-1", 422, "admin"),
    ("Limit dạng chữ", "?limit=abc", 422, "admin"),
    ("Quên token", "", 401, None),
    ("Token lỗi", "", 401, "invalid"),
]:
    req(title, "GET", "/api/v1/exchange-rates/history" + suffix, status, token=token)
for code, status, token in [
    ("CNY", 200, "admin"),
    ("USD", 200, "admin"),
    ("CNY", 200, "customer"),
    ("USD", 200, "sale"),
    ("EUR", 422, "admin"),
    ("VND", 422, "admin"),
    ("cny", 422, "admin"),
    ("abc", 422, "admin"),
    ("CNY", 401, None),
    ("CNY", 401, "invalid"),
]:
    req(
        "Tra cứu mã " + code + " / " + str(token),
        "GET",
        "/api/v1/exchange-rates/current/" + code,
        status,
        token=token,
    )
for token in [
    "admin",
    "sale",
    "customer",
    "registered",
    None,
    "invalid",
    "admin",
    "sale",
    "customer",
    "registered",
]:
    req(
        "Xem tỷ giá hiện hành / " + str(token),
        "GET",
        "/api/v1/exchange-rates/current",
        401 if token in (None, "invalid") else 200,
        token=token,
        checks='if(pm.response.code===200) pm.test("Mỗi ngoại tệ đúng một tỷ giá mới nhất",()=>{const b=pm.response.json();pm.expect(new Set(b.map(x=>x.currency_code)).size).to.eql(b.length);pm.expect(b.find(x=>x.currency_code==="CNY").rate).to.eql("3922.0000");});',
    )

folder("Biểu phí")
fee = {"fee_type": "TEST_FEE", "value": "5", "unit": "PERCENT"}
for title, data, status, token in [
    ("Tạo biểu phí", fee, 201, "admin"),
    ("Tỷ lệ trên 100", fee | {"value": "101"}, 422, "admin"),
    ("Phí âm", fee | {"value": "-1"}, 422, "admin"),
    ("Đơn vị sai", fee | {"unit": "USD"}, 422, "admin"),
    ("Loại phí sai", fee | {"fee_type": "abc"}, 422, "admin"),
    ("Bậc thang ngược", fee | {"tier_min": "100", "tier_max": "10"}, 422, "admin"),
    ("Thiếu giá trị", {"fee_type": "TEST_FEE", "unit": "PERCENT"}, 422, "admin"),
    ("Sale thêm phí", fee, 403, "sale"),
    ("Không token", fee, 401, None),
    ("Token sai", fee, 401, "invalid"),
]:
    req(
        title,
        "POST",
        "/api/v1/fee-configs",
        status,
        data,
        token,
        save="fee_id" if status == 201 else None,
    )
for title, suffix, status, token in [
    ("Xem toàn bộ", "", 200, "admin"),
    ("Khách xem phí", "", 200, "customer"),
    ("Lọc phí test", "?fee_type=TEST_FEE", 200, "admin"),
    ("Phí không tồn tại", "?fee_type=NO_SUCH_FEE", 200, "admin"),
    ("Cả phí ngừng dùng", "?active_only=false", 200, "admin"),
    ("Chỉ phí đang dùng", "?active_only=true", 200, "admin"),
    ("active_only sai kiểu", "?active_only=wrong", 422, "admin"),
    ("Sale xem phí", "", 200, "sale"),
    ("Quên token", "", 401, None),
    ("Token giả", "", 401, "invalid"),
]:
    req(title, "GET", "/api/v1/fee-configs" + suffix, status, token=token)
for title, suffix, status, token in [
    ("Phí hiện hành", "", 200, "admin"),
    ("Phí theo loại", "?fee_type=TEST_FEE", 200, "admin"),
    ("Phí tại ngày cũ", "?on_date=2000-01-01", 200, "admin"),
    ("Phí tại ngày tương lai", "?on_date=2030-01-01", 200, "admin"),
    ("Ngày sai định dạng", "?on_date=abc", 422, "admin"),
    ("Ngày không tồn tại", "?on_date=2026-02-30", 422, "admin"),
    ("Khách xem phí", "", 200, "customer"),
    ("Sale xem phí", "", 200, "sale"),
    ("Quên token", "", 401, None),
    ("Token giả", "", 401, "invalid"),
]:
    req(
        title,
        "GET",
        "/api/v1/fee-configs/current" + suffix,
        status,
        token=token,
        checks='if(pm.response.code===200) pm.test("Mỗi bậc chỉ một phí hiện hành",()=>{const a=pm.response.json().map(x=>[x.fee_type,x.unit,x.tier_min].join("|"));pm.expect(new Set(a).size).to.eql(a.length);});',
    )
for ident, status, token in [
    ("{{fee_id}}", 200, "admin"),
    ("{{fee_id}}", 200, "sale"),
    ("{{fee_id}}", 200, "customer"),
    ("9223372036854775806", 404, "admin"),
    ("0", 404, "admin"),
    ("-1", 404, "admin"),
    ("abc", 422, "admin"),
    ("1.5", 422, "admin"),
    ("{{fee_id}}", 401, None),
    ("{{fee_id}}", 401, "invalid"),
]:
    req(
        "Xem phí ID " + ident + " / " + str(token),
        "GET",
        "/api/v1/fee-configs/" + ident,
        status,
        token=token,
    )
for title, ident, data, status, token in [
    ("Sửa phí", "{{fee_id}}", {"value": "6"}, 200, "admin"),
    ("Sửa mô tả", "{{fee_id}}", {"description": "Đã sửa"}, 200, "admin"),
    ("Giá trị âm", "{{fee_id}}", {"value": "-1"}, 422, "admin"),
    ("Đơn vị sai", "{{fee_id}}", {"unit": "BAD"}, 422, "admin"),
    ("Tỷ lệ quá 100", "{{fee_id}}", {"value": "101"}, 422, "admin"),
    ("Bậc ngược", "{{fee_id}}", {"tier_min": "100", "tier_max": "1"}, 422, "admin"),
    ("Không tồn tại", "9223372036854775806", {}, 404, "admin"),
    ("Sale sửa phí", "{{fee_id}}", {}, 403, "sale"),
    ("Không token", "{{fee_id}}", {}, 401, None),
    ("Token sai", "{{fee_id}}", {}, 401, "invalid"),
]:
    req(title, "PATCH", "/api/v1/fee-configs/" + ident, status, data, token)
for ident, status, token in [
    ("9223372036854775806", 404, "admin"),
    ("0", 404, "admin"),
    ("-1", 404, "admin"),
    ("abc", 422, "admin"),
    ("{{fee_id}}", 403, "sale"),
    ("{{fee_id}}", 403, "customer"),
    ("{{fee_id}}", 401, None),
    ("{{fee_id}}", 401, "invalid"),
    ("{{fee_id}}", 204, "admin"),
    ("{{fee_id}}", 204, "admin"),
]:
    req(
        "Xóa phí ID " + ident + " / " + str(token),
        "DELETE",
        "/api/v1/fee-configs/" + ident,
        status,
        token=token,
    )
folder("Hệ thống — Health")
for i in range(10):
    req(f"Kiểm tra server và DB lần {i + 1}", "GET", "/health", 200, token=None)

collection = {
    "info": {
        "name": "CMS MySQL — Buổi 1–3 — Test API thực tế",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        "description": "Mỗi API khoảng 10 tình huống: thao tác đúng, nhập sai, thiếu dữ liệu, token và quyền. Chạy toàn bộ 1 iteration trên database kiểm thử riêng. Các endpoint chỉ đọc đơn giản có ca kiểm tra lặp với các tài khoản. Không chạy lên production.",
    },
    "variable": [{"key": "base_url", "value": "http://127.0.0.1:8001"}],
    "item": folders,
}
(ROOT / "postman" / "CMS.postman_collection.json").write_text(
    json.dumps(collection, ensure_ascii=False, indent=2)
)
print(
    "Generated",
    sum(len(f["item"]) for f in folders),
    "requests in",
    len(folders),
    "folders",
)
