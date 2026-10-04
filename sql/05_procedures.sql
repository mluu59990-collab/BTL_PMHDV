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
