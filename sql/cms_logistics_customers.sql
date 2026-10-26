-- API khách hàng: chỉ cài procedure trên 10 bảng hiện có.

USE cms_logistics;

DELIMITER $$

DROP PROCEDURE IF EXISTS sp_list_customers$$

CREATE PROCEDURE sp_list_customers(IN p_actor BIGINT, IN p_search VARCHAR(150), IN p_active_only BOOLEAN, IN p_limit INT, IN p_offset INT)
BEGIN
    DECLARE v_role VARCHAR(20);
    SELECT vai_tro INTO v_role FROM nguoi_dung WHERE ma=p_actor AND trang_thai='ACTIVE';
    IF v_role IS NULL OR v_role NOT IN ('ADMIN','SALE','CUSTOMER') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='FORBIDDEN';
    END IF;
    SELECT ma AS id, ma_nguoi_dung AS user_id, ten AS name,
        so_dien_thoai AS phone, email, dia_chi AS address,
        ma_nhan_vien_phu_trach AS sale_id, dang_hoat_dong AS is_active,
        ngay_tao AS created_at, ngay_cap_nhat AS updated_at FROM khach_hang
    WHERE (v_role='ADMIN' OR (v_role='SALE' AND ma_nhan_vien_phu_trach=p_actor)
           OR (v_role='CUSTOMER' AND ma_nguoi_dung=p_actor AND dang_hoat_dong=1))
      AND (NOT p_active_only OR dang_hoat_dong=1)
      AND (p_search IS NULL OR LOCATE(p_search,ten)>0 OR LOCATE(p_search,so_dien_thoai)>0)
    ORDER BY ma DESC LIMIT p_limit OFFSET p_offset;
END$$

DROP PROCEDURE IF EXISTS sp_get_customer$$

CREATE PROCEDURE sp_get_customer(IN p_actor BIGINT, IN p_id BIGINT)
BEGIN
    DECLARE v_role VARCHAR(20);
    SELECT vai_tro INTO v_role FROM nguoi_dung WHERE ma=p_actor AND trang_thai='ACTIVE';
    IF v_role IS NULL OR v_role NOT IN ('ADMIN','SALE','CUSTOMER') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='FORBIDDEN';
    END IF;
    SELECT ma AS id, ma_nguoi_dung AS user_id, ten AS name,
        so_dien_thoai AS phone, email, dia_chi AS address,
        ma_nhan_vien_phu_trach AS sale_id, dang_hoat_dong AS is_active,
        ngay_tao AS created_at, ngay_cap_nhat AS updated_at FROM khach_hang
    WHERE ma=p_id AND (v_role='ADMIN' OR (v_role='SALE' AND ma_nhan_vien_phu_trach=p_actor)
           OR (v_role='CUSTOMER' AND ma_nguoi_dung=p_actor AND dang_hoat_dong=1));
END$$

DROP PROCEDURE IF EXISTS sp_create_customer$$

CREATE PROCEDURE sp_create_customer(IN p_actor BIGINT, IN p_name VARCHAR(150), IN p_phone VARCHAR(20),
    IN p_email VARCHAR(255), IN p_address VARCHAR(500), IN p_user_id BIGINT, IN p_sale_id BIGINT)
BEGIN
    DECLARE v_role VARCHAR(20);
    DECLARE v_ref BIGINT;
    DECLARE v_id BIGINT;
    SELECT vai_tro INTO v_role FROM nguoi_dung WHERE ma=p_actor AND trang_thai='ACTIVE' FOR UPDATE;
    IF v_role IS NULL OR v_role NOT IN ('ADMIN','SALE') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='FORBIDDEN';
    END IF;
    IF v_role='SALE' THEN
        IF p_user_id IS NOT NULL OR (p_sale_id IS NOT NULL AND p_sale_id<>p_actor) THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='FORBIDDEN';
        END IF;
        SET p_sale_id=p_actor;
    END IF;
    IF p_user_id IS NOT NULL THEN
        SET v_ref=NULL;
        SELECT ma INTO v_ref FROM nguoi_dung
        WHERE ma=p_user_id AND vai_tro='CUSTOMER' AND trang_thai='ACTIVE' FOR UPDATE;
        IF v_ref IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_CUSTOMER_USER'; END IF;
    END IF;
    IF p_sale_id IS NOT NULL THEN
        SET v_ref=NULL;
        SELECT ma INTO v_ref FROM nguoi_dung
        WHERE ma=p_sale_id AND vai_tro='SALE' AND trang_thai='ACTIVE' FOR UPDATE;
        IF v_ref IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_SALE'; END IF;
    END IF;
    INSERT INTO khach_hang(ten,so_dien_thoai,email,dia_chi,ma_nguoi_dung,ma_nhan_vien_phu_trach)
    VALUES(p_name,p_phone,p_email,p_address,p_user_id,p_sale_id);
    SET v_id=LAST_INSERT_ID();
    SELECT ma AS id, ma_nguoi_dung AS user_id, ten AS name,
        so_dien_thoai AS phone, email, dia_chi AS address,
        ma_nhan_vien_phu_trach AS sale_id, dang_hoat_dong AS is_active,
        ngay_tao AS created_at, ngay_cap_nhat AS updated_at FROM khach_hang WHERE ma=v_id;
END$$

DROP PROCEDURE IF EXISTS sp_update_customer$$

CREATE PROCEDURE sp_update_customer(IN p_actor BIGINT, IN p_id BIGINT, IN p_patch JSON)
BEGIN
    DECLARE v_role VARCHAR(20);
    DECLARE v_ref BIGINT;
    DECLARE v_id BIGINT;
    DECLARE v_sale BIGINT;
    SELECT vai_tro INTO v_role FROM nguoi_dung WHERE ma=p_actor AND trang_thai='ACTIVE' FOR UPDATE;
    IF v_role IS NULL OR v_role NOT IN ('ADMIN','SALE') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='FORBIDDEN';
    END IF;
    SELECT ma,ma_nhan_vien_phu_trach INTO v_id,v_sale FROM khach_hang WHERE ma=p_id FOR UPDATE;
    IF v_id IS NULL OR (v_role='SALE' AND (v_sale IS NULL OR v_sale<>p_actor)) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='NOT_FOUND';
    END IF;
    IF v_role='SALE' AND (JSON_CONTAINS_PATH(p_patch,'one','$.user_id','$.sale_id','$.is_active')) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='FORBIDDEN';
    END IF;
    IF JSON_CONTAINS_PATH(p_patch,'one','$.user_id') THEN
        SET v_ref=NULL;
        SELECT ma INTO v_ref FROM nguoi_dung WHERE ma=CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(p_patch,'$.user_id')),'null') AS UNSIGNED)
            AND vai_tro='CUSTOMER' AND trang_thai='ACTIVE' FOR UPDATE;
        IF v_ref IS NULL AND JSON_TYPE(JSON_EXTRACT(p_patch,'$.user_id'))<>'NULL' THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_CUSTOMER_USER';
        END IF;
    END IF;
    IF JSON_CONTAINS_PATH(p_patch,'one','$.sale_id') THEN
        SET v_ref=NULL;
        SELECT ma INTO v_ref FROM nguoi_dung WHERE ma=CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(p_patch,'$.sale_id')),'null') AS UNSIGNED)
            AND vai_tro='SALE' AND trang_thai='ACTIVE' FOR UPDATE;
        IF v_ref IS NULL AND JSON_TYPE(JSON_EXTRACT(p_patch,'$.sale_id'))<>'NULL' THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_SALE';
        END IF;
    END IF;
    UPDATE khach_hang SET ten=IF(JSON_CONTAINS_PATH(p_patch,'one','$.name'),NULLIF(JSON_UNQUOTE(JSON_EXTRACT(p_patch,'$.name')),'null'),ten),
        so_dien_thoai=IF(JSON_CONTAINS_PATH(p_patch,'one','$.phone'),NULLIF(JSON_UNQUOTE(JSON_EXTRACT(p_patch,'$.phone')),'null'),so_dien_thoai),
        email=IF(JSON_CONTAINS_PATH(p_patch,'one','$.email'),NULLIF(JSON_UNQUOTE(JSON_EXTRACT(p_patch,'$.email')),'null'),email),
        dia_chi=IF(JSON_CONTAINS_PATH(p_patch,'one','$.address'),NULLIF(JSON_UNQUOTE(JSON_EXTRACT(p_patch,'$.address')),'null'),dia_chi),
        ma_nguoi_dung=IF(JSON_CONTAINS_PATH(p_patch,'one','$.user_id'),CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(p_patch,'$.user_id')),'null') AS UNSIGNED),ma_nguoi_dung),
        ma_nhan_vien_phu_trach=IF(JSON_CONTAINS_PATH(p_patch,'one','$.sale_id'),CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(p_patch,'$.sale_id')),'null') AS UNSIGNED),ma_nhan_vien_phu_trach),
        dang_hoat_dong=IF(JSON_CONTAINS_PATH(p_patch,'one','$.is_active'),(JSON_UNQUOTE(JSON_EXTRACT(p_patch,'$.is_active'))='true'),dang_hoat_dong), ngay_cap_nhat=UTC_TIMESTAMP(6) WHERE ma=p_id;
    SELECT ma AS id, ma_nguoi_dung AS user_id, ten AS name,
        so_dien_thoai AS phone, email, dia_chi AS address,
        ma_nhan_vien_phu_trach AS sale_id, dang_hoat_dong AS is_active,
        ngay_tao AS created_at, ngay_cap_nhat AS updated_at FROM khach_hang WHERE ma=p_id;
END$$

DROP PROCEDURE IF EXISTS sp_deactivate_customer$$

CREATE PROCEDURE sp_deactivate_customer(IN p_actor BIGINT, IN p_id BIGINT)
BEGIN
    DECLARE v_role VARCHAR(20);
    DECLARE v_id BIGINT;
    DECLARE v_sale BIGINT;
    SELECT vai_tro INTO v_role FROM nguoi_dung WHERE ma=p_actor AND trang_thai='ACTIVE' FOR UPDATE;
    IF v_role IS NULL OR v_role NOT IN ('ADMIN','SALE') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='FORBIDDEN';
    END IF;
    SELECT ma,ma_nhan_vien_phu_trach INTO v_id,v_sale FROM khach_hang WHERE ma=p_id FOR UPDATE;
    IF v_id IS NULL OR (v_role='SALE' AND (v_sale IS NULL OR v_sale<>p_actor)) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='NOT_FOUND';
    END IF;
    UPDATE khach_hang SET dang_hoat_dong=0,ngay_cap_nhat=UTC_TIMESTAMP(6) WHERE ma=p_id;
END$$

DELIMITER ;
