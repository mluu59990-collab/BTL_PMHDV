# Backend cms_logistics

Xem [hướng dẫn hiện tại](../README.md) và [API](../docs/API_BUOI_1.md).

Entrypoint: `app.main:app`, cổng 8001. Cấu hình `.env` trỏ tới `cms_logistics`.
Cài procedure bằng cách chạy `../sql/cms_logistics_procedures.sql`, rồi
`../sql/cms_logistics_customers.sql`, `../sql/cms_logistics_orders.sql`,
`../sql/cms_logistics_fulfillment.sql` trong MySQL Workbench.

Code hiện tại:

- `app/main.py`: auth, quyền và đăng ký router khách hàng.
- `app/customers.py`: 5 API khách hàng, schema và xử lý lỗi.
- `app/orders.py`: 5 API đơn vận chuyển, hàng gửi và trạng thái.
- `app/fulfillment.py`: 11 API kho, kiện, nhập/xuất kho và lịch sử.
- `app/core/`: cấu hình và thời gian UTC.
- `app/domain/`: loại token và lỗi xác thực.
- `app/application/ports.py`: giao diện hash/JWT và kiểu dữ liệu token.
- `app/infrastructure/db/session.py`: engine và session MySQL.
- `app/infrastructure/security/`: Argon2 và JWT.

Kiểm thử từ gốc repo: `BE/.venv/bin/python Gateway/integration/check_flow.py BE`.

Kiểm thử đơn/MySQL tạm/Postman: `BE/.venv/bin/python BE/tests/check_orders.py --postman` (từ gốc repo).

Kiểm thử kho/kiện: `BE/.venv/bin/python BE/tests/check_fulfillment.py --postman` (từ gốc repo).
