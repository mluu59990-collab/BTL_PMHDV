-- Dữ liệu thực hành: mỗi lần chạy thêm 10 dòng vào từng bảng (90 dòng).
-- Chạy toàn bộ file trong cùng một tab/kết nối sau khi tạo schema.
USE cms_logistics_core;
SET NAMES utf8mb4;
SET time_zone = '+00:00';
SET @batch = LEFT(REPLACE(UUID(), '-', ''), 20);
-- Hash Argon2id của mật khẩu thực hành Test@123456.
SET @password_hash = '$argon2id$v=19$m=65536,t=3,p=4$PAegmon5+AXpIt3dQSt6gA$rGVcJZERkqmKQVdTtKwz+IEY3AiIBU30VbCI0U21Dvc';

DROP TEMPORARY TABLE IF EXISTS demo_rows;
CREATE TEMPORARY TABLE demo_rows (
    n INT PRIMARY KEY,
    person_name VARCHAR(150),
    product_name VARCHAR(255)
);
INSERT INTO demo_rows VALUES
(1, 'Nguyễn Văn An', 'Áo thun'),
(2, 'Trần Thị Bình', 'Quần jeans'),
(3, 'Lê Minh Châu', 'Giày thể thao'),
(4, 'Phạm Ngọc Dung', 'Balo'),
(5, 'Hoàng Đức Duy', 'Túi xách'),
(6, 'Vũ Thu Hà', 'Đồng hồ'),
(7, 'Đặng Gia Huy', 'Đèn bàn'),
(8, 'Bùi Khánh Linh', 'Bình giữ nhiệt'),
(9, 'Đỗ Quang Minh', 'Ốp điện thoại'),
(10, 'Hồ Bảo Ngọc', 'Tai nghe');

START TRANSACTION;

-- 1. Tài khoản: 1 ADMIN, 1 SALE, 8 CUSTOMER.
INSERT INTO users (username, email, full_name, phone, password_hash, role)
SELECT CONCAT('demo_', @batch, '_', n),
       CONCAT('demo_', @batch, '_', n, '@example.com'),
       person_name, CONCAT('09000000', LPAD(n, 2, '0')), @password_hash,
       CASE n WHEN 1 THEN 'ADMIN' WHEN 2 THEN 'SALE' ELSE 'CUSTOMER' END
FROM demo_rows;

SET @admin_id = (SELECT id FROM users WHERE username = CONCAT('demo_', @batch, '_1'));
SET @sale_id = (SELECT id FROM users WHERE username = CONCAT('demo_', @batch, '_2'));

-- 2. Token minh họa đã thu hồi, không phải phiên đăng nhập thật.
INSERT INTO refresh_tokens (user_id, jti, expires_at, revoked_at)
SELECT u.id, CONCAT('demo_', @batch, '_', d.n),
       UTC_TIMESTAMP(6) + INTERVAL 7 DAY, UTC_TIMESTAMP(6)
FROM demo_rows d
JOIN users u ON u.username = CONCAT('demo_', @batch, '_', d.n);

-- 3. Hai khách đầu chưa có tài khoản; tám khách sau liên kết CUSTOMER.
INSERT INTO customers (user_id, name, phone, email, address, assigned_staff_id)
SELECT CASE WHEN d.n > 2 THEN u.id ELSE NULL END,
       d.person_name, u.phone, u.email,
       CONCAT('Số ', d.n, ' đường Nguyễn Trãi, Hà Nội'), @sale_id
FROM demo_rows d
JOIN users u ON u.username = CONCAT('demo_', @batch, '_', d.n);

-- 4. Năm kho Trung Quốc, năm kho Việt Nam.
INSERT INTO warehouses (code, name, address, country_code)
SELECT CONCAT('W', @batch, '_', n), CONCAT('Kho mẫu ', n),
       CASE WHEN n <= 5 THEN CONCAT('Địa chỉ mẫu ', n, ', Quảng Châu')
            ELSE CONCAT('Địa chỉ mẫu ', n, ', Hà Nội') END,
       CASE WHEN n <= 5 THEN 'CN' ELSE 'VN' END
FROM demo_rows;

-- 5. Đơn hàng đã xác nhận.
INSERT INTO orders (order_code, customer_id, created_by, receiver_name,
                    receiver_phone, receiver_address, shipping_fee, status, note)
SELECT CONCAT('O', @batch, '_', d.n), c.id, @admin_id,
       c.name, c.phone, c.address, 100000 + d.n * 10000, 'CONFIRMED', 'Đơn thực hành'
FROM demo_rows d
JOIN customers c ON c.email = CONCAT('demo_', @batch, '_', d.n, '@example.com');

-- 6. Mỗi đơn một loại mặt hàng.
INSERT INTO order_items (order_id, product_name, quantity, note)
SELECT o.id, d.product_name, d.n, 'Hàng mẫu'
FROM demo_rows d
JOIN orders o ON o.order_code = CONCAT('O', @batch, '_', d.n);

-- 7. Mỗi đơn một kiện đang ở kho.
INSERT INTO packages (order_id, tracking_code, warehouse_id, weight_kg,
                      length_cm, width_cm, height_cm, status)
SELECT o.id, CONCAT('P', @batch, '_', d.n), w.id,
       1 + d.n * 0.5, 30 + d.n, 20 + d.n, 10 + d.n, 'IN_WAREHOUSE'
FROM demo_rows d
JOIN orders o ON o.order_code = CONCAT('O', @batch, '_', d.n)
JOIN warehouses w ON w.code = CONCAT('W', @batch, '_', d.n);

-- 8. Mốc đầu tiên ghi nhận kiện tại kho.
INSERT INTO tracking_events (package_id, warehouse_id, status, note, created_by)
SELECT p.id, p.warehouse_id, 'IN_WAREHOUSE', 'Tiếp nhận kiện tại kho', @admin_id
FROM demo_rows d
JOIN packages p ON p.tracking_code = CONCAT('P', @batch, '_', d.n);

-- 9. Mỗi đơn thanh toán trước 50% phí vận chuyển.
INSERT INTO payments (order_id, amount, type, method, reference_code, created_by)
SELECT o.id, o.shipping_fee / 2, 'PAYMENT',
       CASE WHEN MOD(d.n, 2) = 0 THEN 'BANK_TRANSFER' ELSE 'CASH' END,
       CONCAT('PAY', @batch, '_', d.n), @admin_id
FROM demo_rows d
JOIN orders o ON o.order_code = CONCAT('O', @batch, '_', d.n);

COMMIT;

-- Đếm riêng dữ liệu vừa thêm: mỗi bảng phải có 10 dòng.
SELECT 'users' AS table_name, COUNT(*) AS inserted_rows FROM users
WHERE username LIKE CONCAT('demo!_', @batch, '!_%') ESCAPE '!'
UNION ALL SELECT 'refresh_tokens', COUNT(*) FROM refresh_tokens
WHERE jti LIKE CONCAT('demo!_', @batch, '!_%') ESCAPE '!'
UNION ALL SELECT 'customers', COUNT(*) FROM customers
WHERE email LIKE CONCAT('demo!_', @batch, '!_%') ESCAPE '!'
UNION ALL SELECT 'warehouses', COUNT(*) FROM warehouses
WHERE code LIKE CONCAT('W', @batch, '!_%') ESCAPE '!'
UNION ALL SELECT 'orders', COUNT(*) FROM orders
WHERE order_code LIKE CONCAT('O', @batch, '!_%') ESCAPE '!'
UNION ALL SELECT 'order_items', COUNT(*) FROM order_items i
JOIN orders o ON o.id = i.order_id
WHERE o.order_code LIKE CONCAT('O', @batch, '!_%') ESCAPE '!'
UNION ALL SELECT 'packages', COUNT(*) FROM packages
WHERE tracking_code LIKE CONCAT('P', @batch, '!_%') ESCAPE '!'
UNION ALL SELECT 'tracking_events', COUNT(*) FROM tracking_events t
JOIN packages p ON p.id = t.package_id
WHERE p.tracking_code LIKE CONCAT('P', @batch, '!_%') ESCAPE '!'
UNION ALL SELECT 'payments', COUNT(*) FROM payments
WHERE reference_code LIKE CONCAT('PAY', @batch, '!_%') ESCAPE '!';

DROP TEMPORARY TABLE demo_rows;
