USE cms_logistics_core;
DELIMITER $$
DROP PROCEDURE IF EXISTS sp_create_session$$
CREATE PROCEDURE sp_create_session(IN p_user_id BIGINT, IN p_jti VARCHAR(64), IN p_expires DATETIME(6))
BEGIN
    DECLARE v_status VARCHAR(20);
    SELECT status INTO v_status FROM users WHERE id=p_user_id FOR UPDATE;
    IF v_status IS NULL OR v_status <> 'ACTIVE' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ACCOUNT_INACTIVE';
    END IF;
    INSERT INTO refresh_tokens(user_id,jti,expires_at) VALUES(p_user_id,p_jti,p_expires);
    UPDATE users SET last_login_at=UTC_TIMESTAMP(6) WHERE id=p_user_id;
    SELECT id,username,full_name,role,status FROM users WHERE id=p_user_id;
END$$
DROP PROCEDURE IF EXISTS sp_rotate_refresh$$
CREATE PROCEDURE sp_rotate_refresh(IN p_user_id BIGINT, IN p_old_jti VARCHAR(64),
    IN p_new_jti VARCHAR(64), IN p_expires DATETIME(6))
BEGIN
    DECLARE v_status VARCHAR(20);
    -- Khóa tài khoản trước: hai request refresh không thể dùng cùng token thành công.
    SELECT status INTO v_status FROM users WHERE id=p_user_id FOR UPDATE;
    IF v_status IS NULL OR v_status <> 'ACTIVE' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_REFRESH';
    END IF;
    UPDATE refresh_tokens SET revoked_at=UTC_TIMESTAMP(6)
    WHERE user_id=p_user_id AND jti=p_old_jti AND revoked_at IS NULL
          AND expires_at > UTC_TIMESTAMP(6);
    IF ROW_COUNT() <> 1 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_REFRESH';
    END IF;
    INSERT INTO refresh_tokens(user_id,jti,expires_at) VALUES(p_user_id,p_new_jti,p_expires);
    SELECT id,username,full_name,role,status FROM users WHERE id=p_user_id;
END$$
DROP PROCEDURE IF EXISTS sp_logout_session$$
CREATE PROCEDURE sp_logout_session(IN p_user_id BIGINT, IN p_jti VARCHAR(64))
BEGIN
    UPDATE refresh_tokens SET revoked_at=UTC_TIMESTAMP(6)
    WHERE user_id=p_user_id AND jti=p_jti AND revoked_at IS NULL;
END$$
DELIMITER ;
