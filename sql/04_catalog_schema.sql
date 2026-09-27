-- MySQL 8.0.16+ / InnoDB. Timestamps stored in UTC.
SET time_zone = '+00:00';

START TRANSACTION;

CREATE TABLE IF NOT EXISTS countries (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(50) NOT NULL CHECK (code REGEXP '^[A-Z0-9][A-Z0-9_.-]{0,49}$'),
    name VARCHAR(150) NOT NULL CHECK (length(trim(name)) > 0),
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6), CHECK (code REGEXP '^[A-Z]{2}$'),
    UNIQUE INDEX uq_countries_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS units (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(50) NOT NULL CHECK (code REGEXP '^[A-Z0-9][A-Z0-9_.-]{0,49}$'),
    name VARCHAR(150) NOT NULL CHECK (length(trim(name)) > 0),
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    UNIQUE INDEX uq_units_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS package_types (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(50) NOT NULL CHECK (code REGEXP '^[A-Z0-9][A-Z0-9_.-]{0,49}$'),
    name VARCHAR(150) NOT NULL CHECK (length(trim(name)) > 0),
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    UNIQUE INDEX uq_package_types_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS categories (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(50) NOT NULL CHECK (code REGEXP '^[A-Z0-9][A-Z0-9_.-]{0,49}$'),
    name VARCHAR(150) NOT NULL CHECK (length(trim(name)) > 0),
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    UNIQUE INDEX uq_categories_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS products (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    sku VARCHAR(50) NOT NULL CHECK (sku REGEXP '^[A-Z0-9][A-Z0-9_.-]{0,49}$'),
    name VARCHAR(255) NOT NULL CHECK (length(trim(name)) > 0),
    reference_price NUMERIC(18,4) NOT NULL CHECK (reference_price >= 0),
    currency_code VARCHAR(3) NOT NULL DEFAULT 'CNY' CHECK (currency_code IN ('CNY','USD','VND')),
    source_url VARCHAR(2048),
    image_url VARCHAR(2048),
    description TEXT,
    origin_country_id BIGINT,
    shipping_country_id BIGINT,
    unit_id BIGINT,
    package_type_id BIGINT,
    category_id BIGINT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    FOREIGN KEY (origin_country_id) REFERENCES countries(id),
    FOREIGN KEY (shipping_country_id) REFERENCES countries(id),
    FOREIGN KEY (unit_id) REFERENCES units(id),
    FOREIGN KEY (package_type_id) REFERENCES package_types(id),
    FOREIGN KEY (category_id) REFERENCES categories(id),
    UNIQUE INDEX uq_products_sku (sku),
    INDEX ix_products_category (category_id),
    INDEX ix_products_origin_country (origin_country_id),
    INDEX ix_products_shipping_country (shipping_country_id),
    INDEX ix_products_unit (unit_id),
    INDEX ix_products_package_type (package_type_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS brand_rights (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    brand_name VARCHAR(150) NOT NULL CHECK (length(trim(brand_name)) > 0),
    holder_name VARCHAR(255) NOT NULL CHECK (length(trim(holder_name)) > 0),
    right_type VARCHAR(30) NOT NULL CHECK (right_type IN ('COPYRIGHT','DISTRIBUTION_AUTHORIZATION')),
    product_id BIGINT,
    category_id BIGINT,
    document_url VARCHAR(2048),
    valid_from DATE,
    valid_until DATE,
    note TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT ck_brand_right_target CHECK ((product_id IS NOT NULL) <> (category_id IS NOT NULL)),
    CONSTRAINT ck_brand_right_dates CHECK (valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from),
    FOREIGN KEY (product_id) REFERENCES products(id),
    FOREIGN KEY (category_id) REFERENCES categories(id),
    INDEX ix_brand_rights_product (product_id),
    INDEX ix_brand_rights_category (category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

COMMIT;
