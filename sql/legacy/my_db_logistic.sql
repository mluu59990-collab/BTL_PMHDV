-- Chạy toàn bộ file trong MySQL Workbench để tạo database logistics và dữ liệu dev.

-- Database mới cho phần thực hành logistics; giữ nguyên database cũ.
CREATE DATABASE IF NOT EXISTS cms_logistics_core
CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE cms_logistics_core;


USE cms_logistics_core;

-- Logistics cốt lõi: 9 bảng, MySQL 8.0.16+ / InnoDB.
-- Chỉ áp dụng vào database mới. Không DROP hoặc sửa database Buổi 1–3.
SET time_zone = '+00:00';

CREATE TABLE IF NOT EXISTS users (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 username VARCHAR(50) NOT NULL UNIQUE,
 email VARCHAR(255) UNIQUE,
 full_name VARCHAR(150) NOT NULL,
 phone VARCHAR(20),
 password_hash VARCHAR(255) NOT NULL,
 role VARCHAR(20) NOT NULL CHECK (role IN ('ADMIN','SALE','WAREHOUSE','ACCOUNTANT','CUSTOMER')),
 status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','INACTIVE','LOCKED')),
 last_login_at DATETIME(6),
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS refresh_tokens (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 user_id BIGINT NOT NULL,
 jti VARCHAR(64) NOT NULL UNIQUE,
 expires_at DATETIME(6) NOT NULL,
 revoked_at DATETIME(6),
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS customers (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 user_id BIGINT UNIQUE,
 name VARCHAR(150) NOT NULL,
 phone VARCHAR(20) NOT NULL,
 email VARCHAR(255),
 address VARCHAR(500) NOT NULL,
 assigned_staff_id BIGINT,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 FOREIGN KEY (user_id) REFERENCES users(id),
 FOREIGN KEY (assigned_staff_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS warehouses (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 code VARCHAR(30) NOT NULL UNIQUE,
 name VARCHAR(150) NOT NULL,
 address VARCHAR(500) NOT NULL,
 country_code VARCHAR(2) NOT NULL CHECK (country_code IN ('CN','VN')),
 is_active BOOLEAN NOT NULL DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS orders (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 order_code VARCHAR(40) NOT NULL UNIQUE,
 customer_id BIGINT NOT NULL,
 created_by BIGINT NOT NULL,
 receiver_name VARCHAR(150) NOT NULL,
 receiver_phone VARCHAR(20) NOT NULL,
 receiver_address VARCHAR(500) NOT NULL,
 shipping_fee DECIMAL(18,2) NOT NULL DEFAULT 0 CHECK (shipping_fee >= 0),
 status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','CONFIRMED','SHIPPING','DELIVERED','CANCELLED')),
 note VARCHAR(2000),
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 FOREIGN KEY (customer_id) REFERENCES customers(id),
 FOREIGN KEY (created_by) REFERENCES users(id),
 INDEX ix_orders_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS order_items (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 order_id BIGINT NOT NULL,
 product_name VARCHAR(255) NOT NULL,
 quantity INT NOT NULL CHECK (quantity > 0),
 note VARCHAR(2000),
 FOREIGN KEY (order_id) REFERENCES orders(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS packages (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 order_id BIGINT NOT NULL,
 tracking_code VARCHAR(50) NOT NULL UNIQUE,
 warehouse_id BIGINT,
 weight_kg DECIMAL(12,3) NOT NULL CHECK (weight_kg > 0),
 length_cm DECIMAL(10,2) NOT NULL CHECK (length_cm > 0),
 width_cm DECIMAL(10,2) NOT NULL CHECK (width_cm > 0),
 height_cm DECIMAL(10,2) NOT NULL CHECK (height_cm > 0),
 status VARCHAR(20) NOT NULL DEFAULT 'CREATED' CHECK (status IN ('CREATED','IN_WAREHOUSE','IN_TRANSIT','DELIVERED','CANCELLED')),
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 FOREIGN KEY (order_id) REFERENCES orders(id),
 FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
 CHECK ((status = 'IN_WAREHOUSE' AND warehouse_id IS NOT NULL) OR (status <> 'IN_WAREHOUSE' AND warehouse_id IS NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS tracking_events (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 package_id BIGINT NOT NULL,
 warehouse_id BIGINT,
 status VARCHAR(20) NOT NULL CHECK (status IN ('CREATED','IN_WAREHOUSE','IN_TRANSIT','DELIVERED','CANCELLED')),
 note VARCHAR(2000),
 created_by BIGINT NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 FOREIGN KEY (package_id) REFERENCES packages(id),
 FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
 FOREIGN KEY (created_by) REFERENCES users(id),
 INDEX ix_tracking_events_time (package_id, created_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS payments (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 order_id BIGINT NOT NULL,
 amount DECIMAL(18,2) NOT NULL CHECK (amount > 0),
 type VARCHAR(10) NOT NULL CHECK (type IN ('PAYMENT','REFUND')),
 method VARCHAR(20) NOT NULL CHECK (method IN ('CASH','BANK_TRANSFER')),
 reference_code VARCHAR(80) NOT NULL UNIQUE,
 created_by BIGINT NOT NULL,
 created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
 FOREIGN KEY (order_id) REFERENCES orders(id),
 FOREIGN KEY (created_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


USE cms_logistics_core;

-- Hai kho minh họa, không tạo đơn hoặc thanh toán giả.
INSERT INTO warehouses (code,name,address,country_code) VALUES
 ('CN01','Kho Trung Quốc','Địa chỉ mẫu kho Trung Quốc','CN'),
 ('VN01','Kho Việt Nam','Địa chỉ mẫu kho Việt Nam','VN')
ON DUPLICATE KEY UPDATE id=id;


USE cms_logistics_core;

-- DEV ONLY: admin / Admin@123456; other users / Test@123456
-- MySQL 8.0.16+ / InnoDB. Timestamps stored in UTC.
SET time_zone = '+00:00';

INSERT INTO users (username, email, full_name, phone, password_hash, role, status)
SELECT v.username, v.email, v.full_name, v.phone, v.password_hash, v.role_code, 'ACTIVE'
FROM (SELECT 'admin' AS username, 'admin@example.com' AS email, 'Quản trị viên' AS full_name, '0900000001' AS phone, '$argon2id$v=19$m=65536,t=3,p=4$fA3MH0p4CGhbElMDV2oUZg$QkORG4qYArzK6jh2cnbrOpIm2+EKGKfdo7c8SxmMJKU' AS password_hash, 'ADMIN' AS role_code
UNION ALL SELECT 'sale01', 'sale01@example.com', 'Nhân viên Sale 01', '0900000002', '$argon2id$v=19$m=65536,t=3,p=4$PAegmon5+AXpIt3dQSt6gA$rGVcJZERkqmKQVdTtKwz+IEY3AiIBU30VbCI0U21Dvc', 'SALE'
UNION ALL SELECT 'kho01', 'kho01@example.com', 'Nhân viên Kho 01', '0900000003', '$argon2id$v=19$m=65536,t=3,p=4$PAegmon5+AXpIt3dQSt6gA$rGVcJZERkqmKQVdTtKwz+IEY3AiIBU30VbCI0U21Dvc', 'WAREHOUSE'
UNION ALL SELECT 'ketoan01', 'ketoan01@example.com', 'Kế toán 01', '0900000004', '$argon2id$v=19$m=65536,t=3,p=4$PAegmon5+AXpIt3dQSt6gA$rGVcJZERkqmKQVdTtKwz+IEY3AiIBU30VbCI0U21Dvc', 'ACCOUNTANT'
UNION ALL SELECT 'khach01', 'khach01@example.com', 'Khách hàng 01', '0900000006', '$argon2id$v=19$m=65536,t=3,p=4$PAegmon5+AXpIt3dQSt6gA$rGVcJZERkqmKQVdTtKwz+IEY3AiIBU30VbCI0U21Dvc', 'CUSTOMER') AS v
ON DUPLICATE KEY UPDATE id = users.id;


-- Kiểm tra kết quả
SHOW TABLES;
SELECT id, username, full_name, role, status FROM users;
SELECT id, code, name, country_code FROM warehouses;
