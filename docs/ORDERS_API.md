# API đơn vận chuyển

Đơn ghi nhận hàng khách gửi, không phải nghiệp vụ bán hàng. Dùng hai bảng hiện có
`don_hang` và `chi_tiet_don_hang`; không thêm bảng hoặc danh mục sản phẩm.

Base URL: `http://127.0.0.1:8000`. Tất cả request cần Authorization → Bearer Token
với access_token lấy từ login. POST/PATCH dùng Body → raw → JSON.

## API và dữ liệu mẫu

| Method | URL | Thành công |
|---|---|---|
| POST | http://127.0.0.1:8000/orders | 201 |
| GET | http://127.0.0.1:8000/orders?limit=20&offset=0 | 200 |
| GET | http://127.0.0.1:8000/orders/1 | 200 |
| PATCH | http://127.0.0.1:8000/orders/1 | 200 |
| PATCH | http://127.0.0.1:8000/orders/1/status | 200 |

Thay 1 bằng ID đơn thật. Không có DELETE: dùng chuyển trạng thái CANCELLED.

### Tạo đơn

```json
{
  "customer_id": 1,
  "recipient_name": "Nguyễn Văn A",
  "recipient_phone": "0987654321",
  "recipient_address": "123 Lê Duẩn, Đà Nẵng",
  "shipping_fee": "150000.50",
  "note": "Giao giờ hành chính",
  "items": [
    {"name": "Áo thun", "quantity": 20},
    {"name": "Giày", "quantity": 5, "note": "Đóng riêng"}
  ]
}
```

customer_id là ID hồ sơ từ GET /customers, không phải ID tài khoản người dùng.
Khách phải đang hoạt động. SALE chỉ tạo đơn cho khách đang được phân công.
creator lấy từ token/DB; trạng thái ban đầu luôn PENDING.
order_code có thể bỏ (tự sinh DH + UUID) hoặc gửi mã riêng 3–40 ký tự chữ/số/_/-;
mã nhập được viết hoa, trùng trả 409.

Mỗi đơn có 1–100 dòng hàng; name không rỗng, tối đa 255 ký tự; quantity là số nguyên
1–2147483647. Không có giá bán/SKU/tồn sản phẩm. note tối đa 2000 ký tự.
Phí vận chuyển >= 0, tối đa 16 chữ số phần nguyên và 2 chữ số thập phân;
response dùng chuỗi tiền tệ để giữ độ chính xác. Bỏ phí thì mặc định 0.
Đơn và các dòng hàng được lưu trong cùng transaction: lỗi bất kỳ dòng nào thì rollback toàn bộ.

### Danh sách và chi tiết

Lọc theo customer_id, status, search (mã đơn/tên người nhận/điện thoại), limit (1–100),
offset (>=0). Ví dụ:

`GET /orders?customer_id=1&status=PENDING&search=Nguyễn&limit=20&offset=0`

Danh sách trả `{items: [...], limit: 20, offset: 0}`. Chi tiết trả một đơn kèm items.
Các trường: id, order_code, customer_id, created_by, recipient_name, recipient_phone,
recipient_address, shipping_fee, status, note, created_at, updated_at.
Mỗi dòng hàng: id, name, quantity, note. Thời gian trả UTC.

### Sửa đơn

Chỉ được sửa khi PENDING và chưa có kiện/thanh toán. Ví dụ:

```json
{
  "recipient_address": "456 Nguyễn Trãi, TP HCM",
  "shipping_fee": "160000.00",
  "note": null
}
```

Có thể thay toàn bộ danh sách items bằng một danh sách mới hợp lệ; ID các dòng hàng sẽ thay đổi.
Trường không gửi giữ nguyên; note:null xóa ghi chú, chuỗi "null" vẫn là ghi chú văn bản.
Không được đổi customer_id, order_code, created_by, status qua endpoint sửa thông tin.
Không có API xóa lẻ dòng hàng; dùng items để thay toàn bộ trước xác nhận.

### Trạng thái

`PATCH /orders/1/status`

```json
{"status": "CONFIRMED"}
```

Luồng: PENDING → CONFIRMED → SHIPPING → DELIVERED.
PENDING hoặc CONFIRMED được chuyển CANCELLED. Không quay lại bước trước, không bỏ bước,
không hủy sau SHIPPING. Gửi lại đúng trạng thái hiện tại trả 200.
Sửa thông tin sau xác nhận hoặc chuyển trạng thái sai trả 409.
Hủy bị chặn khi còn kiện chưa CANCELLED hoặc đã có bất kỳ giao dịch thanh toán.

Trạng thái đơn hiện được nhân viên cập nhật thủ công; chưa tự cập nhật trạng thái kiện,
lịch sử vận chuyển hoặc đối soát thanh toán. Các phần đó thuộc API triển khai tiếp theo.

## Phạm vi quyền

- ADMIN quản lý tất cả đơn.
- SALE tạo/sửa/chuyển trạng thái đơn của khách hiện được phân công. Quyền dựa vào khách,
  không dựa vào người tạo đơn: đổi SALE phụ trách thì quyền trên các đơn cũ chuyển theo.
- CUSTOMER chỉ đọc đơn có khach_hang.ma_nguoi_dung bằng ID tài khoản mình, không được ghi.
- ACCOUNTANT/WAREHOUSE chưa có quyền truy cập đơn trong phần này.
- Đơn ngoài phạm vi hoặc không tồn tại trả 404. List ngoài phạm vi trả items rỗng.
- Khách ngừng hoạt động không được tạo thêm đơn; vẫn xem lịch sử đơn trong phạm vi.

## Luồng code

1. Gateway/gateway_app/app.py kiểm tra JWT, thêm x-gateway-key và chuyển /orders sang BE.
2. BE/app/main.py kiểm tra khóa nội bộ; current_user đọc trạng thái/vai trò hiện tại từ DB;
   include_router(create_order_router(current_user)) đăng ký các API đơn.
3. BE/app/orders.py: OrderCreate/OrderUpdate/OrderStatusUpdate kiểm tra JSON; reader/writer
   kiểm tra vai trò. Hàm route gọi CALL sp_* với actor lấy từ tài khoản đã xác thực.
4. BE/app/infrastructure/db/session.py cung cấp AsyncSession kết nối DATABASE_URL.
5. sql/cms_logistics_orders.sql định nghĩa 5 procedure nghiệp vụ và 3 helper:
   sp_order_actor (kiểm tra tài khoản), sp_lock_order (khóa và kiểm tra phạm vi ghi),
   sp_insert_order_items (kiểm tra và thêm hàng). Quyền còn được kiểm tra tại SQL.
6. API gọi commit khi toàn bộ thành công, rollback khi lỗi. order_row đổi Decimal sang chuỗi,
   thời gian thành UTC, đọc JSON danh sách hàng, trả qua Gateway cho client.

Các thao tác ghi khóa tài khoản → khách hàng → đơn để việc đổi phân công và thay đổi trạng thái
không bị kiểm tra trên dữ liệu cũ. Hai nhánh SHIPPING/CANCELLED cạnh tranh chỉ một nhánh thành công.

## Cài SQL và kiểm thử

Database mới: chạy schema, auth procedures, customer procedures, rồi cms_logistics_orders.sql.
Database đã có 10 bảng: chỉ chạy toàn bộ sql/cms_logistics_orders.sql trong MySQL Workbench.
Không cần chạy lại schema. Docker volume rỗng tự cài đủ bốn file qua Compose.

Từ gốc repo:

```bash
BE/.venv/bin/python BE/tests/check_orders.py
BE/.venv/bin/python BE/tests/check_orders.py --postman
```

Runner tạo DB cms_order_test_<uuid>, cài SQL hai lần, kiểm thử API và dọn DB tạm.
Cần CREATE/DROP DATABASE và CREATE ROUTINE. --postman bật hai server HTTP tạm và chạy
Postman CLI với --no-report-events; tự đóng server, không tạo dữ liệu thử trong DB ứng dụng.

Import Gateway/postman/Logistics-Orders.postman_collection.json để test thủ công.
Điền admin_username/admin_password trong biến collection. Chạy collection trên DB ứng dụng
sẽ tạo khách và đơn thử thật; collection không tự xóa các dữ liệu này.
