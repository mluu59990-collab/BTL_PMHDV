USE cms_logistics_core;
CREATE TABLE IF NOT EXISTS config_locks (name VARCHAR(50) PRIMARY KEY)
ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT INTO config_locks(name) VALUES('USER_PERMISSIONS')
ON DUPLICATE KEY UPDATE name=config_locks.name;
DELIMITER $$
DROP PROCEDURE IF EXISTS sp_get_users_page$$
CREATE PROCEDURE sp_get_users_page(IN p_limit INT, IN p_offset INT)
BEGIN
    SELECT id,username,full_name,role,status FROM users ORDER BY id LIMIT p_limit OFFSET p_offset;
END$$
DROP PROCEDURE IF EXISTS sp_update_user_access$$
CREATE PROCEDURE sp_update_user_access(IN p_actor BIGINT, IN p_id BIGINT,
    IN p_role VARCHAR(20), IN p_status VARCHAR(20))
BEGIN
    DECLARE v_lock VARCHAR(50);
    DECLARE v_actor_role VARCHAR(20);
    DECLARE v_actor_status VARCHAR(20);
    DECLARE v_role VARCHAR(20);
    DECLARE v_status VARCHAR(20);
    DECLARE v_count INT;
    -- Tuần tự hóa thay đổi quyền: không thể vô hiệu hóa đồng thời mọi ADMIN.
    SELECT name INTO v_lock FROM config_locks WHERE name='USER_PERMISSIONS' FOR UPDATE;
    SELECT role,status INTO v_actor_role,v_actor_status FROM users WHERE id=p_actor FOR UPDATE;
    IF v_actor_role <> 'ADMIN' OR v_actor_status <> 'ACTIVE' OR v_actor_role IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='FORBIDDEN';
    END IF;
    SELECT role,status INTO v_role,v_status FROM users WHERE id=p_id FOR UPDATE;
    IF v_role IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='NOT_FOUND'; END IF;
    IF v_role='ADMIN' AND v_status='ACTIVE' AND
       (COALESCE(p_role,v_role)<>'ADMIN' OR COALESCE(p_status,v_status)<>'ACTIVE') THEN
        SELECT COUNT(*) INTO v_count FROM users WHERE role='ADMIN' AND status='ACTIVE';
        IF v_count <= 1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='LAST_ADMIN'; END IF;
    END IF;
    UPDATE users SET role=COALESCE(p_role,role),status=COALESCE(p_status,status),updated_at=UTC_TIMESTAMP(6) WHERE id=p_id;
    IF (p_role IS NOT NULL AND p_role<>v_role) OR (p_status IS NOT NULL AND p_status<>v_status) THEN
        UPDATE refresh_tokens SET revoked_at=UTC_TIMESTAMP(6) WHERE user_id=p_id AND revoked_at IS NULL;
    END IF;
    SELECT id,username,full_name,role,status FROM users WHERE id=p_id;
END$$
DELIMITER ;
