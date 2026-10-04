# API Buổi 1 — qua Gateway

Base URL: `http://127.0.0.1:8000`. Backend nội bộ ở cổng 8001. Các API nghiệp vụ dùng stored procedure tại `sql/`; không ghép SQL từ dữ liệu client.

## Đăng ký, đăng nhập và phiên

| API | Body JSON / kết quả |
|---|---|
| POST /auth/register | username, password (8–128 ký tự), full_name, email/phone tùy chọn; 201, luôn CUSTOMER |
| POST /auth/login | username, password; trả access_token + refresh_token |
| POST /auth/refresh | refresh_token; xoay cả hai token; token cũ chỉ dùng một lần |
| POST /auth/logout | refresh_token; 204, thu hồi refresh token |
| GET /auth/me | Bearer access token; tài khoản hiện tại |
| GET /auth/permissions | Vai trò và các quyền hiện tại |

Đăng ký không cho truyền role/status. Username/email trùng trả 409. Sai mật khẩu/token trả 401. Tài khoản bị khóa trả 403. Logout không thu hồi ngay access token đã phát; access hết hạn theo cấu hình, còn trạng thái tài khoản được đọc lại từ DB mỗi request.

## RBAC

Năm vai trò: ADMIN (quản trị), SALE, WAREHOUSE (kho), ACCOUNTANT (kế toán), CUSTOMER (khách hàng).

| Chức năng | ADMIN | SALE / WAREHOUSE / ACCOUNTANT / CUSTOMER |
|---|---|---|
| Đọc tài khoản của mình | Có | Có |
| Xem danh sách người dùng | Có | Không |
| Đổi vai trò / khóa tài khoản | Có | Không |
| Tra cứu tỷ giá và bảng phí | Có | Có |
| Cập nhật tỷ giá và bảng phí | Có | Không |

- `GET /users?limit=10&offset=0`: limit 1–100, offset không âm.
- `PATCH /users/{id}/access`: JSON `{"role":"SALE"}` hoặc `{"status":"LOCKED"}` (có thể truyền cả hai).
- Trạng thái: ACTIVE, INACTIVE, LOCKED. Đổi vai trò/trạng thái thu hồi refresh token cũ.
- Không cho vô hiệu hóa/hạ quyền ADMIN đang hoạt động cuối cùng (409).
- Quyền lấy từ DB hiện tại, không tin header client hoặc role cũ trong JWT.

Gateway mặc định bảo vệ API mới. Chỉ auth/register, auth/login, auth/refresh, auth/logout (POST), health (GET) công khai; backend vẫn yêu cầu khóa gateway.

## Áp dụng SQL

Database mới: chạy `sql/my_db_logistic.sql`. Database hiện có: giữ nguyên bảng/dữ liệu. Chạy các file thủ tục theo thứ tự `05_procedures.sql`, `06_auth_sessions.sql`, `07_rbac.sql`.

Test trên DB tạm: xem `BE/checks/README.md`. Không dùng kết quả test cũ CRM/catalog để kết luận chức năng logistics hiện tại.

## Tỷ giá ngoại tệ

Chạy `sql/08_exchange_rates.sql` sau các file trên. Quy ước `rate` = số VNĐ cho 1 đơn vị ngoại tệ; NDT được chuẩn hóa thành mã CNY. Đây là tỷ giá Admin nhập thủ công, chưa kết nối ngân hàng.

- `POST /exchange-rates` (ADMIN): `{"currency_code":"CNY","rate":"3920.1234","note":"Tỷ giá ngày mới"}`. Mỗi lần tạo là một bản ghi lịch sử; không ghi đè tỷ giá cũ.
- `GET /exchange-rates/current`: tỷ giá mới nhất của các ngoại tệ đã cấu hình.
- `GET /exchange-rates/current/CNY` hoặc `/NDT`, `/USD`: tỷ giá mới nhất; chưa cấu hình trả 404.
- `GET /exchange-rates/history?currency_code=CNY&limit=20&offset=0`: lịch sử giảm dần; hỗ trợ `date_from`, `date_to` dạng ISO-8601 có múi giờ, ví dụ `2026-10-01T00:00:00Z` (bao gồm hai mốc).

Tỷ giá phải dương, tối đa 4 chữ số thập phân; JSON trả tiền dạng chuỗi để giữ độ chính xác. Timestamps trả UTC. Tất cả vai trò đang hoạt động được đọc.

## Thang bảng phí dịch vụ

Chạy `sql/09_fee_configs.sql` sau file `08`. Hai bảng mới: `fee_configs` lưu phiên bản biểu phí; `fee_tiers` lưu các bậc của từng phiên bản.

`POST /fee-configs` (ADMIN), ví dụ:

```json
{
  "fee_type": "INTERNATIONAL_SHIPPING",
  "description": "Phí vận chuyển quốc tế theo kg",
  "unit": "VND_PER_KG",
  "effective_date": "2026-10-05",
  "tiers": [
    {"tier_min":"0", "tier_max":"10", "value":"30000"},
    {"tier_min":"10", "tier_max":null, "value":"25000"}
  ]
}
```

Bậc dùng khoảng `[tier_min, tier_max)`: 10 kg thuộc bậc thứ hai. `null` nghĩa là không có giới hạn trên. Bậc không được chồng lấn, có thể có khoảng trống; trường hợp nằm trong khoảng trống không có mức phí được cấu hình. Phần này cấu hình biểu phí, chưa tính tiền đơn hàng.

- Các mã gợi ý: PURCHASE_SERVICE_FEE (mua hàng), INTERNATIONAL_SHIPPING (vận chuyển), INSPECTION (kiểm đếm), WOOD_PACKING (đóng gỗ). Có thể tạo mã nghiệp vụ khác dạng chữ hoa/số/gạch dưới.
- Đơn vị: PERCENT, VND, VND_PER_KG, VND_PER_M3, VND_PER_ITEM, VND_PER_PACKAGE. Với PERCENT, tier_min/max là giá trị cơ sở tính phí bằng VNĐ; các đơn vị còn lại phân bậc theo khối lượng/thể tích/số món/số kiện tương ứng. VND dùng giá trị cơ sở nghiệp vụ do bên tính phí quy định.
- `value` không âm, tối đa 4 chữ số thập phân; PERCENT không quá 100. Tiền trả dạng chuỗi.
- Ngày hiệu lực mặc định là ngày hiện tại theo Asia/Ho_Chi_Minh.
- `GET /fee-configs?fee_type=INTERNATIONAL_SHIPPING&active_only=false&limit=20&offset=0`: danh sách phiên bản.
- `GET /fee-configs/current?on_date=2026-10-05&fee_type=INTERNATIONAL_SHIPPING&unit=VND_PER_KG`: phiên bản đang hoạt động, mới nhất có ngày hiệu lực không sau ngày chọn, cho từng cặp fee_type/unit. Cùng ngày thì ID mới hơn được chọn.
- `GET /fee-configs/{id}`: xem cả phiên bản đã vô hiệu hóa.
- `PATCH /fee-configs/{id}` (ADMIN): chỉ sửa description/is_active. Đổi mức phí/bậc/ngày hiệu lực bằng POST tạo phiên bản mới, giữ lịch sử cũ.
- `DELETE /fee-configs/{id}` (ADMIN): xóa mềm, trả 204. Khi vô hiệu hóa bản mới nhất, tra cứu hiện hành có thể quay về bản cũ còn hoạt động.

## Test Postman

Import collection tại `Gateway/postman/Logistics-Gateway.postman_collection.json`. Nhóm Buổi 1 chạy theo thứ tự đăng nhập ADMIN → tỷ giá → bảng phí; token tự lưu trong biến collection. Các request cập nhật quyền cần user_id của tài khoản mục tiêu; không dùng ADMIN cuối cùng làm mục tiêu thử khóa.


Có thể áp dụng các file `05` đến `09` tự động từ thư mục BE:

```bash
.venv/bin/python scripts/apply_logistics_sql.py --env .env
```

Script yêu cầu database logistics đã có và kiểm tra cột users.role trước khi chạy. DDL MySQL tự commit; script không xóa bảng hoặc dữ liệu nghiệp vụ.
