"""Smoke test end-to-end cho Buổi 1. Chạy khi server đang chạy:

    python scripts/smoke_test.py                     # mặc định http://localhost:8000
    python scripts/smoke_test.py http://localhost:8000

Cần đã chạy đủ 3 file SQL (có tài khoản dev). Script tự tạo user ngẫu nhiên nên chạy lại nhiều lần được.
"""
import sys
import uuid

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
API = f"{BASE}/api/v1"
client = httpx.Client(timeout=15)

passed = failed = 0


def check(name: str, cond: bool, extra: str = "") -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name}  {extra}")


def login(username: str, password: str) -> httpx.Response:
    return client.post(f"{API}/auth/login", data={"username": username, "password": password})


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def tokens_of(username: str, password: str) -> dict:
    r = login(username, password)
    assert r.status_code == 200, f"login {username} lỗi: {r.status_code} {r.text}"
    return r.json()


suffix = uuid.uuid4().hex[:8]

print("\n[1] Health + kết nối DB async")
r = client.get(f"{BASE}/health")
check("GET /health = 200, database ok", r.status_code == 200 and r.json().get("database") == "ok", r.text)

print("\n[2] Đăng nhập / JWT")
check("sai mật khẩu -> 401", login("admin", "sai-mat-khau").status_code == 401)
check("user không tồn tại -> 401", login("khong_ton_tai", "Admin@123456").status_code == 401)
admin = tokens_of("admin", "Admin@123456")
check("login admin trả access + refresh token", bool(admin["access_token"]) and bool(admin["refresh_token"]))
me = client.get(f"{API}/users/me", headers=auth(admin["access_token"])).json()
check("/users/me trả role ADMIN", me.get("role") == "ADMIN", str(me))
check("/users/me KHÔNG lộ password_hash", "password_hash" not in me)
check("không có token -> 401", client.get(f"{API}/users/me").status_code == 401)
check("token rác -> 401", client.get(f"{API}/users/me", headers=auth("abc.def.ghi")).status_code == 401)
check(
    "dùng refresh token làm access token -> 401",
    client.get(f"{API}/users/me", headers=auth(admin["refresh_token"])).status_code == 401,
)

print("\n[3] Refresh token rotation + logout")
r = client.post(f"{API}/auth/refresh", json={"refresh_token": admin["refresh_token"]})
check("refresh lần 1 -> 200", r.status_code == 200, r.text)
new_pair = r.json()
check(
    "dùng lại refresh token cũ -> 401 (đã bị thu hồi)",
    client.post(f"{API}/auth/refresh", json={"refresh_token": admin["refresh_token"]}).status_code == 401,
)
check(
    "dùng access token làm refresh -> 401",
    client.post(f"{API}/auth/refresh", json={"refresh_token": new_pair["access_token"]}).status_code == 401,
)
r = client.post(f"{API}/auth/logout", json={"refresh_token": new_pair["refresh_token"]})
check("logout -> 204", r.status_code == 204)
check(
    "refresh sau logout -> 401",
    client.post(f"{API}/auth/refresh", json={"refresh_token": new_pair["refresh_token"]}).status_code == 401,
)

print("\n[4] Đăng ký khách hàng + validate")
uname = f"khach_{suffix}"
body = {"username": uname, "password": "MatKhau123", "full_name": "Khách Test", "email": f"{uname}@example.com"}
r = client.post(f"{API}/auth/register", json=body)
check("đăng ký -> 201, role CUSTOMER", r.status_code == 201 and r.json().get("role") == "CUSTOMER", r.text)
check("trùng username -> 409", client.post(f"{API}/auth/register", json=body).status_code == 409)
body2 = {**body, "username": f"khac_{suffix}"}
check("trùng email -> 409", client.post(f"{API}/auth/register", json=body2).status_code == 409)
check("mật khẩu ngắn -> 422", client.post(f"{API}/auth/register", json={**body, "username": f"x_{suffix}", "email": None, "password": "123"}).status_code == 422)
check("username có ký tự lạ -> 422", client.post(f"{API}/auth/register", json={**body, "username": "a b!", "email": None}).status_code == 422)
check("username hoa/thường đều login được", login(uname.upper(), "MatKhau123").status_code == 200)
customer = tokens_of(uname, "MatKhau123")
check("register không cho tự chọn role (bỏ qua field role)", client.post(f"{API}/auth/register", json={**body, "username": f"y_{suffix}", "email": None, "role": "ADMIN"}).json().get("role") == "CUSTOMER")

print("\n[5] Phân quyền RBAC")
sale = tokens_of("sale01", "Test@123456")
kho = tokens_of("kho01", "Test@123456")
check("CUSTOMER xem danh sách user -> 403", client.get(f"{API}/users", headers=auth(customer["access_token"])).status_code == 403)
check("SALE xem danh sách user -> 403", client.get(f"{API}/users", headers=auth(sale["access_token"])).status_code == 403)
r = client.get(f"{API}/users", headers=auth(admin_tok := tokens_of("admin", "Admin@123456")["access_token"]))
check("ADMIN xem danh sách user -> 200 có total", r.status_code == 200 and r.json()["total"] >= 6, r.text)
r = client.get(f"{API}/users", params={"role": "WAREHOUSE"}, headers=auth(admin_tok))
check("lọc theo role WAREHOUSE", r.status_code == 200 and all(u["role"] == "WAREHOUSE" for u in r.json()["items"]) and r.json()["total"] >= 1, r.text)
r = client.get(f"{API}/users", params={"search": "sale01"}, headers=auth(admin_tok))
check("tìm kiếm theo từ khóa", r.status_code == 200 and r.json()["total"] == 1, r.text)

print("\n[6] Admin tạo nhân viên / đổi vai trò / khóa tài khoản")
staff_name = f"nv_{suffix}"
r = client.post(f"{API}/users", headers=auth(admin_tok), json={"username": staff_name, "password": "NhanVien123", "full_name": "NV Test", "role": "WAREHOUSE"})
check("admin tạo user role WAREHOUSE -> 201", r.status_code == 201 and r.json()["role"] == "WAREHOUSE", r.text)
staff_id = r.json()["id"]
check("customer tạo user -> 403", client.post(f"{API}/users", headers=auth(customer["access_token"]), json={"username": f"z_{suffix}", "password": "NhanVien123", "full_name": "Z", "role": "ADMIN"}).status_code == 403)
r = client.patch(f"{API}/users/{staff_id}", headers=auth(admin_tok), json={"role": "SALE"})
check("admin đổi role -> SALE", r.status_code == 200 and r.json()["role"] == "SALE", r.text)
my_id = client.get(f"{API}/users/me", headers=auth(admin_tok)).json()["id"]
r = client.patch(f"{API}/users/{my_id}", headers=auth(admin_tok), json={"status": "LOCKED"})
check("admin tự khóa chính mình -> 422 (chống tự khóa)", r.status_code == 422, r.text)
staff = tokens_of(staff_name, "NhanVien123")
r = client.patch(f"{API}/users/{staff_id}", headers=auth(admin_tok), json={"status": "LOCKED"})
check("admin khóa nhân viên -> 200", r.status_code == 200 and r.json()["status"] == "LOCKED", r.text)
check("user bị khóa: access token cũ bị từ chối ngay -> 401", client.get(f"{API}/users/me", headers=auth(staff["access_token"])).status_code == 401)
check("user bị khóa: refresh -> 401", client.post(f"{API}/auth/refresh", json={"refresh_token": staff["refresh_token"]}).status_code == 401)
check("user bị khóa: login -> 401", login(staff_name, "NhanVien123").status_code == 401)
check("admin mở khóa", client.patch(f"{API}/users/{staff_id}", headers=auth(admin_tok), json={"status": "ACTIVE"}).status_code == 200)
check("mở khóa xong login lại được", login(staff_name, "NhanVien123").status_code == 200)

print("\n[7] Thông tin cá nhân + đổi mật khẩu")
r = client.patch(f"{API}/users/me", headers=auth(customer["access_token"]), json={"full_name": "Tên Mới", "phone": "0912345678"})
check("sửa họ tên + sđt -> 200", r.status_code == 200 and r.json()["full_name"] == "Tên Mới" and r.json()["phone"] == "0912345678", r.text)
r = client.patch(f"{API}/users/me", headers=auth(customer["access_token"]), json={"role": "ADMIN"})
check("tự sửa role qua /me -> role vẫn là CUSTOMER", client.get(f"{API}/users/me", headers=auth(customer["access_token"])).json()["role"] == "CUSTOMER")
r = client.post(f"{API}/users/me/change-password", headers=auth(customer["access_token"]), json={"old_password": "SaiRoi12345", "new_password": "MatKhauMoi123"})
check("đổi mật khẩu với mật khẩu cũ sai -> 422", r.status_code == 422, r.text)
r = client.post(f"{API}/users/me/change-password", headers=auth(customer["access_token"]), json={"old_password": "MatKhau123", "new_password": "MatKhauMoi123"})
check("đổi mật khẩu đúng -> 204", r.status_code == 204, r.text)
check("refresh token cũ bị thu hồi sau đổi mật khẩu", client.post(f"{API}/auth/refresh", json={"refresh_token": customer["refresh_token"]}).status_code == 401)
check("mật khẩu cũ không login được", login(uname, "MatKhau123").status_code == 401)
check("mật khẩu mới login được", login(uname, "MatKhauMoi123").status_code == 200)
customer = tokens_of(uname, "MatKhauMoi123")

print("\n[8] Tỷ giá (REQ-1.2, 1.3)")
r = client.get(f"{API}/exchange-rates/current", headers=auth(customer["access_token"]))
codes = {x["currency_code"] for x in r.json()} if r.status_code == 200 else set()
check("customer xem tỷ giá hiện hành: có CNY + USD", codes == {"CNY", "USD"}, r.text)
check("không token xem tỷ giá -> 401", client.get(f"{API}/exchange-rates/current").status_code == 401)
r = client.post(f"{API}/exchange-rates", headers=auth(sale["access_token"]), json={"currency_code": "CNY", "rate": "3950"})
check("SALE cập nhật tỷ giá -> 403", r.status_code == 403)
r = client.post(f"{API}/exchange-rates", headers=auth(admin_tok), json={"currency_code": "CNY", "rate": "3955.5", "note": "smoke test"})
check("ADMIN cập nhật tỷ giá CNY -> 201", r.status_code == 201 and r.json()["rate"].startswith("3955.5"), r.text)
r = client.get(f"{API}/exchange-rates/current/CNY", headers=auth(sale["access_token"]))
check("tỷ giá hiện hành CNY = giá vừa đặt", r.status_code == 200 and float(r.json()["rate"]) == 3955.5, r.text)
r = client.get(f"{API}/exchange-rates/current", headers=auth(sale["access_token"]))
cur = {x["currency_code"]: float(x["rate"]) for x in r.json()}
check("USD giữ nguyên 26500", cur.get("USD") == 26500.0, str(cur))
r = client.get(f"{API}/exchange-rates/history", params={"currency_code": "CNY"}, headers=auth(sale["access_token"]))
check("lịch sử CNY có >= 2 dòng (giá seed + giá mới), mới nhất trước", r.status_code == 200 and r.json()["total"] >= 2 and float(r.json()["items"][0]["rate"]) == 3955.5, r.text)
check("rate = 0 -> 422", client.post(f"{API}/exchange-rates", headers=auth(admin_tok), json={"currency_code": "CNY", "rate": 0}).status_code == 422)
check("rate âm -> 422", client.post(f"{API}/exchange-rates", headers=auth(admin_tok), json={"currency_code": "CNY", "rate": -5}).status_code == 422)
check("mã tiền lạ -> 422", client.post(f"{API}/exchange-rates", headers=auth(admin_tok), json={"currency_code": "EUR", "rate": 100}).status_code == 422)
client.post(f"{API}/exchange-rates", headers=auth(admin_tok), json={"currency_code": "CNY", "rate": 3920, "note": "khôi phục sau smoke test"})

print("\n[9] Thang bảng phí (REQ-9.1)")
r = client.get(f"{API}/fee-configs/current", headers=auth(customer["access_token"]))
fees = r.json() if r.status_code == 200 else []
types = {f["fee_type"] for f in fees}
check("customer xem biểu phí đang áp dụng", r.status_code == 200 and len(fees) >= 9, r.text)
check("đủ 4 loại phí", {"PURCHASE_SERVICE_FEE", "INTL_SHIPPING_FEE", "INSPECTION_FEE", "WOODEN_CRATE_FEE"} <= types, str(types))
r = client.get(f"{API}/fee-configs/current", params={"fee_type": "PURCHASE_SERVICE_FEE"}, headers=auth(sale["access_token"]))
check("lọc theo fee_type: 3 bậc phí mua hàng", r.status_code == 200 and len(r.json()) == 3, r.text)
new_fee = {"fee_type": f"TEST_FEE_{suffix.upper()}", "description": "phí test", "value": "5", "unit": "PERCENT"}
check("SALE tạo phí -> 403", client.post(f"{API}/fee-configs", headers=auth(sale["access_token"]), json=new_fee).status_code == 403)
r = client.post(f"{API}/fee-configs", headers=auth(admin_tok), json=new_fee)
check("ADMIN tạo loại phí MỚI (không sửa code) -> 201", r.status_code == 201 and r.json()["is_active"] is True, r.text)
fee_id = r.json()["id"]
check("PERCENT > 100 -> 422", client.post(f"{API}/fee-configs", headers=auth(admin_tok), json={**new_fee, "value": "150"}).status_code == 422)
check("tier_max <= tier_min -> 422", client.post(f"{API}/fee-configs", headers=auth(admin_tok), json={**new_fee, "unit": "VND_PER_KG", "tier_min": 10, "tier_max": 5}).status_code == 422)
check("fee_type viết thường -> 422", client.post(f"{API}/fee-configs", headers=auth(admin_tok), json={**new_fee, "fee_type": "abc"}).status_code == 422)
check("unit lạ -> 422", client.post(f"{API}/fee-configs", headers=auth(admin_tok), json={**new_fee, "unit": "BANANA"}).status_code == 422)
r = client.patch(f"{API}/fee-configs/{fee_id}", headers=auth(admin_tok), json={"value": "7.5"})
check("ADMIN sửa giá trị phí -> 200", r.status_code == 200 and float(r.json()["value"]) == 7.5, r.text)
r = client.patch(f"{API}/fee-configs/{fee_id}", headers=auth(admin_tok), json={"tier_min": 100, "tier_max": 50})
check("sửa thành tier sai -> 422", r.status_code == 422, r.text)
check("phí không tồn tại -> 404", client.get(f"{API}/fee-configs/99999999", headers=auth(admin_tok)).status_code == 404)
# Hiệu lực theo ngày: bản mới có effective_date muộn hơn thay thế bản cũ, bản cũ vẫn giữ làm lịch sử
r = client.post(f"{API}/fee-configs", headers=auth(admin_tok), json={**new_fee, "value": "9", "effective_date": "2099-01-01"})
future_id = r.json()["id"]
r = client.get(f"{API}/fee-configs/current", params={"fee_type": new_fee["fee_type"]}, headers=auth(admin_tok))
check("bản có hiệu lực tương lai chưa được áp dụng hôm nay", [f["id"] for f in r.json()] == [fee_id], r.text)
r = client.get(f"{API}/fee-configs/current", params={"fee_type": new_fee["fee_type"], "on_date": "2099-06-01"}, headers=auth(admin_tok))
check("tra cứu ngày 2099-06-01 thì lấy bản mới (9)", [float(f["value"]) for f in r.json()] == [9.0], r.text)
check("ADMIN ngừng áp dụng (xóa mềm) -> 204", client.delete(f"{API}/fee-configs/{fee_id}", headers=auth(admin_tok)).status_code == 204)
r = client.get(f"{API}/fee-configs/current", params={"fee_type": new_fee["fee_type"]}, headers=auth(admin_tok))
check("phí đã ngừng không còn trong biểu phí hiện hành", r.json() == [], r.text)
client.delete(f"{API}/fee-configs/{future_id}", headers=auth(admin_tok))

print(f"\n{'=' * 50}\nKẾT QUẢ: {passed} đạt, {failed} lỗi\n{'=' * 50}")
sys.exit(1 if failed else 0)
