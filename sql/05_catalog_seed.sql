-- Danh mục khởi tạo. Thêm/sửa qua API, không cần sửa mã nguồn.
BEGIN;
INSERT INTO countries (code, name) VALUES ('CN', 'Trung Quốc'), ('VN', 'Việt Nam')
ON CONFLICT DO NOTHING;
INSERT INTO units (code, name) VALUES
    ('KG', 'Kilogram'), ('M3', 'Mét khối'), ('ITEM', 'Cái'), ('BOX', 'Thùng')
ON CONFLICT DO NOTHING;
INSERT INTO package_types (code, name) VALUES
    ('CARTON', 'Thùng carton'), ('PALLET', 'Pallet'), ('BAG', 'Bao')
ON CONFLICT DO NOTHING;
INSERT INTO categories (code, name) VALUES
    ('GENERAL', 'Hàng tổng hợp')
ON CONFLICT DO NOTHING;
COMMIT;
