-- DEV ONLY: admin / Admin@123456; other users / Test@123456
-- MySQL 8.0.16+ / InnoDB. Timestamps stored in UTC.
SET time_zone = '+00:00';

INSERT INTO users (username, email, full_name, phone, password_hash, role_id, status)
SELECT v.username, v.email, v.full_name, v.phone, v.password_hash, r.id, 'ACTIVE'
FROM (SELECT 'admin' AS username, 'admin@example.com' AS email, 'Quản trị viên' AS full_name, '0900000001' AS phone, '$argon2id$v=19$m=65536,t=3,p=4$fA3MH0p4CGhbElMDV2oUZg$QkORG4qYArzK6jh2cnbrOpIm2+EKGKfdo7c8SxmMJKU' AS password_hash, 'ADMIN' AS role_code
UNION ALL SELECT 'sale01', 'sale01@example.com', 'Nhân viên Sale 01', '0900000002', '$argon2id$v=19$m=65536,t=3,p=4$PAegmon5+AXpIt3dQSt6gA$rGVcJZERkqmKQVdTtKwz+IEY3AiIBU30VbCI0U21Dvc', 'SALE'
UNION ALL SELECT 'kho01', 'kho01@example.com', 'Nhân viên Kho 01', '0900000003', '$argon2id$v=19$m=65536,t=3,p=4$PAegmon5+AXpIt3dQSt6gA$rGVcJZERkqmKQVdTtKwz+IEY3AiIBU30VbCI0U21Dvc', 'WAREHOUSE'
UNION ALL SELECT 'ketoan01', 'ketoan01@example.com', 'Kế toán 01', '0900000004', '$argon2id$v=19$m=65536,t=3,p=4$PAegmon5+AXpIt3dQSt6gA$rGVcJZERkqmKQVdTtKwz+IEY3AiIBU30VbCI0U21Dvc', 'ACCOUNTANT'
UNION ALL SELECT 'muahang01', 'muahang01@example.com', 'Nhân viên Đặt hàng 01', '0900000005', '$argon2id$v=19$m=65536,t=3,p=4$PAegmon5+AXpIt3dQSt6gA$rGVcJZERkqmKQVdTtKwz+IEY3AiIBU30VbCI0U21Dvc', 'PURCHASER'
UNION ALL SELECT 'khach01', 'khach01@example.com', 'Khách hàng 01', '0900000006', '$argon2id$v=19$m=65536,t=3,p=4$PAegmon5+AXpIt3dQSt6gA$rGVcJZERkqmKQVdTtKwz+IEY3AiIBU30VbCI0U21Dvc', 'CUSTOMER') AS v
JOIN roles r ON r.code = v.role_code
ON DUPLICATE KEY UPDATE id = users.id;
