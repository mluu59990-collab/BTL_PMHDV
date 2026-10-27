-- Thanh toán phí vận chuyển: sổ giao dịch thu/hoàn, không thêm bảng.

-- Chỉ cài procedure, không tạo dữ liệu hoặc kết nối ngân hàng.

USE cms_logistics;

DELIMITER $$

DROP PROCEDURE IF EXISTS sp_payment_actor$$

CREATE PROCEDURE sp_payment_actor(IN p_actor BIGINT,IN p_write BOOLEAN,OUT p_role VARCHAR(20))
BEGIN
    SET p_role=NULL;
    IF p_write THEN
        SELECT vai_tro INTO p_role FROM nguoi_dung WHERE ma=p_actor AND trang_thai='ACTIVE' FOR UPDATE;
    ELSE
        SELECT vai_tro INTO p_role FROM nguoi_dung WHERE ma=p_actor AND trang_thai='ACTIVE';
    END IF;
    IF p_role IS NULL OR p_role NOT IN ('ADMIN','ACCOUNTANT','SALE','CUSTOMER')
       OR (p_write AND p_role NOT IN ('ADMIN','ACCOUNTANT')) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='FORBIDDEN';
    END IF;
END$$

DROP PROCEDURE IF EXISTS sp_lock_payment_order$$

CREATE PROCEDURE sp_lock_payment_order(IN p_actor BIGINT,IN p_order BIGINT,OUT p_status VARCHAR(20),OUT p_fee DECIMAL(18,2))
BEGIN
    DECLARE v_role VARCHAR(20);
    DECLARE v_customer BIGINT;
    DECLARE v_locked BIGINT;
    CALL sp_payment_actor(p_actor,TRUE,v_role);
    SELECT ma_khach_hang INTO v_customer FROM don_hang WHERE ma=p_order;
    IF v_customer IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='NOT_FOUND'; END IF;
    -- Chung thứ tự khóa với API đơn/kiện để thu tiền không chạy đua với sửa phí hoặc hủy đơn.
    SELECT ma INTO v_locked FROM khach_hang WHERE ma=v_customer FOR UPDATE;
    SET p_status=NULL;
    SELECT trang_thai,phi_van_chuyen INTO p_status,p_fee FROM don_hang WHERE ma=p_order FOR UPDATE;
    IF p_status IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='NOT_FOUND'; END IF;
END$$

DROP PROCEDURE IF EXISTS sp_get_payment$$

CREATE PROCEDURE sp_get_payment(IN p_actor BIGINT,IN p_id BIGINT)
BEGIN
    DECLARE v_role VARCHAR(20);
    CALL sp_payment_actor(p_actor,FALSE,v_role);
    SELECT t.ma AS id,t.ma_don_hang AS order_id,t.so_tien AS amount,t.loai_giao_dich AS transaction_type,
        t.phuong_thuc AS method,t.ma_tham_chieu AS reference_code,t.nguoi_tao AS created_by,t.ngay_tao AS created_at FROM thanh_toan t JOIN don_hang o ON o.ma=t.ma_don_hang
    JOIN khach_hang c ON c.ma=o.ma_khach_hang WHERE t.ma=p_id AND (v_role IN ('ADMIN','ACCOUNTANT') OR (v_role='SALE' AND c.ma_nhan_vien_phu_trach=p_actor)
        OR (v_role='CUSTOMER' AND c.ma_nguoi_dung=p_actor));
END$$

DROP PROCEDURE IF EXISTS sp_list_payments$$

CREATE PROCEDURE sp_list_payments(IN p_actor BIGINT,IN p_order BIGINT,IN p_type VARCHAR(10),IN p_method VARCHAR(20),
    IN p_from DATETIME(6),IN p_to DATETIME(6),IN p_search VARCHAR(80),IN p_limit INT,IN p_offset INT)
BEGIN
    DECLARE v_role VARCHAR(20);
    CALL sp_payment_actor(p_actor,FALSE,v_role);
    SELECT t.ma AS id,t.ma_don_hang AS order_id,t.so_tien AS amount,t.loai_giao_dich AS transaction_type,
        t.phuong_thuc AS method,t.ma_tham_chieu AS reference_code,t.nguoi_tao AS created_by,t.ngay_tao AS created_at FROM thanh_toan t JOIN don_hang o ON o.ma=t.ma_don_hang
    JOIN khach_hang c ON c.ma=o.ma_khach_hang WHERE (v_role IN ('ADMIN','ACCOUNTANT') OR (v_role='SALE' AND c.ma_nhan_vien_phu_trach=p_actor)
        OR (v_role='CUSTOMER' AND c.ma_nguoi_dung=p_actor))
      AND (p_order IS NULL OR t.ma_don_hang=p_order) AND (p_type IS NULL OR t.loai_giao_dich=p_type)
      AND (p_method IS NULL OR t.phuong_thuc=p_method)
      AND (p_from IS NULL OR t.ngay_tao>=p_from) AND (p_to IS NULL OR t.ngay_tao<=p_to)
      AND (p_search IS NULL OR LOCATE(p_search,t.ma_tham_chieu)>0)
    ORDER BY t.ngay_tao DESC,t.ma DESC LIMIT p_limit OFFSET p_offset;
END$$

DROP PROCEDURE IF EXISTS sp_order_payment_summary$$

CREATE PROCEDURE sp_order_payment_summary(IN p_actor BIGINT,IN p_order BIGINT)
BEGIN
    DECLARE v_role VARCHAR(20);
    CALL sp_payment_actor(p_actor,FALSE,v_role);
    SELECT o.ma AS order_id,o.ma_don AS order_code,o.trang_thai AS order_status,'VND' AS currency,
        o.phi_van_chuyen AS shipping_fee,COALESCE(t.paid,0.00) AS total_paid,
        COALESCE(t.refunded,0.00) AS total_refunded,
        COALESCE(t.paid,0.00)-COALESCE(t.refunded,0.00) AS net_paid,
        GREATEST(IF(o.trang_thai='CANCELLED',0.00,o.phi_van_chuyen)-COALESCE(t.paid,0.00)+COALESCE(t.refunded,0.00),0.00) AS amount_due,
        GREATEST(COALESCE(t.paid,0.00)-COALESCE(t.refunded,0.00)-IF(o.trang_thai='CANCELLED',0.00,o.phi_van_chuyen),0.00) AS refund_due,
        CASE
            WHEN COALESCE(t.paid,0)<COALESCE(t.refunded,0) THEN 'INVALID'
            WHEN o.trang_thai='CANCELLED' AND COALESCE(t.paid,0)>COALESCE(t.refunded,0) THEN 'REFUND_DUE'
            WHEN o.trang_thai='CANCELLED' THEN 'CANCELLED'
            WHEN COALESCE(t.paid,0)-COALESCE(t.refunded,0)>o.phi_van_chuyen THEN 'OVERPAID'
            WHEN COALESCE(t.paid,0)-COALESCE(t.refunded,0)=o.phi_van_chuyen THEN 'PAID'
            WHEN COALESCE(t.paid,0)=COALESCE(t.refunded,0) AND COALESCE(t.refunded,0)>0 THEN 'REFUNDED'
            WHEN COALESCE(t.paid,0)=COALESCE(t.refunded,0) THEN 'UNPAID'
            ELSE 'PARTIAL'
        END AS payment_status
    FROM don_hang o JOIN khach_hang c ON c.ma=o.ma_khach_hang
    LEFT JOIN (SELECT ma_don_hang,
        SUM(IF(loai_giao_dich='PAYMENT',so_tien,0.00)) AS paid,
        SUM(IF(loai_giao_dich='REFUND',so_tien,0.00)) AS refunded
        FROM thanh_toan WHERE ma_don_hang=p_order GROUP BY ma_don_hang) t ON t.ma_don_hang=o.ma
    WHERE o.ma=p_order AND (v_role IN ('ADMIN','ACCOUNTANT') OR (v_role='SALE' AND c.ma_nhan_vien_phu_trach=p_actor)
        OR (v_role='CUSTOMER' AND c.ma_nguoi_dung=p_actor));
END$$

DROP PROCEDURE IF EXISTS sp_record_payment$$

CREATE PROCEDURE sp_record_payment(IN p_actor BIGINT,IN p_order BIGINT,IN p_amount DECIMAL(18,2),
    IN p_type VARCHAR(10),IN p_method VARCHAR(20),IN p_reference VARCHAR(80))
BEGIN
    DECLARE v_status VARCHAR(20);
    DECLARE v_fee DECIMAL(18,2);
    DECLARE v_paid DECIMAL(38,2);
    DECLARE v_refunded DECIMAL(38,2);
    DECLARE v_id BIGINT;
    DECLARE v_order BIGINT;
    DECLARE v_amount DECIMAL(18,2);
    DECLARE v_type VARCHAR(10);
    DECLARE v_method VARCHAR(20);
    DECLARE v_replay BOOLEAN DEFAULT FALSE;
    CALL sp_lock_payment_order(p_actor,p_order,v_status,v_fee);
    IF p_amount IS NULL OR p_amount<=0 OR p_type IS NULL OR p_type NOT IN ('PAYMENT','REFUND')
       OR p_method IS NULL OR p_method NOT IN ('CASH','BANK_TRANSFER')
       OR p_reference IS NULL OR CHAR_LENGTH(TRIM(p_reference))<3 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_PAYMENT';
    END IF;
    SELECT ma,ma_don_hang,so_tien,loai_giao_dich,phuong_thuc
    INTO v_id,v_order,v_amount,v_type,v_method FROM thanh_toan WHERE ma_tham_chieu=p_reference;
    IF v_id IS NOT NULL THEN
        IF v_order<>p_order OR v_amount<>p_amount OR v_type<>p_type OR v_method<>p_method THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='REFERENCE_CONFLICT';
        END IF;
        SET v_replay=TRUE;
    ELSE
        SELECT COALESCE(SUM(IF(loai_giao_dich='PAYMENT',so_tien,0.00)),0.00),
               COALESCE(SUM(IF(loai_giao_dich='REFUND',so_tien,0.00)),0.00)
        INTO v_paid,v_refunded FROM thanh_toan WHERE ma_don_hang=p_order;
        IF v_paid<v_refunded THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='LEDGER_INCONSISTENT'; END IF;
        IF p_type='PAYMENT' THEN
            IF v_status NOT IN ('CONFIRMED','SHIPPING','DELIVERED') THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ORDER_NOT_PAYABLE';
            END IF;
            IF p_amount>v_fee-v_paid+v_refunded THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='OVERPAYMENT';
            END IF;
        ELSE
            IF p_amount>v_paid-v_refunded THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='OVER_REFUND';
            END IF;
        END IF;
        INSERT INTO thanh_toan(ma_don_hang,so_tien,loai_giao_dich,phuong_thuc,ma_tham_chieu,nguoi_tao)
        VALUES(p_order,p_amount,p_type,p_method,p_reference,p_actor);
        SET v_id=LAST_INSERT_ID();
    END IF;
    SELECT t.ma AS id,t.ma_don_hang AS order_id,t.so_tien AS amount,t.loai_giao_dich AS transaction_type,
        t.phuong_thuc AS method,t.ma_tham_chieu AS reference_code,t.nguoi_tao AS created_by,t.ngay_tao AS created_at,v_replay AS replayed FROM thanh_toan t WHERE t.ma=v_id;
END$$

DELIMITER ;
