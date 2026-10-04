# Phạm vi đã chốt — chỉ sửa database

Đã tạo MySQL `cms_logistics_core` gồm 9 bảng: users, refresh_tokens, customers, orders, order_items, warehouses, packages, tracking_events, payments.

Bỏ khỏi thiết kế database mới: VIP, CSKH, đánh giá, kế hoạch doanh số, quyền thương hiệu và catalog độc lập. Mặt hàng được lưu ngay trong chi tiết đơn.

**Theo yêu cầu mới nhất, không triển khai code/API.** Code, Postman và cấu hình ứng dụng đã được khôi phục về bản trước; ứng dụng vẫn dùng database cũ. Bạn sẽ tự thực hành chỉnh code để kết nối schema mới sau.

Database cũ và dữ liệu minh chứng được giữ nguyên. Dữ liệu mới chỉ có 5 tài khoản thực hành và 2 kho mẫu; chưa chuyển khách hàng/giao dịch cũ sang.

- SQL: [../sql/logistics_core/](../sql/logistics_core/)
- Chi tiết bảng/trường: [DB_LOGISTICS_GON.md](DB_LOGISTICS_GON.md)
- Câu lệnh xem database: [xem-db-logistics.sql](xem-db-logistics.sql)
