# Logistics API Gateway

Repo FastAPI riêng. Client gọi Gateway :8000; Gateway gọi BE :8001; chỉ BE kết nối MySQL. Gateway không có SQL hoặc cấu hình database.

## 1. Chuẩn bị hai repo

Đặt `Gateway/` cạnh `BE/`. Mỗi thư mục có `.venv`, `.env` và Git riêng.

Trong Gateway:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

`.env` đã được tạo trên máy khi tích hợp. Trên máy khác, copy `.env.example` thành `.env`, rồi cấu hình:

```dotenv
BACKEND_URL=http://127.0.0.1:8001
JWT_SECRET_KEY=<cùng giá trị JWT_SECRET_KEY trong BE/.env>
JWT_ALGORITHM=HS256
GATEWAY_SHARED_SECRET=<khóa nội bộ ngẫu nhiên, cùng giá trị trong BE/.env>
REQUEST_TIMEOUT=15
MAX_BODY_BYTES=1048576
```

Tạo khóa nội bộ nếu chưa có: `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'`.
Khóa JWT và khóa gateway phải là hai khóa khác nhau, tối thiểu 32 ký tự. Không đưa `.env` lên Git hoặc nhập khóa nội bộ vào Postman.

## 2. Cài stored procedure

Mở `../sql/05_procedures.sql` trong MySQL Workbench, chạy toàn bộ trên `cms_logistics_core`. File chỉ tạo lại bốn thủ tục, không sửa bảng hoặc dữ liệu:

- `sp_health`: kiểm tra DB.
- `sp_get_user_for_login`: tìm tài khoản để xác thực.
- `sp_get_auth_user`: đọc trạng thái và vai trò mới nhất.
- `sp_get_users`: lấy tối đa 10 người dùng.

Nếu database ở máy khác, tạo schema và dữ liệu từ `../sql/my_db_logistic.sql` trước. BE/.env phải có DATABASE_URL đúng database này.

## 3. Bật backend — Terminal 1

Mở Terminal tại thư mục BE:

```bash
DEBUG=false .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

## 4. Bật gateway — Terminal 2

Mở Terminal tại thư mục Gateway:

```bash
.venv/bin/python -m uvicorn gateway_app.main:app --host 127.0.0.1 --port 8000 --reload
```

Giữ cả hai Terminal mở. Dừng phiên BE cũ đang chiếm cổng 8000 trước khi bật gateway. Dùng `.venv/bin/python` tránh activation script cũ bị sai đường dẫn sau khi đổi tên BTL thành BE.

## 5. Test trong Postman

Import `postman/Logistics-Gateway.postman_collection.json`. Collection có biến `base_url=http://127.0.0.1:8000` và tự lưu token từ request đăng nhập thành `access_token`.

Chạy lần lượt:

1. **Gateway health** — GET `/gateway/health`, No Auth → 200. Chỉ kiểm tra gateway.
2. **Backend + DB health** — GET `/health`, No Auth → 200. Kiểm tra cả gateway, BE và DB.
3. **Users without token** — GET `/users`, No Auth → 401.
4. **Login admin** — POST `/auth/login`, No Auth; Body raw JSON:

```json
{"username":"admin","password":"Admin@123456"}
```

Kết quả 200, có `access_token`; Postman tự lưu biến.

5. **Current user** — GET `/auth/me`, Bearer Token `{{access_token}}` → 200.
6. **Users as admin** — GET `/users`, Bearer Token `{{access_token}}` → 200, không có password_hash.
7. **Wrong password** → 401; **Invalid token** → 401.
8. **Direct backend blocked** — GET `http://127.0.0.1:8001/users`, No Auth → 403.
9. **Login sale** rồi **Users as sale** → đăng nhập 200, danh sách users 403.

Tài khoản trên là tài khoản seed thực hành. Nếu bạn đã thay mật khẩu, sửa biến `admin_password`/`sale_password` của collection.

## Cấu trúc và quy tắc

- `gateway_app/config.py`: đọc cấu hình; chỉ chấp nhận HS256 phù hợp BE hiện tại.
- `gateway_app/app.py`: xác thực JWT, lọc header, chuyển HTTP request/response.
- `gateway_app/main.py`: entrypoint Uvicorn.
- `tests/test_gateway.py`: test xác thực, proxy và xử lý lỗi.
- `integration/check_flow.py`: test xuyên gateway/BE với DB giả lập; chạy từ Gateway bằng `python integration/check_flow.py ../BE` sau khi cài requirements của BE vào môi trường test.

Chỉ `POST /auth/login`, `GET /health` và health riêng gateway là công khai. API mới mặc định cần access token; token refresh không được dùng thay access token. Gateway không cấp JWT. BE cấp access token và kiểm tra lại token cùng trạng thái/vai trò trong DB. Chưa triển khai refresh/logout ở luồng mới.

Gateway loại header danh tính do client tự gửi, tự thêm khóa nội bộ. BE kiểm tra khóa trên mọi request, kể cả health. Khi triển khai phải dùng HTTPS, giữ BE trong mạng nội bộ và giới hạn kết nối từ gateway; khóa dùng chung không thay thế kiểm soát mạng.

Bản này phục vụ HTTP JSON trong giai đoạn học: body tối đa 1 MiB, timeout 15 giây, không tự theo redirect hoặc retry request ghi. Chưa có WebSocket, CORS cho frontend, rate limiting hoặc cân bằng tải nhiều backend. Postman không cần CORS.

## Lỗi thường gặp

| Mã/lỗi | Nguyên nhân |
|---|---|
| Không kết nối được :8000 | Gateway chưa chạy hoặc sai port |
| 502 | BE chưa chạy hoặc BACKEND_URL sai |
| 504 | BE xử lý quá thời gian |
| 401 | Thiếu/sai/hết hạn token hoặc JWT_SECRET_KEY không khớp |
| 403 qua gateway kể cả /health | GATEWAY_SHARED_SECRET giữa hai repo không khớp |
| 403 ở /users | Tài khoản không có quyền ADMIN hoặc bị khóa |
| 500 từ BE | Xem Terminal BE; kiểm tra DB và stored procedure |
| Cổng đã được sử dụng | Dừng tiến trình cũ bằng Ctrl+C tại Terminal đang chạy |

## Kiểm thử

```bash
.venv/bin/python -m pytest tests -q
```

Tài liệu tham khảo: [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/), [HTTPX async streaming](https://www.python-httpx.org/async/).
