-- Chạy toàn bộ trong Workbench. Chỉ cập nhật 4 thủ tục, không thay bảng/dữ liệu.
USE cms_logistics_core;
DELIMITER $$
DROP PROCEDURE IF EXISTS sp_health$$
CREATE PROCEDURE sp_health()
BEGIN
    SELECT 1 AS ok;
END$$
DROP PROCEDURE IF EXISTS sp_get_users$$
CREATE PROCEDURE sp_get_users()
BEGIN
    SELECT id, username, full_name, role, status FROM users ORDER BY id LIMIT 10;
END$$
DROP PROCEDURE IF EXISTS sp_get_user_for_login$$
CREATE PROCEDURE sp_get_user_for_login(IN p_username VARCHAR(50))
BEGIN
    SELECT id, username, full_name, password_hash, role, status
    FROM users WHERE username = p_username;
END$$
DROP PROCEDURE IF EXISTS sp_get_auth_user$$
CREATE PROCEDURE sp_get_auth_user(IN p_user_id BIGINT)
BEGIN
    SELECT id, username, full_name, role, status FROM users WHERE id = p_user_id;
END$$
DELIMITER ;

-- Đăng ký công khai luôn tạo CUSTOMER; không nhận vai trò từ client.
DELIMITER $$
DROP PROCEDURE IF EXISTS sp_register_user$$
CREATE PROCEDURE sp_register_user(IN p_username VARCHAR(50), IN p_email VARCHAR(255),
    IN p_full_name VARCHAR(150), IN p_phone VARCHAR(20), IN p_password_hash VARCHAR(255))
BEGIN
    INSERT INTO users(username,email,full_name,phone,password_hash,role,status)
    VALUES(p_username,p_email,p_full_name,p_phone,p_password_hash,'CUSTOMER','ACTIVE');
    SELECT id,username,full_name,role,status FROM users WHERE id=LAST_INSERT_ID();
END$$
DELIMITER ;
