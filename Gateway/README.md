# Logistics API Gateway

Xem [hướng dẫn chạy và API hiện tại](../README.md).

Gateway cổng 8000, BE cổng 8001; `BACKEND_URL=http://127.0.0.1:8001`.
JWT_SECRET_KEY và GATEWAY_SHARED_SECRET phải khớp BE.

Tại thư mục Gateway:
```bash
.venv/bin/python -m uvicorn gateway_app.main:app --host 127.0.0.1 --port 8000 --reload
```

Import `postman/Logistics-Gateway.postman_collection.json`, cấu hình mật khẩu thực tế.
Gateway kiểm tra JWT, loại header giả mạo và thêm khóa nội bộ; BE kiểm tra lại quyền từ DB.
502: không kết nối được BE; 504: timeout; 403 cả health: kiểm tra khóa nội bộ.
Chưa hỗ trợ CORS cho frontend khác origin, WebSocket hoặc rate limiting.

Đơn vận chuyển: import `postman/Logistics-Orders.postman_collection.json`, cấu hình
`admin_username`/`admin_password`. Collection tạo khách và đơn thử trong DB đang kết nối.
Hướng dẫn: [ORDERS_API.md](../docs/ORDERS_API.md).

Kho/kiện: import `postman/Logistics-Fulfillment.postman_collection.json`, cấu hình
`admin_username`/`admin_password`. Xem [FULFILLMENT_API.md](../docs/FULFILLMENT_API.md).

Thu/hoàn phí: import `postman/Logistics-Payments.postman_collection.json`, cấu hình
`admin_username`/`admin_password`. Xem [PAYMENTS_API.md](../docs/PAYMENTS_API.md).
