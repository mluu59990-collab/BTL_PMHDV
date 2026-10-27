# Logistics — database cms_logistics

Luồng hiện tại: Postman / Frontend → Gateway :8000 → BE :8001 → MySQL.
BE dùng stored procedure với 10 bảng tiếng Việt. Tên trường JSON vẫn là `id`,
`username`, `full_name`, `role`, `status` để giữ tương thích client.

## Chạy lại trên máy đã cấu hình

Bật MySQL trước. Từ gốc repo, mở hai Terminal:

```bash
cd BE && DEBUG=false .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

```bash
cd Gateway && .venv/bin/python -m uvicorn gateway_app.main:app --host 127.0.0.1 --port 8000 --reload
```

Kiểm tra: `curl http://127.0.0.1:8000/health`.

## Cài đặt lần đầu

1. Tạo database `cms_logistics` trong MySQL (utf8mb4). Nếu chưa có bảng, chạy
   `sql/cms_logistics_schema.sql` trong database này. File chỉ có cấu trúc, không có tài khoản mẫu.
2. Cài thư viện trong BE và Gateway: `python3 -m venv .venv`, rồi
   `.venv/bin/python -m pip install -r requirements.txt` ở mỗi thư mục.
3. Tạo `.env` từ `.env.example` nếu chưa có. BE dùng
   `DATABASE_URL=mysql+asyncmy://USER:PASSWORD@127.0.0.1:3306/cms_logistics`.
   Hai bên dùng cùng `JWT_SECRET_KEY` và cùng `GATEWAY_SHARED_SECRET`;
   hai loại khóa phải khác nhau, mỗi khóa ít nhất 32 ký tự.
4. Mở `sql/cms_logistics_procedures.sql` trong MySQL Workbench và chạy toàn bộ
   rồi chạy `sql/cms_logistics_customers.sql`, `sql/cms_logistics_orders.sql`,
   `sql/cms_logistics_fulfillment.sql`, `sql/cms_logistics_payments.sql` để cài stored procedure cho `cms_logistics`.
   Các file procedure không thêm bảng hoặc dữ liệu mẫu.
   API đăng ký tạo CUSTOMER; ADMIN phải được quản trị viên cấp quyền trong DB.
   Các file SQL cũ `05`–`09` và `my_db_logistic.sql` thuộc schema trước đây.

## API hiện tại

Không có prefix `/api/v1`. Client gọi cổng 8000; Swagger đã tắt.

| Method | Path | Quyền |
|---|---|---|
| GET | /gateway/health | Công khai; chỉ kiểm tra Gateway |
| GET | /health | Công khai; kiểm tra BE và bảng người dùng |
| POST | /auth/register | Công khai; tạo CUSTOMER |
| POST | /auth/login | Công khai |
| POST | /auth/refresh | Refresh token trong body |
| POST | /auth/logout | Refresh token trong body |
| GET | /auth/me | Bearer access token |
| GET | /auth/permissions | Bearer access token |
| GET | /users | ADMIN; limit/offset |
| PATCH | /users/{user_id}/access | ADMIN; role/status |
| POST | /customers | ADMIN hoặc SALE; SALE tự gán phụ trách |
| GET | /customers | ADMIN tất cả; SALE được phân công; CUSTOMER của mình |
| GET | /customers/{id} | Cùng phạm vi với danh sách |
| PATCH | /customers/{id} | ADMIN hoặc SALE được phân công |
| DELETE | /customers/{id} | ADMIN hoặc SALE được phân công; xóa mềm |
| POST | /orders | ADMIN hoặc SALE phụ trách khách; tạo đơn + hàng gửi |
| GET | /orders | ADMIN tất cả, SALE phụ trách khách, CUSTOMER của mình |
| GET | /orders/{id} | Chi tiết đơn kèm hàng, cùng phạm vi với danh sách |
| PATCH | /orders/{id} | ADMIN hoặc SALE phụ trách; chỉ sửa PENDING |
| PATCH | /orders/{id}/status | ADMIN hoặc SALE phụ trách; đúng luồng trạng thái |
| POST/PATCH/DELETE | /warehouses, /warehouses/{id} | ADMIN quản lý thông tin/xóa mềm kho |
| GET | /warehouses, /warehouses/{id} | ADMIN/WAREHOUSE tất cả, SALE/CUSTOMER kho liên quan |
| POST/PATCH | /packages, /packages/{id} | ADMIN/WAREHOUSE đóng và sửa kiện CREATED |
| GET | /packages, /packages/{id} | ADMIN/WAREHOUSE tất cả; SALE/CUSTOMER trong phạm vi |
| PATCH | /packages/{id}/status | ADMIN/WAREHOUSE nhập/xuất kho, giao/hủy |
| GET | /packages/{id}/history | Lịch sử theo phạm vi của kiện |
| POST | /payments | ADMIN/ACCOUNTANT ghi thu phí |
| POST | /payments/refunds | ADMIN/ACCOUNTANT ghi hoàn tiền |
| GET | /payments, /payments/{id} | ADMIN/ACCOUNTANT tất cả; SALE/CUSTOMER theo phạm vi |
| GET | /orders/{id}/payment-summary | Tổng thu/hoàn/số dư theo cùng phạm vi |

Ví dụ đăng ký: `{"username":"customer01","password":"Strong@123456","full_name":"Khách mới"}`.
Đăng nhập: `{"username":"customer01","password":"Strong@123456"}`.
Refresh/logout: `{"refresh_token":"..."}`.
Đổi quyền: `{"role":"SALE"}`; khóa: `{"status":"LOCKED"}`.

Mật khẩu Argon2, JWT access/refresh, refresh xoay vòng, kiểm tra quyền từ DB,
thu hồi refresh khi đổi quyền/trạng thái và bảo vệ ADMIN cuối cùng được giữ lại.
Logout không thu hồi ngay access token đã phát.

DB không có bảng tỷ giá/bảng phí: các API này đã được gỡ, gọi với token hợp lệ trả 404.
Đã có API khách hàng, đơn vận chuyển, kho, kiện và lịch sử vận chuyển.
Kiện bắt đầu đi/giao đủ hàng sẽ tự đồng bộ SHIPPING/DELIVERED của đơn.
Đã có API ghi nhận thu/hoàn phí và đối soát số dư theo đơn; chưa có tích hợp chuyển tiền ngân hàng.
Không có danh mục sản phẩm bán hàng.
Code CRM/catalog, service, router, repository và ORM model cũ đã được dọn khỏi BE/app.
Các file SQL cũ ở thư mục gốc sql thuộc schema trước đây.

## Postman và kiểm thử

Import `Gateway/postman/Logistics-Gateway.postman_collection.json`.
Điền mật khẩu tài khoản thực tế trong collection; collection tạo dữ liệu thử khi chạy.
Kiểm thử Gateway và luồng Gateway → BE (DB giả lập):

```bash
BE/.venv/bin/python -m pip install -r BE/requirements-dev.txt
BE/.venv/bin/python Gateway/integration/check_flow.py BE
BE/.venv/bin/python BE/tests/check_customers.py
BE/.venv/bin/python BE/tests/check_orders.py --postman
BE/.venv/bin/python BE/tests/check_fulfillment.py --postman
BE/.venv/bin/python BE/tests/check_payments.py --postman
cd Gateway && ../BE/.venv/bin/python -m pytest tests -q
```

Bộ test khách hàng tạo DB MySQL tạm cùng 10 bảng, kiểm tra quyền và tự xóa DB tạm;
cần quyền CREATE/DROP DATABASE và CREATE ROUTINE. Bộ test CRM/catalog cũ đã được xóa. Runner MySQL `BE/checks` và các script
`BE/scripts` hiện không còn trong workspace.

## MySQL Docker tùy chọn

`docker compose -f BE/docker-compose.yml up -d` dùng cổng **3307**.
MySQL local đang được sử dụng trên máy là cổng **3306**.
Docker chỉ chạy SQL khởi tạo khi volume mới/rỗng; volume cũ không tự cập nhật.
Không xóa volume chứa dữ liệu. Muốn dùng Docker, kiểm tra schema và đổi URL sang 3307.

API khách hàng chi tiết và luồng code: [docs/CUSTOMERS_API.md](docs/CUSTOMERS_API.md).

API đơn vận chuyển và luồng code: [docs/ORDERS_API.md](docs/ORDERS_API.md).

Kho/kiện/lịch sử và luồng test: [docs/FULFILLMENT_API.md](docs/FULFILLMENT_API.md).

Thu/hoàn phí và số dư: [docs/PAYMENTS_API.md](docs/PAYMENTS_API.md).
