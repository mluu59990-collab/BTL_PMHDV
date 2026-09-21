-- =====================================================================
-- SEED DỮ LIỆU NỀN (chạy lại nhiều lần không bị trùng)
-- =====================================================================

-- ---------- Vai trò ---------------------------------------------------
-- 5 vai trò theo Master Plan (1.2) + PURCHASER theo SRS B.2.2.
-- Không cần PURCHASER thì: DELETE FROM roles WHERE code = 'PURCHASER';
INSERT INTO roles (code, name, description) VALUES
    ('ADMIN',      'Admin',              'Toàn quyền hệ thống; cấu hình tỷ giá, biểu phí, danh mục dùng chung'),
    ('SALE',       'Sale / CSKH',        'Quản lý khách hàng phụ trách, đơn hàng, khiếu nại, kế hoạch doanh số'),
    ('WAREHOUSE',  'Nhân viên Kho',      'Quét mã vạch nhập/xuất kho TQ và VN, cân đo kiện hàng'),
    ('ACCOUNTANT', 'Kế toán',            'Theo dõi dòng tiền, công nợ, hóa đơn'),
    ('CUSTOMER',   'Khách hàng',         'Tạo yêu cầu đặt hàng, đặt cọc, theo dõi đơn hàng'),
    ('PURCHASER',  'Nhân viên Đặt hàng', 'Đặt mua hàng trên sàn TMĐT Trung Quốc, cập nhật MVĐ nội địa TQ')
ON CONFLICT (code) DO NOTHING;

-- ---------- Tỷ giá khởi tạo (số ví dụ trong SRS REQ-1.2) --------------
INSERT INTO exchange_rates (currency_code, rate, note)
SELECT v.currency_code, v.rate, 'Tỷ giá khởi tạo (seed)'
FROM (VALUES ('CNY', 3920.0000), ('USD', 26500.0000)) AS v(currency_code, rate)
WHERE NOT EXISTS (SELECT 1 FROM exchange_rates);

-- ---------- Thang bảng phí MẪU ----------------------------------------
-- !!! SỐ LIỆU DƯỚI ĐÂY CHỈ LÀ VÍ DỤ ĐỂ TEST - sửa lại theo biểu phí thực tế
--     (qua API PATCH /fee-configs/{id} hoặc UPDATE trực tiếp) !!!
INSERT INTO fee_configs (fee_type, description, value, unit, tier_min, tier_max)
SELECT * FROM (VALUES
    -- Phí mua hàng (%) theo giá trị đơn (VNĐ)
    ('PURCHASE_SERVICE_FEE', 'Đơn dưới 10 triệu',        3.0000, 'PERCENT',          0::numeric,          10000000::numeric),
    ('PURCHASE_SERVICE_FEE', 'Đơn từ 10 - dưới 50 triệu', 2.0000, 'PERCENT',   10000000::numeric,          50000000::numeric),
    ('PURCHASE_SERVICE_FEE', 'Đơn từ 50 triệu',          1.0000, 'PERCENT',   50000000::numeric,                    NULL),
    -- Phí vận chuyển quốc tế (đ/kg) theo cân nặng tính phí (kg)
    ('INTL_SHIPPING_FEE',    'Dưới 100 kg',          25000.0000, 'VND_PER_KG',         0::numeric,            100::numeric),
    ('INTL_SHIPPING_FEE',    'Từ 100 - dưới 500 kg', 22000.0000, 'VND_PER_KG',       100::numeric,            500::numeric),
    ('INTL_SHIPPING_FEE',    'Từ 500 kg',            20000.0000, 'VND_PER_KG',       500::numeric,                  NULL),
    -- Phí vận chuyển quốc tế theo khối (đ/m3)
    ('INTL_SHIPPING_FEE',    'Hàng cồng kềnh tính theo m3', 4000000.0000, 'VND_PER_M3', NULL,                       NULL),
    -- Phí kiểm đếm (đ/sản phẩm) và phí đóng gỗ (đ/kiện)
    ('INSPECTION_FEE',       'Kiểm đếm cơ bản',          1000.0000, 'VND_PER_ITEM',    NULL,                       NULL),
    ('WOODEN_CRATE_FEE',     'Đóng gỗ',                150000.0000, 'VND_PER_PACKAGE', NULL,                       NULL)
) AS v(fee_type, description, value, unit, tier_min, tier_max)
WHERE NOT EXISTS (SELECT 1 FROM fee_configs);
