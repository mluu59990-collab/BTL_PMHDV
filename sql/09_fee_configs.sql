USE cms_logistics_core;
CREATE TABLE IF NOT EXISTS fee_configs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    fee_type VARCHAR(50) NOT NULL,
    description VARCHAR(255),
    unit VARCHAR(20) NOT NULL CHECK(unit IN ('PERCENT','VND','VND_PER_KG','VND_PER_M3','VND_PER_ITEM','VND_PER_PACKAGE')),
    effective_date DATE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    FOREIGN KEY(created_by) REFERENCES users(id),
    INDEX ix_fee_config_current(fee_type,unit,is_active,effective_date,id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS fee_tiers (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    config_id BIGINT NOT NULL,
    tier_min DECIMAL(18,4) NOT NULL CHECK(tier_min>=0),
    tier_max DECIMAL(18,4),
    value DECIMAL(18,4) NOT NULL CHECK(value>=0),
    CHECK(tier_max IS NULL OR tier_max>tier_min),
    FOREIGN KEY(config_id) REFERENCES fee_configs(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE OR REPLACE VIEW fee_config_details AS
SELECT f.*, COALESCE((SELECT JSON_ARRAYAGG(JSON_OBJECT('tier_min',CAST(t.tier_min AS CHAR),
    'tier_max',CAST(t.tier_max AS CHAR),'value',CAST(t.value AS CHAR)))
    FROM fee_tiers t WHERE t.config_id=f.id),JSON_ARRAY()) AS tiers
FROM fee_configs f;
DELIMITER $$
DROP PROCEDURE IF EXISTS sp_create_fee_config$$
CREATE PROCEDURE sp_create_fee_config(IN p_actor BIGINT, IN p_type VARCHAR(50), IN p_description VARCHAR(255),
    IN p_unit VARCHAR(20), IN p_date DATE, IN p_tiers JSON)
BEGIN
    DECLARE v_id BIGINT;
    CALL sp_assert_admin(p_actor);
    IF JSON_TYPE(p_tiers)<>'ARRAY' OR JSON_LENGTH(p_tiers)=0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_TIERS';
    END IF;
    IF EXISTS (
        SELECT 1 FROM JSON_TABLE(p_tiers,'$[*]' COLUMNS(n FOR ORDINALITY,
            lo DECIMAL(18,4) PATH '$.tier_min',hi DECIMAL(18,4) PATH '$.tier_max')) a
        JOIN JSON_TABLE(p_tiers,'$[*]' COLUMNS(n FOR ORDINALITY,
            lo DECIMAL(18,4) PATH '$.tier_min',hi DECIMAL(18,4) PATH '$.tier_max')) b
        ON a.n<b.n AND (b.hi IS NULL OR a.lo<b.hi) AND (a.hi IS NULL OR b.lo<a.hi)
    ) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='OVERLAPPING_TIERS'; END IF;
    IF p_unit='PERCENT' AND EXISTS(SELECT 1 FROM JSON_TABLE(p_tiers,'$[*]'
        COLUMNS(v DECIMAL(18,4) PATH '$.value')) t WHERE t.v>100) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='INVALID_PERCENT';
    END IF;
    INSERT INTO fee_configs(fee_type,description,unit,effective_date,created_by)
    VALUES(p_type,p_description,p_unit,p_date,p_actor);
    SET v_id=LAST_INSERT_ID();
    INSERT INTO fee_tiers(config_id,tier_min,tier_max,value)
    SELECT v_id,t.lo,t.hi,t.v FROM JSON_TABLE(p_tiers,'$[*]' COLUMNS(
        lo DECIMAL(18,4) PATH '$.tier_min',hi DECIMAL(18,4) PATH '$.tier_max',v DECIMAL(18,4) PATH '$.value')) t;
    SELECT * FROM fee_config_details WHERE id=v_id;
END$$
DROP PROCEDURE IF EXISTS sp_get_fee_config$$
CREATE PROCEDURE sp_get_fee_config(IN p_id BIGINT)
BEGIN
    SELECT * FROM fee_config_details WHERE id=p_id;
END$$
DROP PROCEDURE IF EXISTS sp_list_fee_configs$$
CREATE PROCEDURE sp_list_fee_configs(IN p_type VARCHAR(50),IN p_active BOOLEAN,IN p_limit INT,IN p_offset INT)
BEGIN
    SELECT * FROM fee_config_details WHERE (p_type IS NULL OR fee_type=p_type)
        AND (NOT p_active OR is_active=TRUE)
    ORDER BY effective_date DESC,id DESC LIMIT p_limit OFFSET p_offset;
END$$
DROP PROCEDURE IF EXISTS sp_current_fee_configs$$
CREATE PROCEDURE sp_current_fee_configs(IN p_type VARCHAR(50),IN p_unit VARCHAR(20),IN p_date DATE)
BEGIN
    SELECT f.* FROM fee_config_details f
    WHERE f.is_active=TRUE AND f.effective_date<=p_date
      AND (p_type IS NULL OR f.fee_type=p_type) AND (p_unit IS NULL OR f.unit=p_unit)
      AND NOT EXISTS(SELECT 1 FROM fee_configs n WHERE n.fee_type=f.fee_type AND n.unit=f.unit
        AND n.is_active=TRUE AND n.effective_date<=p_date
        AND (n.effective_date>f.effective_date OR (n.effective_date=f.effective_date AND n.id>f.id)))
    ORDER BY f.fee_type,f.unit;
END$$
DROP PROCEDURE IF EXISTS sp_update_fee_config$$
CREATE PROCEDURE sp_update_fee_config(IN p_actor BIGINT,IN p_id BIGINT,IN p_set_description BOOLEAN,
    IN p_description VARCHAR(255),IN p_active BOOLEAN)
BEGIN
    DECLARE v_id BIGINT;
    CALL sp_assert_admin(p_actor);
    SELECT id INTO v_id FROM fee_configs WHERE id=p_id FOR UPDATE;
    IF v_id IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='NOT_FOUND'; END IF;
    UPDATE fee_configs SET description=IF(p_set_description,p_description,description),
        is_active=COALESCE(p_active,is_active),updated_at=UTC_TIMESTAMP(6) WHERE id=p_id;
    SELECT * FROM fee_config_details WHERE id=p_id;
END$$
DELIMITER ;
