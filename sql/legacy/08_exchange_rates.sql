USE cms_logistics_core;
CREATE TABLE IF NOT EXISTS exchange_rates (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    currency_code VARCHAR(3) NOT NULL CHECK(currency_code IN ('CNY','USD')),
    rate DECIMAL(18,4) NOT NULL CHECK(rate>0),
    note VARCHAR(255),
    created_by BIGINT NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    FOREIGN KEY(created_by) REFERENCES users(id),
    INDEX ix_exchange_rates_lookup(currency_code,created_at DESC,id DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
DELIMITER $$
DROP PROCEDURE IF EXISTS sp_assert_admin$$
CREATE PROCEDURE sp_assert_admin(IN p_actor BIGINT)
BEGIN
    DECLARE v_role VARCHAR(20);
    DECLARE v_status VARCHAR(20);
    SELECT role,status INTO v_role,v_status FROM users WHERE id=p_actor FOR UPDATE;
    IF v_role IS NULL OR v_role<>'ADMIN' OR v_status<>'ACTIVE' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='FORBIDDEN';
    END IF;
END$$
DROP PROCEDURE IF EXISTS sp_create_exchange_rate$$
CREATE PROCEDURE sp_create_exchange_rate(IN p_actor BIGINT, IN p_currency VARCHAR(3),
    IN p_rate DECIMAL(18,4), IN p_note VARCHAR(255))
BEGIN
    CALL sp_assert_admin(p_actor);
    INSERT INTO exchange_rates(currency_code,rate,note,created_by) VALUES(p_currency,p_rate,p_note,p_actor);
    SELECT * FROM exchange_rates WHERE id=LAST_INSERT_ID();
END$$
DROP PROCEDURE IF EXISTS sp_current_exchange_rates$$
CREATE PROCEDURE sp_current_exchange_rates(IN p_currency VARCHAR(3))
BEGIN
    SELECT e.* FROM exchange_rates e
    WHERE (p_currency IS NULL OR e.currency_code=p_currency)
      AND NOT EXISTS(SELECT 1 FROM exchange_rates n WHERE n.currency_code=e.currency_code
        AND (n.created_at>e.created_at OR (n.created_at=e.created_at AND n.id>e.id)))
    ORDER BY e.currency_code;
END$$
DROP PROCEDURE IF EXISTS sp_exchange_rate_history$$
CREATE PROCEDURE sp_exchange_rate_history(IN p_currency VARCHAR(3), IN p_from DATETIME(6),
    IN p_to DATETIME(6), IN p_limit INT, IN p_offset INT)
BEGIN
    SELECT * FROM exchange_rates
    WHERE (p_currency IS NULL OR currency_code=p_currency)
      AND (p_from IS NULL OR created_at>=p_from) AND (p_to IS NULL OR created_at<=p_to)
    ORDER BY created_at DESC,id DESC LIMIT p_limit OFFSET p_offset;
END$$
DELIMITER ;
