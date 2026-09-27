-- MySQL 8.0.16+ / InnoDB. Timestamps stored in UTC.
SET time_zone = '+00:00';

CREATE TABLE IF NOT EXISTS roles (
    id          SMALLINT AUTO_INCREMENT PRIMARY KEY,
    code        VARCHAR(30)  NOT NULL UNIQUE,
    name        VARCHAR(100) NOT NULL,
    description TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS users (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL,
    email         VARCHAR(255),
    full_name     VARCHAR(150) NOT NULL,
    phone         VARCHAR(20),
    password_hash VARCHAR(255) NOT NULL,
    role_id       SMALLINT     NOT NULL,
    balance       NUMERIC(18,2) NOT NULL DEFAULT 0,
    status        VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE',
    last_login_at DATETIME(6),
    created_at    DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at    DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT ck_users_status CHECK (status IN ('ACTIVE', 'INACTIVE', 'LOCKED')),
    FOREIGN KEY (role_id) REFERENCES roles(id),
    UNIQUE INDEX uq_users_username_lower (username),
    UNIQUE INDEX uq_users_email_lower (email),
    INDEX ix_users_role_id (role_id),
    INDEX ix_users_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id    BIGINT      NOT NULL,
    jti        VARCHAR(64) NOT NULL UNIQUE,
    expires_at DATETIME(6) NOT NULL,
    revoked_at DATETIME(6),
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX ix_refresh_tokens_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS exchange_rates (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    currency_code VARCHAR(3)    NOT NULL,
    rate          NUMERIC(18,4) NOT NULL,
    note          VARCHAR(255),
    created_by    BIGINT,
    created_at    DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT ck_exchange_rates_code CHECK (currency_code REGEXP '^[A-Z]{3}$'),
    CONSTRAINT ck_exchange_rates_rate CHECK (rate > 0),
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX ix_exchange_rates_lookup (currency_code, created_at DESC, id DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS fee_configs (
    id             BIGINT AUTO_INCREMENT PRIMARY KEY,
    fee_type       VARCHAR(50)   NOT NULL,
    description    VARCHAR(255),
    value          NUMERIC(18,4) NOT NULL,
    unit           VARCHAR(20)   NOT NULL,
    tier_min       NUMERIC(18,4),
    tier_max       NUMERIC(18,4),
    effective_date DATE          NOT NULL DEFAULT (DATE(UTC_TIMESTAMP() + INTERVAL 7 HOUR)),
    is_active      BOOLEAN       NOT NULL DEFAULT TRUE,
    created_by     BIGINT,
    created_at     DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at     DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT ck_fee_configs_type  CHECK (fee_type REGEXP '^[A-Z][A-Z0-9_]{1,49}$'),
    CONSTRAINT ck_fee_configs_unit  CHECK (unit IN ('PERCENT','VND','VND_PER_KG','VND_PER_M3','VND_PER_ITEM','VND_PER_PACKAGE')),
    CONSTRAINT ck_fee_configs_value CHECK (value >= 0),
    CONSTRAINT ck_fee_configs_tier  CHECK (tier_min IS NULL OR tier_max IS NULL OR tier_max > tier_min),
    CONSTRAINT ck_fee_configs_pct   CHECK (unit <> 'PERCENT' OR value <= 100),
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX ix_fee_configs_lookup (fee_type, is_active, effective_date DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
