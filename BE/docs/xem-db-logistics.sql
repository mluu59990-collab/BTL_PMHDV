-- Mở trong MySQL Workbench, dùng kết nối MySQL local cổng 3306.
-- Chỉ đọc; có thể chạy từng đoạn để chụp minh chứng schema mới.
USE cms_logistics_core;
SHOW TABLES;

SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = 'cms_logistics_core'
ORDER BY TABLE_NAME, ORDINAL_POSITION;

SELECT id, username, full_name, role, status FROM users;
SELECT id, code, name, address, country_code, is_active FROM warehouses;

-- Không có đơn/khách/giao dịch seed giả; bạn sẽ tự thực hành code/API sau.
SELECT * FROM customers;
SELECT * FROM orders;
SELECT * FROM order_items;
SELECT * FROM packages;
SELECT * FROM tracking_events;
SELECT * FROM payments;
