# Kho, đóng kiện và vận chuyển

Dùng 4 bảng hiện có: kho_hang, kien_hang, chi_tiet_kien_hang, lich_su_van_chuyen.
Không thêm bảng, không có danh mục sản phẩm bán hàng. Hàng đóng kiện phải lấy từ chi_tiet_don_hang.

Base URL: http://127.0.0.1:8000. Mọi API cần Bearer access token.
POST/PATCH: Body → raw → JSON. Thay ID mẫu bằng ID thật trong response.

## Quyền

- ADMIN tạo/sửa/ngừng hoạt động kho; xử lý tất cả kiện.
- WAREHOUSE xem kho/đơn, đóng kiện, sửa kiện trước nhập kho và cập nhật vận chuyển.
  Không được đổi thông tin kho hoặc sửa thông tin/trạng thái đơn trực tiếp.
- SALE chỉ xem kiện/đơn của khách hiện được phân công; CUSTOMER chỉ xem kiện/đơn của hồ sơ liên kết.
- SALE/CUSTOMER chỉ thấy kho mà kiện trong phạm vi của họ đã đi qua (dựa vào lịch sử).
  Không được xem danh sách tồn kho của người khác khi thêm warehouse_id vào query.
- ACCOUNTANT chưa có quyền trong phần này. Truy cập hồ sơ ngoài phạm vi trả 404;
  gọi chức năng ghi không được phép trả 403. Phạm vi lấy từ DB hiện tại, không tin role cũ trong JWT.

## Kho — 5 API

| Method | URL | Chức năng |
|---|---|---|
| POST | http://127.0.0.1:8000/warehouses | ADMIN tạo kho (201) |
| GET | http://127.0.0.1:8000/warehouses?limit=20&offset=0 | Danh sách (200) |
| GET | http://127.0.0.1:8000/warehouses/1 | Chi tiết (200) |
| PATCH | http://127.0.0.1:8000/warehouses/1 | ADMIN sửa (200) |
| DELETE | http://127.0.0.1:8000/warehouses/1 | ADMIN ngừng hoạt động (204) |

Tạo kho:

```json
{
  "warehouse_code": "CN_01",
  "name": "Kho Quảng Châu",
  "address": "Quảng Châu, Trung Quốc",
  "country_code": "CN"
}
```

country_code: CN hoặc VN. Mã kho 2–30 ký tự chữ/số/_/-, được viết hoa, trùng trả 409.
Danh sách hỗ trợ search (mã/tên), active_only (mặc định true), limit (1–100), offset (>=0).
Response gồm id, warehouse_code, name, address, country_code, is_active.

PATCH chỉ cho name/address/is_active, không đổi mã kho hoặc quốc gia:

```json
{"name": "Kho CN mới", "address": "Địa chỉ mới"}
```

DELETE là xóa mềm; kho còn kiện IN_WAREHOUSE trả 409.
Kích hoạt lại bằng PATCH `{"is_active": true}`. Kho ngừng hoạt động không nhận thêm kiện;
lịch sử cũ vẫn giữ. Để xem kho inactive trong danh sách dùng active_only=false.

## Kiện và lịch sử — 6 API

| Method | URL | Chức năng |
|---|---|---|
| POST | http://127.0.0.1:8000/packages | Đóng kiện (201) |
| GET | http://127.0.0.1:8000/packages?order_id=1 | Danh sách theo đơn (200) |
| GET | http://127.0.0.1:8000/packages/1 | Chi tiết và hàng trong kiện (200) |
| PATCH | http://127.0.0.1:8000/packages/1 | Sửa kiện CREATED (200) |
| PATCH | http://127.0.0.1:8000/packages/1/status | Nhập/xuất kho, giao/hủy (200) |
| GET | http://127.0.0.1:8000/packages/1/history | Lịch sử (200) |

### Chuẩn bị và tạo kiện

1. Tạo đơn, xác nhận qua PATCH /orders/{id}/status với status=CONFIRMED.
2. GET /orders/{id} lấy items[].id, packed_quantity và remaining_quantity.
3. POST /packages bằng ADMIN hoặc WAREHOUSE:

```json
{
  "order_id": 1,
  "weight_kg": "3.500",
  "length_cm": "40.00",
  "width_cm": "30.00",
  "height_cm": "20.00",
  "items": [
    {"order_item_id": 1, "quantity": 10},
    {"order_item_id": 2, "quantity": 5}
  ],
  "note": "Đóng kiện đầu tiên"
}
```

order_item_id là ID dòng hàng từ GET /orders/{id}, không phải ID đơn hay ID khách.
Mỗi kiện có 1–100 dòng hàng, không trùng order_item_id. quantity phải là số nguyên >0.
Dòng hàng phải thuộc đúng đơn. Tổng số lượng trong các kiện không CANCELLED không được vượt số lượng đặt.
Phần vượt trả 409; dòng hàng thuộc đơn khác trả 422. Hai nhân viên đóng đồng thời dùng cùng khóa đơn,
chỉ một người giữ được phần số lượng còn lại. Toàn bộ kiện, hàng và mốc CREATED cùng transaction.

Đơn phải CONFIRMED hoặc SHIPPING, cho phép tiếp tục đóng phần hàng còn lại khi giao nhiều đợt.
Không đóng đơn PENDING/CANCELLED/DELIVERED. tracking_code có thể bỏ để tự sinh VD + UUID;
nếu gửi riêng thì 3–50 ký tự chữ/số/_/-, viết hoa, trùng trả 409.
weight_kg >0, tối đa 9 chữ số nguyên và 3 số thập phân; kích thước >0,
tối đa 8 chữ số nguyên và 2 số thập phân. Response trả số đo dạng chuỗi chính xác.

### Xem và sửa kiện

Danh sách lọc order_id, warehouse_id (kho hiện tại), status, search (mã vận đơn), limit/offset.
Ví dụ: `/packages?warehouse_id=1&status=IN_WAREHOUSE&limit=20&offset=0`.
Response danh sách `{items: [...], limit: 20, offset: 0}`.
Chi tiết có id, order_id, tracking_code, warehouse_id, weight_kg, length_cm, width_cm,
height_cm, status, created_at, updated_at, items (id, order_item_id, name, quantity).

PATCH chỉ cho weight_kg/length_cm/width_cm/height_cm/items, chỉ khi CREATED:

```json
{"weight_kg": "3.750"}
```

Nếu gửi items thì thay toàn bộ hàng trong kiện và tính lại sức chứa khả dụng, không cộng trùng chính kiện.
Các ID dòng chi tiết kiện sẽ đổi; lỗi giữa chừng rollback để giữ nguyên dữ liệu cũ.
Không đổi order_id/tracking_code qua PATCH. Đo lại trước nhập kho; sau nhập kho sửa trả 409.

### Nhập kho, xuất kho, giao hàng

Cùng URL `PATCH /packages/1/status`, lần lượt gửi:

Nhập kho CN:

```json
{"status": "IN_WAREHOUSE", "warehouse_id": 1, "note": "Đã nhập CN"}
```

Xuất kho:

```json
{"status": "IN_TRANSIT", "note": "Đang vận chuyển sang VN"}
```

Nhập kho VN:

```json
{"status": "IN_WAREHOUSE", "warehouse_id": 2, "note": "Đã đến VN"}
```

Xuất giao nội địa:

```json
{"status": "IN_TRANSIT"}
```

Giao thành công:

```json
{"status": "DELIVERED", "note": "Khách đã nhận"}
```

Luồng: CREATED → IN_WAREHOUSE → IN_TRANSIT → IN_WAREHOUSE (kho tiếp theo) hoặc DELIVERED.
CREATED/IN_WAREHOUSE có thể CANCELLED để ngừng kiện và giải phóng số lượng đóng;
hủy tại kho có nghĩa kiện đã được rút khỏi kho, sự kiện giữ kho nguồn trong lịch sử.
IN_TRANSIT không được hủy. DELIVERED/CANCELLED không mở lại; không hỗ trợ nghiệp vụ hoàn hàng.
Không đổi kho trực tiếp khi IN_WAREHOUSE: phải xuất rồi nhập kho mới.
Chỉ IN_WAREHOUSE nhận warehouse_id; trạng thái khác phải bỏ hoặc để null (theo CHECK constraint DB).

Gửi lại đúng trạng thái và kho hiện tại trả 200 mà không thêm sự kiện lịch sử.
Muốn bổ sung ghi chú vào mốc cũ hiện chưa có API riêng.
DELETE kiện không được cung cấp; dùng status=CANCELLED. Kiện hủy giữ nguyên hàng và lịch sử,
nhưng không chiếm số lượng nên có thể đóng kiện thay thế.

### Đồng bộ đơn và lịch sử

- Kiện đầu tiên chuyển IN_TRANSIT thì đơn CONFIRMED tự thành SHIPPING.
- Chỉ khi tổng số lượng đã DELIVERED đủ mọi dòng hàng mới tự thành DELIVERED.
  Giao một phần hoặc còn hàng chưa đóng thì đơn vẫn SHIPPING.
- Mỗi lần đổi trạng thái ghi lịch sử và cập nhật kiện/đơn trong cùng transaction.
- Đơn đã có kiện không được chuyển tay sang SHIPPING/DELIVERED nếu tiến độ kiện chưa khớp.
  Đơn chưa có kiện vẫn giữ luồng chuyển thủ công cũ để tương thích.
- Không tự động CANCELLED cả đơn khi hủy kiện; ADMIN/SALE hủy đơn qua API đơn khi điều kiện cho phép.

History hỗ trợ limit (mặc định 50, tối đa 100) và offset; thứ tự thời gian tăng dần, cùng thời gian thì theo id.
Mỗi mốc có id, package_id, warehouse_id, status, note, created_by, created_at (UTC).
Nhập kho ghi kho đích; xuất/hủy tại kho ghi kho nguồn. warehouse_id trên kiện chỉ là kho hiện tại,
ra khỏi kho thì null; các kho đã đi qua còn trong lịch sử.

## File và luồng code

1. Gateway/gateway_app/app.py kiểm tra JWT và chuyển request cùng khóa nội bộ.
2. BE/app/main.py: middleware, current_user từ BE/app/auth.py, include_router(create_fulfillment_router(current_user)).
3. BE/app/fulfillment.py: schema JSON, reader/operator/administrator; các route gọi procedure;
   one/many xử lý kết quả, commit/rollback và ánh xạ lỗi HTTP.
4. BE/app/infrastructure/db/session.py cung cấp session MySQL.
5. sql/cms_logistics_fulfillment.sql: 13 procedure kiểm tra quyền, khóa đơn, kiểm tra sức chứa,
   ghi kho/kiện/hàng/lịch sử và đồng bộ trạng thái đơn.
6. sql/cms_logistics_orders.sql cập nhật quyền đọc WAREHOUSE, số lượng đã đóng/còn lại
   và chặn chuyển trạng thái đơn lệch tiến độ kiện.

Khi ghi: khóa tài khoản → khách hàng → đơn → kiện → kho đích. Các kiện cùng đơn dùng chung khóa đơn
để tránh vượt số lượng; việc tắt kho và nhập kho cùng khóa kho để tránh tồn hàng trong kho inactive.

## Cài đặt và kiểm thử

DB đã có 10 bảng: chạy lại sql/cms_logistics_orders.sql rồi sql/cms_logistics_fulfillment.sql.
Đây chỉ là thay procedure, không chạy lại schema hoặc tạo dữ liệu thử trên DB ứng dụng.
Docker volume mới tự cài qua Compose; volume cũ không tự chạy SQL khởi tạo.

```bash
BE/.venv/bin/python BE/tests/check_fulfillment.py
BE/.venv/bin/python BE/tests/check_fulfillment.py --postman
```

Test tạo database MySQL ngẫu nhiên, cài SQL hai lần, tạo fixture riêng và xóa DB tạm sau chạy.
--postman bật server HTTP tạm, chạy CLI với --no-report-events và tự đóng server.
Cần CREATE/DROP DATABASE và CREATE ROUTINE. Không ghi fixture vào cms_logistics.

Test thủ công: import Gateway/postman/Logistics-Fulfillment.postman_collection.json;
điền admin_username/admin_password. Collection tự tạo khách/đơn/kho/kiện trong DB đang kết nối,
không tự xóa các dữ liệu này. Có 25 request, 29 assertion.
