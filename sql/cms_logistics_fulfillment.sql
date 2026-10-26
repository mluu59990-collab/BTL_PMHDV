-- Kho, kiện và lịch sử vận chuyển; chỉ tạo procedure trên 10 bảng hiện có.

-- Cài sau cms_logistics_orders.sql. Không tự sửa dữ liệu hiện có.

USE cms_logistics;

DELIMITER $$

DROP PROCEDURE IF EXISTS sp_fulfillment_actor$$

CREATE PROCEDURE sp_fulfillment_actor(IN p_actor BIGINT,IN p_write BOOLEAN,OUT p_role VARCHAR(20))
BEGIN
    SET p_role=NULL;
    IF p_write THEN
        SELECT vai_tro INTO p_role FROM nguoi_dung WHERE ma=p_actor AND trang_thai='ACTIVE' FOR UPDATE;
    ELSE
        SELECT vai_tro INTO p_role FROM nguoi_dung WHERE ma=p_actor AND trang_thai='ACTIVE';
    END IF;
    IF p_role IS NULL OR p_role NOT IN ('ADMIN','WAREHOUSE','SALE','CUSTOMER')
       OR (p_write AND p_role NOT IN ('ADMIN','WAREHOUSE')) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='FORBIDDEN';
    END IF;
END$$

DROP PROCEDURE IF EXISTS sp_lock_fulfillment_order$$

CREATE PROCEDURE sp_lock_fulfillment_order(IN p_actor BIGINT,IN p_order BIGINT,OUT p_status VARCHAR(20))
BEGIN
    DECLARE v_role VARCHAR(20);
    DECLARE v_customer BIGINT;
    DECLARE v_locked BIGINT;
    CALL sp_fulfillment_actor(p_actor,TRUE,v_role);
    SELECT ma_khach_hang INTO v_customer FROM don_hang WHERE ma=p_order;
    IF v_customer IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='NOT_FOUND'; END IF;
    -- Cùng thứ tự khóa với API đơn/khách hàng; mọi kiện cùng đơn dùng chung khóa đơn.
    SELECT ma INTO v_locked FROM khach_hang WHERE ma=v_customer FOR UPDATE;
    SET p_status=NULL;
    SELECT trang_thai INTO p_status FROM don_hang WHERE ma=p_order FOR UPDATE;
    IF p_status IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='NOT_FOUND'; END IF;
END$$

DROP PROCEDURE IF EXISTS sp_list_warehouses$$

CREATE PROCEDURE sp_list_warehouses(IN p_actor BIGINT,IN p_active BOOLEAN,IN p_search VARCHAR(150),IN p_limit INT,IN p_offset INT)
BEGIN
    DECLARE v_role VARCHAR(20);
    CALL sp_fulfillment_actor(p_actor,FALSE,v_role);
    SELECT w.ma AS id,w.ma_kho AS warehouse_code,w.ten AS name,w.dia_chi AS address,w.ma_quoc_gia AS country_code,w.dang_hoat_dong AS is_active FROM kho_hang w
    WHERE (v_role IN ('ADMIN','WAREHOUSE') OR EXISTS(
        SELECT 1 FROM lich_su_van_chuyen h JOIN kien_hang p ON p.ma=h.ma_kien_hang
        JOIN don_hang o ON o.ma=p.ma_don_hang JOIN khach_hang c ON c.ma=o.ma_khach_hang
        WHERE h.ma_kho_hang=w.ma AND (v_role IN ('ADMIN','WAREHOUSE') OR (v_role='SALE' AND c.ma_nhan_vien_phu_trach=p_actor)
        OR (v_role='CUSTOMER' AND c.ma_nguoi_dung=p_actor)))) AND (NOT p_active OR w.dang_hoat_dong=1)
      AND (p_search IS NULL OR LOCATE(p_search,w.ma_kho)>0 OR LOCATE(p_search,w.ten)>0)
    ORDER BY w.ma LIMIT p_limit OFFSET p_offset;
END$$

DROP PROCEDURE IF EXISTS sp_get_warehouse$$

CREATE PROCEDURE sp_get_warehouse(IN p_actor BIGINT,IN p_id BIGINT)
BEGIN
    DECLARE v_role VARCHAR(20);
    CALL sp_fulfillment_actor(p_actor,FALSE,v_role);
    SELECT w.ma AS id,w.ma_kho AS warehouse_code,w.ten AS name,w.dia_chi AS address,w.ma_quoc_gia AS country_code,w.dang_hoat_dong AS is_active FROM kho_hang w WHERE w.ma=p_id AND (v_role IN ('ADMIN','WAREHOUSE') OR EXISTS(
        SELECT 1 FROM lich_su_van_chuyen h JOIN kien_hang p ON p.ma=h.ma_kien_hang
        JOIN don_hang o ON o.ma=p.ma_don_hang JOIN khach_hang c ON c.ma=o.ma_khach_hang
        WHERE h.ma_kho_hang=w.ma AND (v_role IN ('ADMIN','WAREHOUSE') OR (v_role='SALE' AND c.ma_nhan_vien_phu_trach=p_actor)
        OR (v_role='CUSTOMER' AND c.ma_nguoi_dung=p_actor))));
END$$

DROP PROCEDURE IF EXISTS sp_create_warehouse$$

CREATE PROCEDURE sp_create_warehouse(IN p_actor BIGINT,IN p_code VARCHAR(30),IN p_name VARCHAR(150),IN p_address VARCHAR(500),IN p_country VARCHAR(2))
BEGIN
    DECLARE v_role VARCHAR(20);
    DECLARE v_id BIGINT;
    CALL sp_fulfillment_actor(p_actor,TRUE,v_role);
    IF v_role<>'ADMIN' THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='FORBIDDEN'; END IF;
    INSERT INTO kho_hang(ma_kho,ten,dia_chi,ma_quoc_gia) VALUES(p_code,p_name,p_address,p_country);
    SET v_id=LAST_INSERT_ID();
    CALL sp_get_warehouse(p_actor,v_id);
END$$

DROP PROCEDURE IF EXISTS sp_update_warehouse$$

CREATE PROCEDURE sp_update_warehouse(IN p_actor BIGINT,IN p_id BIGINT,IN p_patch JSON)
BEGIN
    DECLARE v_role VARCHAR(20);
    DECLARE v_id BIGINT;
    CALL sp_fulfillment_actor(p_actor,TRUE,v_role);
    IF v_role<>'ADMIN' THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='FORBIDDEN'; END IF;
    SELECT ma INTO v_id FROM kho_hang WHERE ma=p_id FOR UPDATE;
    IF v_id IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='NOT_FOUND'; END IF;
    IF JSON_CONTAINS_PATH(p_patch,'one','$.is_active') AND JSON_UNQUOTE(JSON_EXTRACT(p_patch,'$.is_active'))='false'
       AND EXISTS(SELECT 1 FROM kien_hang WHERE ma_kho_hang=p_id AND trang_thai='IN_WAREHOUSE') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='WAREHOUSE_OCCUPIED';
    END IF;
    UPDATE kho_hang SET
        ten=IF(JSON_CONTAINS_PATH(p_patch,'one','$.name'),JSON_UNQUOTE(JSON_EXTRACT(p_patch,'$.name')),ten),
        dia_chi=IF(JSON_CONTAINS_PATH(p_patch,'one','$.address'),JSON_UNQUOTE(JSON_EXTRACT(p_patch,'$.address')),dia_chi),
        dang_hoat_dong=IF(JSON_CONTAINS_PATH(p_patch,'one','$.is_active'),JSON_UNQUOTE(JSON_EXTRACT(p_patch,'$.is_active'))='true',dang_hoat_dong)
    WHERE ma=p_id;
    CALL sp_get_warehouse(p_actor,p_id);
END$$

DROP PROCEDURE IF EXISTS sp_list_packages$$

CREATE PROCEDURE sp_list_packages(IN p_actor BIGINT,IN p_order BIGINT,IN p_warehouse BIGINT,IN p_status VARCHAR(20),
    IN p_search VARCHAR(150),IN p_limit INT,IN p_offset INT)
BEGIN
    DECLARE v_role VARCHAR(20);
    CALL sp_fulfillment_actor(p_actor,FALSE,v_role);
    SELECT p.ma AS id,p.ma_don_hang AS order_id,p.ma_van_don AS tracking_code,
        p.ma_kho_hang AS warehouse_id,p.khoi_luong_kg AS weight_kg,p.chieu_dai_cm AS length_cm,
        p.chieu_rong_cm AS width_cm,p.chieu_cao_cm AS height_cm,p.trang_thai AS status,
        p.ngay_tao AS created_at,p.ngay_cap_nhat AS updated_at FROM kien_hang p JOIN don_hang o ON o.ma=p.ma_don_hang
    JOIN khach_hang c ON c.ma=o.ma_khach_hang
    WHERE (v_role IN ('ADMIN','WAREHOUSE') OR (v_role='SALE' AND c.ma_nhan_vien_phu_trach=p_actor)
        OR (v_role='CUSTOMER' AND c.ma_nguoi_dung=p_actor)) AND (p_order IS NULL OR p.ma_don_hang=p_order)
      AND (p_warehouse IS NULL OR p.ma_kho_hang=p_warehouse) AND (p_status IS NULL OR p.trang_thai=p_status)
      AND (p_search IS NULL OR LOCATE(p_search,p.ma_van_don)>0)
    ORDER BY p.ma DESC LIMIT p_limit OFFSET p_offset;
END$$

DROP PROCEDURE IF EXISTS sp_get_package$$

CREATE PROCEDURE sp_get_package(IN p_actor BIGINT,IN p_id BIGINT)
BEGIN
    DECLARE v_role VARCHAR(20);
    CALL sp_fulfillment_actor(p_actor,FALSE,v_role);
    SELECT p.ma AS id,p.ma_don_hang AS order_id,p.ma_van_don AS tracking_code,
        p.ma_kho_hang AS warehouse_id,p.khoi_luong_kg AS weight_kg,p.chieu_dai_cm AS length_cm,
        p.chieu_rong_cm AS width_cm,p.chieu_cao_cm AS height_cm,p.trang_thai AS status,
        p.ngay_tao AS created_at,p.ngay_cap_nhat AS updated_at,COALESCE((SELECT JSON_ARRAYAGG(JSON_OBJECT('id',d.ma,'order_item_id',d.ma_chi_tiet_don_hang,
        'name',i.ten_san_pham,'quantity',d.so_luong))
        FROM chi_tiet_kien_hang d JOIN chi_tiet_don_hang i ON i.ma=d.ma_chi_tiet_don_hang
        WHERE d.ma_kien_hang=p.ma),JSON_ARRAY()) AS items
    FROM kien_hang p JOIN don_hang o ON o.ma=p.ma_don_hang JOIN khach_hang c ON c.ma=o.ma_khach_hang
    WHERE p.ma=p_id AND (v_role IN ('ADMIN','WAREHOUSE') OR (v_role='SALE' AND c.ma_nhan_vien_phu_trach=p_actor)
        OR (v_role='CUSTOMER' AND c.ma_nguoi_dung=p_actor));
END$$

DROP PROCEDURE IF EXISTS sp_package_history$$

CREATE PROCEDURE sp_package_history(IN p_actor BIGINT,IN p_id BIGINT,IN p_limit INT,IN p_offset INT)
BEGIN
    DECLARE v_role VARCHAR(20);
    CALL sp_fulfillment_actor(p_actor,FALSE,v_role);
    IF NOT EXISTS(SELECT 1 FROM kien_hang p JOIN don_hang o ON o.ma=p.ma_don_hang
        JOIN khach_hang c ON c.ma=o.ma_khach_hang WHERE p.ma=p_id AND (v_role IN ('ADMIN','WAREHOUSE') OR (v_role='SALE' AND c.ma_nhan_vien_phu_trach=p_actor)
        OR (v_role='CUSTOMER' AND c.ma_nguoi_dung=p_actor))) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='NOT_FOUND';
    END IF;
    SELECT h.ma AS id,h.ma_kien_hang AS package_id,h.ma_kho_hang AS warehouse_id,h.trang_thai AS status,
        h.ghi_chu AS note,h.nguoi_tao AS created_by,h.ngay_tao AS created_at
    FROM lich_su_van_chuyen h WHERE h.ma_kien_hang=p_id
    ORDER BY h.ngay_tao,h.ma LIMIT p_limit OFFSET p_offset;
END$$

DROP PROCEDURE IF EXISTS sp_allocate_package_items$$

CREATE PROCEDURE sp_allocate_package_items(IN p_package BIGINT,IN p_order BIGINT,IN p_items JSON)
BEGIN
    DECLARE v_i INT DEFAULT 0;
    DECLARE v_item BIGINT;
    DECLARE v_quantity BIGINT;
    DECLARE v_ordered BIGINT;
    DECLARE v_used BIGINT;
    DECLARE v_id_json JSON;
    DECLARE v_qty_json JSON;
    -- Caller must hold the shared order row lock throughout validation and insertion.
    IF p_items IS NULL OR JSON_TYPE(p_items)<>'ARRAY' OR JSON_LENGTH(p_items)<1 OR JSON_LENGTH(p_items)>100 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_PACKAGE_ITEMS';
    END IF;
    WHILE v_i<JSON_LENGTH(p_items) DO
        SET v_id_json=JSON_EXTRACT(p_items,CONCAT('$[',v_i,'].order_item_id'));
        SET v_qty_json=JSON_EXTRACT(p_items,CONCAT('$[',v_i,'].quantity'));
        IF v_id_json IS NULL OR JSON_TYPE(v_id_json)<>'INTEGER' OR v_qty_json IS NULL
           OR JSON_TYPE(v_qty_json)<>'INTEGER' THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_PACKAGE_ITEMS';
        END IF;
        SET v_item=CAST(JSON_UNQUOTE(v_id_json) AS SIGNED);
        SET v_quantity=CAST(JSON_UNQUOTE(v_qty_json) AS SIGNED);
        IF v_item<1 OR v_quantity<1 OR v_quantity>2147483647 THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_PACKAGE_ITEMS';
        END IF;
        IF EXISTS(SELECT 1 FROM chi_tiet_kien_hang WHERE ma_kien_hang=p_package AND ma_chi_tiet_don_hang=v_item) THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_PACKAGE_ITEMS';
        END IF;
        SET v_ordered=NULL;
        SELECT so_luong INTO v_ordered FROM chi_tiet_don_hang WHERE ma=v_item AND ma_don_hang=p_order;
        IF v_ordered IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ITEM_NOT_IN_ORDER'; END IF;
        SELECT COALESCE(SUM(d.so_luong),0) INTO v_used FROM chi_tiet_kien_hang d
        JOIN kien_hang p ON p.ma=d.ma_kien_hang WHERE d.ma_chi_tiet_don_hang=v_item AND p.trang_thai<>'CANCELLED';
        IF v_used+v_quantity>v_ordered THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='OVER_PACKED'; END IF;
        INSERT INTO chi_tiet_kien_hang(ma_kien_hang,ma_chi_tiet_don_hang,so_luong) VALUES(p_package,v_item,v_quantity);
        SET v_i=v_i+1;
    END WHILE;
END$$

DROP PROCEDURE IF EXISTS sp_create_package$$

CREATE PROCEDURE sp_create_package(IN p_actor BIGINT,IN p_order BIGINT,IN p_code VARCHAR(50),IN p_metrics JSON,IN p_items JSON,IN p_note VARCHAR(2000))
BEGIN
    DECLARE v_order_status VARCHAR(20);
    DECLARE v_id BIGINT;
    CALL sp_lock_fulfillment_order(p_actor,p_order,v_order_status);
    IF v_order_status NOT IN ('CONFIRMED','SHIPPING') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ORDER_NOT_PACKABLE';
    END IF;
    INSERT INTO kien_hang(ma_don_hang,ma_van_don,khoi_luong_kg,chieu_dai_cm,chieu_rong_cm,chieu_cao_cm)
    VALUES(p_order,p_code,CAST(JSON_UNQUOTE(JSON_EXTRACT(p_metrics,'$.weight_kg')) AS DECIMAL(12,3)),CAST(JSON_UNQUOTE(JSON_EXTRACT(p_metrics,'$.length_cm')) AS DECIMAL(10,2)),CAST(JSON_UNQUOTE(JSON_EXTRACT(p_metrics,'$.width_cm')) AS DECIMAL(10,2)),CAST(JSON_UNQUOTE(JSON_EXTRACT(p_metrics,'$.height_cm')) AS DECIMAL(10,2)));
    SET v_id=LAST_INSERT_ID();
    CALL sp_allocate_package_items(v_id,p_order,p_items);
    INSERT INTO lich_su_van_chuyen(ma_kien_hang,trang_thai,ghi_chu,nguoi_tao)
    VALUES(v_id,'CREATED',p_note,p_actor);
    CALL sp_get_package(p_actor,v_id);
END$$

DROP PROCEDURE IF EXISTS sp_update_package$$

CREATE PROCEDURE sp_update_package(IN p_actor BIGINT,IN p_id BIGINT,IN p_patch JSON)
BEGIN
    DECLARE v_order BIGINT;
    DECLARE v_order_status VARCHAR(20);
    DECLARE v_status VARCHAR(20);
    SELECT ma_don_hang INTO v_order FROM kien_hang WHERE ma=p_id;
    IF v_order IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='NOT_FOUND'; END IF;
    CALL sp_lock_fulfillment_order(p_actor,v_order,v_order_status);
    SELECT trang_thai INTO v_status FROM kien_hang WHERE ma=p_id FOR UPDATE;
    IF v_status<>'CREATED' OR v_order_status NOT IN ('CONFIRMED','SHIPPING') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='PACKAGE_NOT_EDITABLE';
    END IF;
    IF JSON_CONTAINS_PATH(p_patch,'one','$.items') THEN
        DELETE FROM chi_tiet_kien_hang WHERE ma_kien_hang=p_id;
        CALL sp_allocate_package_items(p_id,v_order,JSON_EXTRACT(p_patch,'$.items'));
    END IF;
    UPDATE kien_hang SET khoi_luong_kg=IF(JSON_CONTAINS_PATH(p_patch,'one','$.weight_kg'),CAST(JSON_UNQUOTE(JSON_EXTRACT(p_patch,'$.weight_kg')) AS DECIMAL(12,3)),khoi_luong_kg),
        chieu_dai_cm=IF(JSON_CONTAINS_PATH(p_patch,'one','$.length_cm'),CAST(JSON_UNQUOTE(JSON_EXTRACT(p_patch,'$.length_cm')) AS DECIMAL(10,2)),chieu_dai_cm),
        chieu_rong_cm=IF(JSON_CONTAINS_PATH(p_patch,'one','$.width_cm'),CAST(JSON_UNQUOTE(JSON_EXTRACT(p_patch,'$.width_cm')) AS DECIMAL(10,2)),chieu_rong_cm),
        chieu_cao_cm=IF(JSON_CONTAINS_PATH(p_patch,'one','$.height_cm'),CAST(JSON_UNQUOTE(JSON_EXTRACT(p_patch,'$.height_cm')) AS DECIMAL(10,2)),chieu_cao_cm),ngay_cap_nhat=UTC_TIMESTAMP(6) WHERE ma=p_id;
    CALL sp_get_package(p_actor,p_id);
END$$

DROP PROCEDURE IF EXISTS sp_update_package_status$$

CREATE PROCEDURE sp_update_package_status(IN p_actor BIGINT,IN p_id BIGINT,IN p_status VARCHAR(20),IN p_warehouse BIGINT,IN p_note VARCHAR(2000))
BEGIN
    DECLARE v_order BIGINT;
    DECLARE v_order_status VARCHAR(20);
    DECLARE v_status VARCHAR(20);
    DECLARE v_old_warehouse BIGINT;
    DECLARE v_active BOOLEAN;
    DECLARE v_event_warehouse BIGINT;
    SELECT ma_don_hang INTO v_order FROM kien_hang WHERE ma=p_id;
    IF v_order IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='NOT_FOUND'; END IF;
    CALL sp_lock_fulfillment_order(p_actor,v_order,v_order_status);
    SELECT trang_thai,ma_kho_hang INTO v_status,v_old_warehouse FROM kien_hang WHERE ma=p_id FOR UPDATE;
    IF p_status IS NULL OR p_status NOT IN ('CREATED','IN_WAREHOUSE','IN_TRANSIT','DELIVERED','CANCELLED')
       OR (p_status='IN_WAREHOUSE' AND p_warehouse IS NULL)
       OR (p_status<>'IN_WAREHOUSE' AND p_warehouse IS NOT NULL) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_PACKAGE_STATUS';
    END IF;
    IF p_status=v_status THEN
        IF NOT (p_warehouse <=> v_old_warehouse) THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_PACKAGE_TRANSITION';
        END IF;
    ELSE
        IF v_order_status NOT IN ('CONFIRMED','SHIPPING') THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ORDER_NOT_PACKABLE';
        END IF;
        IF NOT ((v_status='CREATED' AND p_status IN ('IN_WAREHOUSE','CANCELLED'))
            OR (v_status='IN_WAREHOUSE' AND p_status IN ('IN_TRANSIT','CANCELLED'))
            OR (v_status='IN_TRANSIT' AND p_status IN ('IN_WAREHOUSE','DELIVERED'))) THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_PACKAGE_TRANSITION';
        END IF;
        IF p_status='IN_WAREHOUSE' THEN
            SET v_active=NULL;
            SELECT dang_hoat_dong INTO v_active FROM kho_hang WHERE ma=p_warehouse FOR UPDATE;
            IF v_active IS NULL OR NOT v_active THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_WAREHOUSE';
            END IF;
        END IF;
        SET v_event_warehouse=IF(p_status='IN_WAREHOUSE',p_warehouse,v_old_warehouse);
        UPDATE kien_hang SET trang_thai=p_status,ma_kho_hang=p_warehouse,ngay_cap_nhat=UTC_TIMESTAMP(6) WHERE ma=p_id;
        INSERT INTO lich_su_van_chuyen(ma_kien_hang,ma_kho_hang,trang_thai,ghi_chu,nguoi_tao)
        VALUES(p_id,v_event_warehouse,p_status,p_note,p_actor);
        IF p_status='IN_TRANSIT' AND v_order_status='CONFIRMED' THEN
            UPDATE don_hang SET trang_thai='SHIPPING',ngay_cap_nhat=UTC_TIMESTAMP(6) WHERE ma=v_order;
        END IF;
        IF p_status='DELIVERED' AND NOT EXISTS(
            SELECT 1 FROM chi_tiet_don_hang i WHERE i.ma_don_hang=v_order AND i.so_luong>
            (SELECT COALESCE(SUM(d.so_luong),0) FROM chi_tiet_kien_hang d JOIN kien_hang p ON p.ma=d.ma_kien_hang
             WHERE d.ma_chi_tiet_don_hang=i.ma AND p.trang_thai='DELIVERED')) THEN
            UPDATE don_hang SET trang_thai='DELIVERED',ngay_cap_nhat=UTC_TIMESTAMP(6) WHERE ma=v_order;
        END IF;
    END IF;
    CALL sp_get_package(p_actor,p_id);
END$$

DELIMITER ;
