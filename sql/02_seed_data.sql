-- MySQL 8.0.16+ / InnoDB. Timestamps stored in UTC.
SET time_zone = '+00:00';

INSERT INTO roles (code, name, description) VALUES
    ('ADMIN',      'Admin',              'Toàn quyền hệ thống; cấu hình tỷ giá, biểu phí, danh mục dùng chung'),
    ('SALE',       'Sale / CSKH',        'Quản lý khách hàng phụ trách, đơn hàng, khiếu nại, kế hoạch doanh số'),
    ('WAREHOUSE',  'Nhân viên Kho',      'Quét mã vạch nhập/xuất kho TQ và VN, cân đo kiện hàng'),
    ('ACCOUNTANT', 'Kế toán',            'Theo dõi dòng tiền, công nợ, hóa đơn'),
    ('CUSTOMER',   'Khách hàng',         'Tạo yêu cầu đặt hàng, đặt cọc, theo dõi đơn hàng'),
    ('PURCHASER',  'Nhân viên Đặt hàng', 'Đặt mua hàng trên sàn TMĐT Trung Quốc, cập nhật MVĐ nội địa TQ')
ON DUPLICATE KEY UPDATE id = id;

INSERT INTO exchange_rates (currency_code, rate, note)
SELECT v.currency_code, v.rate, 'Tỷ giá khởi tạo (seed)'
FROM (SELECT 'CNY' AS currency_code, 3920.0000 AS rate
UNION ALL SELECT 'USD', 26500.0000) AS v
WHERE NOT EXISTS (SELECT 1 FROM exchange_rates);

INSERT INTO fee_configs (fee_type, description, value, unit, tier_min, tier_max)
SELECT * FROM (SELECT 'PURCHASE_SERVICE_FEE' AS fee_type, 'Đơn dưới 10 triệu' AS description, 3.0000 AS value, 'PERCENT' AS unit, 0 AS tier_min, 10000000 AS tier_max
UNION ALL SELECT 'PURCHASE_SERVICE_FEE', 'Đơn từ 10 - dưới 50 triệu', 2.0000, 'PERCENT', 10000000, 50000000
UNION ALL SELECT 'PURCHASE_SERVICE_FEE', 'Đơn từ 50 triệu', 1.0000, 'PERCENT', 50000000, NULL
UNION ALL SELECT 'INTL_SHIPPING_FEE', 'Dưới 100 kg', 25000.0000, 'VND_PER_KG', 0, 100
UNION ALL SELECT 'INTL_SHIPPING_FEE', 'Từ 100 - dưới 500 kg', 22000.0000, 'VND_PER_KG', 100, 500
UNION ALL SELECT 'INTL_SHIPPING_FEE', 'Từ 500 kg', 20000.0000, 'VND_PER_KG', 500, NULL
UNION ALL SELECT 'INTL_SHIPPING_FEE', 'Hàng cồng kềnh tính theo m3', 4000000.0000, 'VND_PER_M3', NULL, NULL
UNION ALL SELECT 'INSPECTION_FEE', 'Kiểm đếm cơ bản', 1000.0000, 'VND_PER_ITEM', NULL, NULL
UNION ALL SELECT 'WOODEN_CRATE_FEE', 'Đóng gỗ', 150000.0000, 'VND_PER_PACKAGE', NULL, NULL) AS v
WHERE NOT EXISTS (SELECT 1 FROM fee_configs);
