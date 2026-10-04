# BTL Phát triển phần mềm hướng dịch vụ

Một repo chứa backend FastAPI, API Gateway riêng và SQL logistics.

```text
Postman / Frontend → Gateway :8000 → BE :8001 → MySQL :3306
```

## Cấu trúc

- `BE/`: backend và phần nghiệp vụ. Code cũ CRM/catalog vẫn được giữ để tham khảo; luồng đang chạy trong `BE/app/main.py` dùng stored procedure logistics.
- `Gateway/`: dịch vụ FastAPI xác thực JWT và chuyển request sang BE.
- `sql/`: schema, dữ liệu mẫu và stored procedure.
- `doc/`: tài liệu SRS và kế hoạch.
- `BTL/postman/`: metadata workspace Postman có sẵn trên máy.

## Chạy lần đầu

1. Bật MySQL. Chạy `sql/my_db_logistic.sql` để tạo database và dữ liệu dev. Nếu muốn thêm dữ liệu thực hành, chạy `sql/data.sql` (xem nội dung trước khi chạy lại).
2. Chạy toàn bộ `sql/05_procedures.sql` trong MySQL Workbench để tạo các thủ tục mà BE cần.
3. Tạo môi trường riêng và cài thư viện trong mỗi thư mục:

```bash
cd BE
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cd ../Gateway
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

4. Tạo `BE/.env` và `Gateway/.env` theo `.env.example` của từng thư mục. Cấu hình `DATABASE_URL` tại BE trỏ tới `cms_logistics_core`. Hai file phải có cùng `JWT_SECRET_KEY` và cùng `GATEWAY_SHARED_SECRET`; hai loại khóa phải khác nhau và dài ít nhất 32 ký tự. Không commit `.env`.
5. Trong Terminal tại BE:

```bash
DEBUG=false .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

6. Trong Terminal khác tại Gateway:

```bash
.venv/bin/python -m uvicorn gateway_app.main:app --host 127.0.0.1 --port 8000 --reload
```

7. Import `Gateway/postman/Logistics-Gateway.postman_collection.json` vào Postman. Client gọi cổng 8000; gọi trực tiếp BE thiếu khóa nội bộ sẽ trả 403.

Xem hướng dẫn đầy đủ tại [Gateway/README.md](Gateway/README.md). Các tài liệu/test CRM/catalog cũ trong BE thuộc phiên bản trước, không phải toàn bộ chức năng của luồng logistics hiện tại.

## Kiểm thử gateway

Từ thư mục Gateway:

```bash
.venv/bin/python -m pytest tests -q
../BE/.venv/bin/python integration/check_flow.py ../BE
```

Bộ integration dùng DB giả lập để kiểm tra luồng Gateway → BE; không thay thế việc test MySQL thật. Nếu chỉ cài requirements.txt cho BE, cài thêm requirements-dev.txt trước khi chạy integration test.
