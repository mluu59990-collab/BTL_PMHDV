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
