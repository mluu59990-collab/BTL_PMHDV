-- API cms_logistics: chỉ tạo stored procedure, giữ nguyên 10 bảng và dữ liệu.
-- Chạy toàn bộ trong MySQL Workbench.
USE cms_logistics;
DELIMITER $$
DROP PROCEDURE IF EXISTS sp_health$$
CREATE PROCEDURE sp_health()
BEGIN
    SELECT COUNT(*) AS user_count FROM nguoi_dung;
END$$
DROP PROCEDURE IF EXISTS sp_get_users$$
CREATE PROCEDURE sp_get_users()
BEGIN
    SELECT ma AS id, ten_dang_nhap AS username, ho_ten AS full_name, vai_tro AS role, trang_thai AS status FROM nguoi_dung ORDER BY ma LIMIT 10;
END$$
DROP PROCEDURE IF EXISTS sp_get_user_for_login$$
CREATE PROCEDURE sp_get_user_for_login(IN p_username VARCHAR(50))
BEGIN
    SELECT ma AS id, ten_dang_nhap AS username, ho_ten AS full_name, mat_khau_bam AS password_hash, vai_tro AS role, trang_thai AS status
    FROM nguoi_dung WHERE ten_dang_nhap = p_username;
END$$
DROP PROCEDURE IF EXISTS sp_get_auth_user$$
CREATE PROCEDURE sp_get_auth_user(IN p_user_id BIGINT)
BEGIN
    SELECT ma AS id, ten_dang_nhap AS username, ho_ten AS full_name, vai_tro AS role, trang_thai AS status FROM nguoi_dung WHERE ma = p_user_id;
END$$
DELIMITER ;

-- Đăng ký công khai luôn tạo CUSTOMER; không nhận vai trò từ client.
DELIMITER $$
DROP PROCEDURE IF EXISTS sp_register_user$$
CREATE PROCEDURE sp_register_user(IN p_username VARCHAR(50), IN p_email VARCHAR(255),
    IN p_full_name VARCHAR(150), IN p_phone VARCHAR(20), IN p_password_hash VARCHAR(255))
BEGIN
    INSERT INTO nguoi_dung(ten_dang_nhap,email,ho_ten,so_dien_thoai,mat_khau_bam,vai_tro,trang_thai)
    VALUES(p_username,p_email,p_full_name,p_phone,p_password_hash,'CUSTOMER','ACTIVE');
    SELECT ma AS id, ten_dang_nhap AS username, ho_ten AS full_name, vai_tro AS role, trang_thai AS status FROM nguoi_dung WHERE ma=LAST_INSERT_ID();
END$$
DELIMITER ;

USE cms_logistics;
DELIMITER $$
DROP PROCEDURE IF EXISTS sp_create_session$$
CREATE PROCEDURE sp_create_session(IN p_user_id BIGINT, IN p_jti VARCHAR(64), IN p_expires DATETIME(6))
BEGIN
    DECLARE v_status VARCHAR(20);
    SELECT trang_thai INTO v_status FROM nguoi_dung WHERE ma=p_user_id FOR UPDATE;
    IF v_status IS NULL OR v_status <> 'ACTIVE' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ACCOUNT_INACTIVE';
    END IF;
    INSERT INTO ma_lam_moi(ma_nguoi_dung,ma_dinh_danh_token,ngay_het_han) VALUES(p_user_id,p_jti,p_expires);
    UPDATE nguoi_dung SET lan_dang_nhap_cuoi=UTC_TIMESTAMP(6) WHERE ma=p_user_id;
    SELECT ma AS id, ten_dang_nhap AS username, ho_ten AS full_name, vai_tro AS role, trang_thai AS status FROM nguoi_dung WHERE ma=p_user_id;
END$$
DROP PROCEDURE IF EXISTS sp_rotate_refresh$$
CREATE PROCEDURE sp_rotate_refresh(IN p_user_id BIGINT, IN p_old_jti VARCHAR(64),
    IN p_new_jti VARCHAR(64), IN p_expires DATETIME(6))
BEGIN
    DECLARE v_status VARCHAR(20);
    -- Khóa tài khoản trước: hai request refresh không thể dùng cùng token thành công.
    SELECT trang_thai INTO v_status FROM nguoi_dung WHERE ma=p_user_id FOR UPDATE;
    IF v_status IS NULL OR v_status <> 'ACTIVE' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_REFRESH';
    END IF;
    UPDATE ma_lam_moi SET ngay_thu_hoi=UTC_TIMESTAMP(6)
    WHERE ma_nguoi_dung=p_user_id AND ma_dinh_danh_token=p_old_jti AND ngay_thu_hoi IS NULL
          AND ngay_het_han > UTC_TIMESTAMP(6);
    IF ROW_COUNT() <> 1 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_REFRESH';
    END IF;
    INSERT INTO ma_lam_moi(ma_nguoi_dung,ma_dinh_danh_token,ngay_het_han) VALUES(p_user_id,p_new_jti,p_expires);
    SELECT ma AS id, ten_dang_nhap AS username, ho_ten AS full_name, vai_tro AS role, trang_thai AS status FROM nguoi_dung WHERE ma=p_user_id;
END$$
DROP PROCEDURE IF EXISTS sp_logout_session$$
CREATE PROCEDURE sp_logout_session(IN p_user_id BIGINT, IN p_jti VARCHAR(64))
BEGIN
    UPDATE ma_lam_moi SET ngay_thu_hoi=UTC_TIMESTAMP(6)
    WHERE ma_nguoi_dung=p_user_id AND ma_dinh_danh_token=p_jti AND ngay_thu_hoi IS NULL;
END$$
DELIMITER ;

USE cms_logistics;
DELIMITER $$
DROP PROCEDURE IF EXISTS sp_get_users_page$$
CREATE PROCEDURE sp_get_users_page(IN p_limit INT, IN p_offset INT)
BEGIN
    SELECT ma AS id, ten_dang_nhap AS username, ho_ten AS full_name, vai_tro AS role, trang_thai AS status FROM nguoi_dung ORDER BY ma LIMIT p_limit OFFSET p_offset;
END$$
DROP PROCEDURE IF EXISTS sp_update_user_access$$
CREATE PROCEDURE sp_update_user_access(IN p_actor BIGINT, IN p_id BIGINT,
    IN p_role VARCHAR(20), IN p_status VARCHAR(20))
BEGIN
    DECLARE v_lock BIGINT;
    DECLARE v_actor_role VARCHAR(20);
    DECLARE v_actor_status VARCHAR(20);
    DECLARE v_role VARCHAR(20);
    DECLARE v_status VARCHAR(20);
    DECLARE v_count INT;
    -- Khóa cùng tài khoản đầu tiên để tuần tự hóa thay đổi quyền, không cần bảng phụ.
    -- API không xóa tài khoản; hàng khóa này ổn định giữa các lần đổi quyền.
    SELECT ma INTO v_lock FROM nguoi_dung ORDER BY ma LIMIT 1 FOR UPDATE;
    SELECT vai_tro,trang_thai INTO v_actor_role,v_actor_status FROM nguoi_dung WHERE ma=p_actor FOR UPDATE;
    IF v_actor_role <> 'ADMIN' OR v_actor_status <> 'ACTIVE' OR v_actor_role IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='FORBIDDEN';
    END IF;
    SELECT vai_tro,trang_thai INTO v_role,v_status FROM nguoi_dung WHERE ma=p_id FOR UPDATE;
    IF v_role IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='NOT_FOUND'; END IF;
    IF v_role='ADMIN' AND v_status='ACTIVE' AND
       (COALESCE(p_role,v_role)<>'ADMIN' OR COALESCE(p_status,v_status)<>'ACTIVE') THEN
        SELECT COUNT(*) INTO v_count FROM nguoi_dung WHERE vai_tro='ADMIN' AND trang_thai='ACTIVE';
        IF v_count <= 1 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='LAST_ADMIN'; END IF;
    END IF;
    UPDATE nguoi_dung SET vai_tro=COALESCE(p_role,vai_tro),trang_thai=COALESCE(p_status,trang_thai),ngay_cap_nhat=UTC_TIMESTAMP(6) WHERE ma=p_id;
    IF (p_role IS NOT NULL AND p_role<>v_role) OR (p_status IS NOT NULL AND p_status<>v_status) THEN
        UPDATE ma_lam_moi SET ngay_thu_hoi=UTC_TIMESTAMP(6) WHERE ma_nguoi_dung=p_id AND ngay_thu_hoi IS NULL;
    END IF;
    SELECT ma AS id, ten_dang_nhap AS username, ho_ten AS full_name, vai_tro AS role, trang_thai AS status FROM nguoi_dung WHERE ma=p_id;
END$$
DELIMITER ;
