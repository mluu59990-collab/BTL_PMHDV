-- Minh chứng dữ liệu đã kiểm thử; các câu lệnh chỉ đọc.
USE cms_postman_577eaca804ee;
SHOW TABLES;

-- Buổi 2: sản phẩm và dữ liệu liên kết.
SELECT p.id, p.sku, p.name, p.reference_price, p.currency_code,
       c.name AS category, co.name AS origin_country, p.is_active
FROM products p
LEFT JOIN categories c ON c.id = p.category_id
LEFT JOIN countries co ON co.id = p.origin_country_id;
SELECT id, brand_name, holder_name, right_type, product_id, is_active FROM brand_rights;

-- Buổi 3: khách hàng và Sale phụ trách.
SELECT c.id, c.code, c.name, c.phone, u.username AS sale, c.credit_limit, c.is_active
FROM customers c LEFT JOIN users u ON u.id = c.sale_id;
SELECT id, tracking_code, customer_id, shipped_on, is_active FROM crm_trackings;
SELECT id, customer_id, title, due_on, status, is_active FROM care_tasks;
SELECT id, sale_id, period_type, period_start, target_amount, actual_amount FROM sales_plans;
SELECT id, customer_id, period_start, period_end, rating, comment FROM service_reviews;
SELECT m.id, c.name AS customer, p.name AS vip_package, m.valid_from, m.valid_until, m.is_active
FROM vip_memberships m JOIN customers c ON c.id = m.customer_id
JOIN vip_packages p ON p.id = m.package_id;
