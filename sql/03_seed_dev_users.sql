-- =====================================================================
-- TÀI KHOẢN DEV - CHỈ DÙNG KHI PHÁT TRIỂN/TEST. KHÔNG chạy file này ở production!
--   admin                          / Admin@123456
--   sale01, kho01, ketoan01,
--   muahang01, khach01             / Test@123456
-- (mật khẩu đã hash Argon2id; đổi mật khẩu qua API POST /users/me/change-password)
-- =====================================================================
INSERT INTO users (username, email, full_name, phone, password_hash, role_id, status)
SELECT v.username, v.email, v.full_name, v.phone, v.password_hash, r.id, 'ACTIVE'
FROM (VALUES
    ('admin',     'admin@example.com',     'Quản trị viên',     '0900000001', '$argon2id$v=19$m=65536,t=3,p=4$fA3MH0p4CGhbElMDV2oUZg$QkORG4qYArzK6jh2cnbrOpIm2+EKGKfdo7c8SxmMJKU', 'ADMIN'),
    ('sale01',    'sale01@example.com',    'Nhân viên Sale 01', '0900000002', '$argon2id$v=19$m=65536,t=3,p=4$PAegmon5+AXpIt3dQSt6gA$rGVcJZERkqmKQVdTtKwz+IEY3AiIBU30VbCI0U21Dvc', 'SALE'),
    ('kho01',     'kho01@example.com',     'Nhân viên Kho 01',  '0900000003', '$argon2id$v=19$m=65536,t=3,p=4$PAegmon5+AXpIt3dQSt6gA$rGVcJZERkqmKQVdTtKwz+IEY3AiIBU30VbCI0U21Dvc', 'WAREHOUSE'),
    ('ketoan01',  'ketoan01@example.com',  'Kế toán 01',        '0900000004', '$argon2id$v=19$m=65536,t=3,p=4$PAegmon5+AXpIt3dQSt6gA$rGVcJZERkqmKQVdTtKwz+IEY3AiIBU30VbCI0U21Dvc', 'ACCOUNTANT'),
    ('muahang01', 'muahang01@example.com', 'Nhân viên Đặt hàng 01', '0900000005', '$argon2id$v=19$m=65536,t=3,p=4$PAegmon5+AXpIt3dQSt6gA$rGVcJZERkqmKQVdTtKwz+IEY3AiIBU30VbCI0U21Dvc', 'PURCHASER'),
    ('khach01',   'khach01@example.com',   'Khách hàng 01',     '0900000006', '$argon2id$v=19$m=65536,t=3,p=4$PAegmon5+AXpIt3dQSt6gA$rGVcJZERkqmKQVdTtKwz+IEY3AiIBU30VbCI0U21Dvc', 'CUSTOMER')
) AS v(username, email, full_name, phone, password_hash, role_code)
JOIN roles r ON r.code = v.role_code
ON CONFLICT DO NOTHING;
