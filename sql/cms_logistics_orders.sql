-- Đơn vận chuyển và hàng khách gửi; không thêm bảng hay dữ liệu mẫu.

-- Cài sau cms_logistics_procedures.sql và cms_logistics_customers.sql.

USE cms_logistics;

DELIMITER $$

DROP PROCEDURE IF EXISTS sp_order_actor$$

CREATE PROCEDURE sp_order_actor(IN p_actor BIGINT, IN p_write BOOLEAN, OUT p_role VARCHAR(20))
BEGIN
    SET p_role=NULL;
    IF p_write THEN
        SELECT vai_tro INTO p_role FROM nguoi_dung WHERE ma=p_actor AND trang_thai='ACTIVE' FOR UPDATE;
    ELSE
        SELECT vai_tro INTO p_role FROM nguoi_dung WHERE ma=p_actor AND trang_thai='ACTIVE';
    END IF;
    IF p_role IS NULL OR p_role NOT IN ('ADMIN','SALE','CUSTOMER')
       OR (p_write AND p_role='CUSTOMER') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='FORBIDDEN';
    END IF;
END$$

DROP PROCEDURE IF EXISTS sp_lock_order$$

CREATE PROCEDURE sp_lock_order(IN p_actor BIGINT, IN p_id BIGINT, OUT p_status VARCHAR(20))
BEGIN
    DECLARE v_role VARCHAR(20);
    DECLARE v_customer BIGINT;
    DECLARE v_sale BIGINT;
    DECLARE v_locked_customer BIGINT;
    CALL sp_order_actor(p_actor,TRUE,v_role);
    SELECT ma_khach_hang INTO v_customer FROM don_hang WHERE ma=p_id;
    IF v_customer IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='NOT_FOUND'; END IF;
    -- Giữ phân công khách ổn định cho đến lúc commit; cùng thứ tự khóa với API khách hàng.
    SELECT ma,ma_nhan_vien_phu_trach INTO v_locked_customer,v_sale
    FROM khach_hang WHERE ma=v_customer FOR UPDATE;
    IF v_locked_customer IS NULL OR (v_role='SALE' AND (v_sale IS NULL OR v_sale<>p_actor)) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='NOT_FOUND';
    END IF;
    SET p_status=NULL;
    SELECT trang_thai INTO p_status FROM don_hang WHERE ma=p_id FOR UPDATE;
    IF p_status IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='NOT_FOUND'; END IF;
END$$

DROP PROCEDURE IF EXISTS sp_list_orders$$

CREATE PROCEDURE sp_list_orders(IN p_actor BIGINT, IN p_customer BIGINT, IN p_status VARCHAR(20),
    IN p_search VARCHAR(150), IN p_limit INT, IN p_offset INT)
BEGIN
    DECLARE v_role VARCHAR(20);
    CALL sp_order_actor(p_actor,FALSE,v_role);
    SELECT o.ma AS id, o.ma_don AS order_code, o.ma_khach_hang AS customer_id,
        o.nguoi_tao AS created_by, o.ten_nguoi_nhan AS recipient_name,
        o.sdt_nguoi_nhan AS recipient_phone, o.dia_chi_nguoi_nhan AS recipient_address,
        o.phi_van_chuyen AS shipping_fee, o.trang_thai AS status, o.ghi_chu AS note,
        o.ngay_tao AS created_at, o.ngay_cap_nhat AS updated_at
    FROM don_hang o JOIN khach_hang c ON c.ma=o.ma_khach_hang
    WHERE (v_role='ADMIN' OR (v_role='SALE' AND c.ma_nhan_vien_phu_trach=p_actor)
        OR (v_role='CUSTOMER' AND c.ma_nguoi_dung=p_actor))
      AND (p_customer IS NULL OR o.ma_khach_hang=p_customer)
      AND (p_status IS NULL OR o.trang_thai=p_status)
      AND (p_search IS NULL OR LOCATE(p_search,o.ma_don)>0 OR LOCATE(p_search,o.ten_nguoi_nhan)>0
           OR LOCATE(p_search,o.sdt_nguoi_nhan)>0)
    ORDER BY o.ma DESC LIMIT p_limit OFFSET p_offset;
END$$

DROP PROCEDURE IF EXISTS sp_get_order$$

CREATE PROCEDURE sp_get_order(IN p_actor BIGINT, IN p_id BIGINT)
BEGIN
    DECLARE v_role VARCHAR(20);
    CALL sp_order_actor(p_actor,FALSE,v_role);
    SELECT o.ma AS id, o.ma_don AS order_code, o.ma_khach_hang AS customer_id,
        o.nguoi_tao AS created_by, o.ten_nguoi_nhan AS recipient_name,
        o.sdt_nguoi_nhan AS recipient_phone, o.dia_chi_nguoi_nhan AS recipient_address,
        o.phi_van_chuyen AS shipping_fee, o.trang_thai AS status, o.ghi_chu AS note,
        o.ngay_tao AS created_at, o.ngay_cap_nhat AS updated_at,
        COALESCE((SELECT JSON_ARRAYAGG(JSON_OBJECT('id',d.ma,'name',d.ten_san_pham,
            'quantity',d.so_luong,'note',d.ghi_chu)) FROM chi_tiet_don_hang d WHERE d.ma_don_hang=o.ma),
            JSON_ARRAY()) AS items
    FROM don_hang o JOIN khach_hang c ON c.ma=o.ma_khach_hang
    WHERE o.ma=p_id AND (v_role='ADMIN' OR (v_role='SALE' AND c.ma_nhan_vien_phu_trach=p_actor)
        OR (v_role='CUSTOMER' AND c.ma_nguoi_dung=p_actor));
END$$

DROP PROCEDURE IF EXISTS sp_insert_order_items$$

CREATE PROCEDURE sp_insert_order_items(IN p_id BIGINT, IN p_items JSON)
BEGIN
    DECLARE v_i INT DEFAULT 0;
    DECLARE v_name TEXT;
    DECLARE v_quantity JSON;
    DECLARE v_note TEXT;
    IF p_items IS NULL OR JSON_TYPE(p_items)<>'ARRAY' OR JSON_LENGTH(p_items)<1 OR JSON_LENGTH(p_items)>100 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_ITEMS';
    END IF;
    WHILE v_i<JSON_LENGTH(p_items) DO
        SET v_name=JSON_UNQUOTE(JSON_EXTRACT(p_items,CONCAT('$[',v_i,'].name')));
        SET v_quantity=JSON_EXTRACT(p_items,CONCAT('$[',v_i,'].quantity'));
        SET v_note=JSON_UNQUOTE(JSON_EXTRACT(p_items,CONCAT('$[',v_i,'].note')));
        IF JSON_TYPE(JSON_EXTRACT(p_items,CONCAT('$[',v_i,'].name')))<>'STRING'
           OR v_name IS NULL OR CHAR_LENGTH(TRIM(v_name))<1 OR CHAR_LENGTH(v_name)>255
           OR v_quantity IS NULL OR JSON_TYPE(v_quantity)<>'INTEGER'
           OR CAST(JSON_UNQUOTE(v_quantity) AS DECIMAL(30,0))<1
           OR CAST(JSON_UNQUOTE(v_quantity) AS DECIMAL(30,0))>2147483647 THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_ITEMS';
        END IF;
        IF JSON_TYPE(JSON_EXTRACT(p_items,CONCAT('$[',v_i,'].note')))='NULL' THEN SET v_note=NULL; END IF;
        IF CHAR_LENGTH(v_note)>2000 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_ITEMS'; END IF;
        INSERT INTO chi_tiet_don_hang(ma_don_hang,ten_san_pham,so_luong,ghi_chu)
        VALUES(p_id,TRIM(v_name),CAST(JSON_UNQUOTE(v_quantity) AS UNSIGNED),v_note);
        SET v_i=v_i+1;
    END WHILE;
END$$

DROP PROCEDURE IF EXISTS sp_create_order$$

CREATE PROCEDURE sp_create_order(IN p_actor BIGINT, IN p_code VARCHAR(40), IN p_customer BIGINT,
    IN p_recipient_name VARCHAR(150), IN p_phone VARCHAR(20), IN p_address VARCHAR(500),
    IN p_fee DECIMAL(18,2), IN p_note VARCHAR(2000), IN p_items JSON)
BEGIN
    DECLARE v_role VARCHAR(20);
    DECLARE v_sale BIGINT;
    DECLARE v_active BOOLEAN;
    DECLARE v_customer BIGINT;
    DECLARE v_id BIGINT;
    CALL sp_order_actor(p_actor,TRUE,v_role);
    SELECT ma,ma_nhan_vien_phu_trach,dang_hoat_dong INTO v_customer,v_sale,v_active
    FROM khach_hang WHERE ma=p_customer FOR UPDATE;
    IF v_customer IS NULL OR (v_role='SALE' AND (v_sale IS NULL OR v_sale<>p_actor)) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='NOT_FOUND';
    END IF;
    IF NOT v_active THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INACTIVE_CUSTOMER'; END IF;
    IF p_fee IS NULL OR p_fee<0 THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_FEE'; END IF;
    INSERT INTO don_hang(ma_don,ma_khach_hang,nguoi_tao,ten_nguoi_nhan,sdt_nguoi_nhan,
        dia_chi_nguoi_nhan,phi_van_chuyen,trang_thai,ghi_chu)
    VALUES(p_code,p_customer,p_actor,p_recipient_name,p_phone,p_address,p_fee,'PENDING',p_note);
    SET v_id=LAST_INSERT_ID();
    CALL sp_insert_order_items(v_id,p_items);
    CALL sp_get_order(p_actor,v_id);
END$$

DROP PROCEDURE IF EXISTS sp_update_order$$

CREATE PROCEDURE sp_update_order(IN p_actor BIGINT, IN p_id BIGINT, IN p_patch JSON)
BEGIN
    DECLARE v_status VARCHAR(20);
    CALL sp_lock_order(p_actor,p_id,v_status);
    IF v_status<>'PENDING' THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ORDER_NOT_EDITABLE'; END IF;
    -- Không thay đổi phí/hàng gửi khi đã có kiện hoặc giao dịch liên quan.
    IF EXISTS(SELECT 1 FROM kien_hang WHERE ma_don_hang=p_id)
       OR EXISTS(SELECT 1 FROM thanh_toan WHERE ma_don_hang=p_id) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ORDER_HAS_DEPENDENCIES';
    END IF;
    IF JSON_CONTAINS_PATH(p_patch,'one','$.items') THEN
        DELETE FROM chi_tiet_don_hang WHERE ma_don_hang=p_id;
        CALL sp_insert_order_items(p_id,JSON_EXTRACT(p_patch,'$.items'));
    END IF;
    UPDATE don_hang SET ten_nguoi_nhan=IF(JSON_CONTAINS_PATH(p_patch,'one','$.recipient_name'),JSON_UNQUOTE(JSON_EXTRACT(p_patch,'$.recipient_name')),ten_nguoi_nhan),
        sdt_nguoi_nhan=IF(JSON_CONTAINS_PATH(p_patch,'one','$.recipient_phone'),JSON_UNQUOTE(JSON_EXTRACT(p_patch,'$.recipient_phone')),sdt_nguoi_nhan),
        dia_chi_nguoi_nhan=IF(JSON_CONTAINS_PATH(p_patch,'one','$.recipient_address'),JSON_UNQUOTE(JSON_EXTRACT(p_patch,'$.recipient_address')),dia_chi_nguoi_nhan),
        phi_van_chuyen=IF(JSON_CONTAINS_PATH(p_patch,'one','$.shipping_fee'),CAST(JSON_UNQUOTE(JSON_EXTRACT(p_patch,'$.shipping_fee')) AS DECIMAL(18,2)),phi_van_chuyen),
        ghi_chu=IF(JSON_CONTAINS_PATH(p_patch,'one','$.note'),IF(JSON_TYPE(JSON_EXTRACT(p_patch,'$.note'))='NULL',NULL,JSON_UNQUOTE(JSON_EXTRACT(p_patch,'$.note'))),ghi_chu),ngay_cap_nhat=UTC_TIMESTAMP(6) WHERE ma=p_id;
    CALL sp_get_order(p_actor,p_id);
END$$

DROP PROCEDURE IF EXISTS sp_update_order_status$$

CREATE PROCEDURE sp_update_order_status(IN p_actor BIGINT, IN p_id BIGINT, IN p_status VARCHAR(20))
BEGIN
    DECLARE v_status VARCHAR(20);
    CALL sp_lock_order(p_actor,p_id,v_status);
    IF p_status IS NULL OR p_status NOT IN ('PENDING','CONFIRMED','SHIPPING','DELIVERED','CANCELLED') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_STATUS';
    END IF;
    IF p_status<>v_status THEN
        IF NOT ((v_status='PENDING' AND p_status IN ('CONFIRMED','CANCELLED'))
             OR (v_status='CONFIRMED' AND p_status IN ('SHIPPING','CANCELLED'))
             OR (v_status='SHIPPING' AND p_status='DELIVERED')) THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_TRANSITION';
        END IF;
        IF p_status='CANCELLED' AND
           (EXISTS(SELECT 1 FROM kien_hang WHERE ma_don_hang=p_id AND trang_thai<>'CANCELLED')
            OR EXISTS(SELECT 1 FROM thanh_toan WHERE ma_don_hang=p_id)) THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ORDER_HAS_DEPENDENCIES';
        END IF;
        UPDATE don_hang SET trang_thai=p_status,ngay_cap_nhat=UTC_TIMESTAMP(6) WHERE ma=p_id;
    END IF;
    CALL sp_get_order(p_actor,p_id);
END$$

DELIMITER ;
