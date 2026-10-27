# API khách hàng — cms_logistics

Base URL: `http://127.0.0.1:8000`. Tất cả request cần header
`Authorization: Bearer <access_token>`. POST/PATCH dùng Body → raw → JSON.

| Method | URL | Thành công |
|---|---|---|
| POST | http://127.0.0.1:8000/customers | 201 |
| GET | http://127.0.0.1:8000/customers?limit=20&offset=0 | 200 |
| GET | http://127.0.0.1:8000/customers/1 | 200 |
| PATCH | http://127.0.0.1:8000/customers/1 | 200 |
| DELETE | http://127.0.0.1:8000/customers/1 | 204 |

Thay `1` bằng ID khách hàng thật; ID khách hàng khác ID tài khoản.

## Quyền

- ADMIN đọc/tạo/sửa/xóa mềm mọi hồ sơ, liên kết tài khoản, phân công SALE và kích hoạt lại.
- SALE đọc/sửa/xóa mềm khách được phân công. Khách do SALE tạo tự gán cho SALE đó.
  SALE không được gửi user_id/sale_id khi tạo hoặc sửa, không được PATCH is_active.
- CUSTOMER chỉ đọc hồ sơ có user_id bằng ID tài khoản đang đăng nhập và còn hoạt động.
  CUSTOMER không được tạo/sửa/xóa. Danh sách chỉ chứa hồ sơ của mình hoặc rỗng.
- WAREHOUSE/ACCOUNTANT không được truy cập khách hàng.
- Hồ sơ không tồn tại hoặc ngoài phạm vi đọc/sửa/xóa trả 404.

## Tạo khách hàng

```json
{
  "name": "Nguyễn Văn A",
  "phone": "0912345678",
  "address": "Hà Nội",
  "email": "a@example.com"
}
```

ADMIN có thể bổ sung `"user_id": 8` và `"sale_id": 2`, dùng ID thật:
user_id phải là tài khoản CUSTOMER ACTIVE; sale_id phải là SALE ACTIVE.
Một tài khoản chỉ liên kết một hồ sơ khách; trùng liên kết trả 409.
Nếu không có tài khoản liên kết, bỏ user_id hoặc để null. Không bắt buộc khách hàng có tài khoản.
Đăng ký tài khoản không tự tạo hồ sơ khach_hang: ADMIN phải tạo/liên kết hồ sơ riêng.

## Sửa và phân công

SALE/ADMIN có thể PATCH name, phone, address, email. Chỉ cập nhật các trường đã gửi.
ADMIN có thể PATCH user_id, sale_id, is_active.

```json
{"sale_id": 2, "user_id": 8}
```

Bỏ liên kết/phân công: `{"user_id": null, "sale_id": null}`.
Xóa email: `{"email": null}`. name/phone/address/is_active không được null.
Kích hoạt lại (ADMIN): `{"is_active": true}`.
Body rỗng, trường lạ, email/điện thoại sai, ID <= 0 trả 422.

## Danh sách và xóa mềm

Query: search (tên/điện thoại), limit (1–100), offset (>= 0), active_only (mặc định true).
Ví dụ: `/customers?search=Nguyễn&active_only=false&limit=20&offset=0`.
Phản hồi `{items: [...], limit: 20, offset: 0}`; mỗi item gồm id, user_id, name, phone,
email, address, sale_id, is_active, created_at, updated_at (UTC).

DELETE đặt dang_hoat_dong=0, không xóa hàng DB hay ảnh hưởng khóa ngoại đơn hàng.
ADMIN/SALE có thể xem hồ sơ không hoạt động trong phạm vi qua chi tiết hoặc active_only=false.
CUSTOMER không được xem hồ sơ đã ngừng hoạt động kể cả gửi active_only=false.

## Luồng code

1. `Gateway/gateway_app/app.py`: kiểm tra JWT, thêm khóa nội bộ, chuyển request tới BE.
   /customers không nằm trong PUBLIC_ROUTES nên tự được bảo vệ.
2. `BE/app/main.py`: middleware kiểm tra khóa; current_user trong BE/app/auth.py đọc trạng thái/vai trò từ DB;
   include_router(create_customer_router(current_user)) đăng ký API khách hàng.
3. `BE/app/customers.py`: reader/writer kiểm tra vai trò, CustomerCreate/CustomerUpdate
   kiểm tra JSON, gọi CALL sp_* bằng tham số. Lỗi SQL chuyển thành 403/404/409/422.
4. `BE/app/infrastructure/db/session.py`: cung cấp AsyncSession dùng DATABASE_URL từ config/.env.
5. `sql/cms_logistics_customers.sql`: định nghĩa 5 procedure list/get/create/update/deactivate;
   kiểm tra lại vai trò và phạm vi trong SQL, dùng ma_nguoi_dung/ma_nhan_vien_phu_trach.
6. MySQL đọc/ghi khach_hang; API ghi commit khi thành công, rollback khi lỗi, trả JSON qua Gateway.

File SQL được cài vào MySQL một lần, không đọc từ đĩa mỗi request. Cài vào DB đã có bảng
bằng cách chạy toàn bộ sql/cms_logistics_customers.sql trong Workbench. Docker volume mới tự cài.

## Kiểm thử

Từ gốc repo: `BE/.venv/bin/python BE/tests/check_customers.py`.
Runner tạo DB ngẫu nhiên cms_customer_test_<uuid>, cài schema và procedures (hai lần),
tạo tài khoản thử rồi chạy HTTP Gateway → BE → MySQL. Cuối cùng xóa đúng DB tạm;
không tạo dữ liệu thử trong cms_logistics. Cần CREATE/DROP DATABASE và CREATE ROUTINE.
