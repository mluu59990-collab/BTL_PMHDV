-- MySQL 8.0.16+ / InnoDB. Timestamps stored in UTC.
SET time_zone = '+00:00';

START TRANSACTION;
INSERT INTO countries (code, name) VALUES ('CN', 'Trung Quốc'), ('VN', 'Việt Nam')
ON DUPLICATE KEY UPDATE id = id;
INSERT INTO units (code, name) VALUES
    ('KG', 'Kilogram'), ('M3', 'Mét khối'), ('ITEM', 'Cái'), ('BOX', 'Thùng')
ON DUPLICATE KEY UPDATE id = id;
INSERT INTO package_types (code, name) VALUES
    ('CARTON', 'Thùng carton'), ('PALLET', 'Pallet'), ('BAG', 'Bao')
ON DUPLICATE KEY UPDATE id = id;
INSERT INTO categories (code, name) VALUES
    ('GENERAL', 'Hàng tổng hợp')
ON DUPLICATE KEY UPDATE id = id;
COMMIT;
