CREATE DATABASE IF NOT EXISTS best4baby;
USE best4baby;

-- 1. Create Catalog Tables
CREATE TABLE IF NOT EXISTS oc_product (
    product_id INT AUTO_INCREMENT PRIMARY KEY,
    model VARCHAR(64) NOT NULL,
    quantity INT NOT NULL DEFAULT 0,
    price DECIMAL(15,4) NOT NULL DEFAULT 0.0000,
    status TINYINT(1) NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS oc_product_description (
    product_id INT NOT NULL,
    language_id INT NOT NULL DEFAULT 1,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    PRIMARY KEY (product_id, language_id)
);

CREATE TABLE IF NOT EXISTS oc_product_option_value (
    product_option_value_id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    option_id INT NOT NULL DEFAULT 1,
    option_value_id INT NOT NULL DEFAULT 1,
    quantity INT NOT NULL DEFAULT 0,
    subtract TINYINT(1) NOT NULL DEFAULT 1,
    price DECIMAL(15,4) NOT NULL DEFAULT 0.0000
);

-- 2. Create Order & Customer Tables
CREATE TABLE IF NOT EXISTS oc_order (
    order_id INT AUTO_INCREMENT PRIMARY KEY,
    invoice_no INT NOT NULL DEFAULT 0,
    total DECIMAL(15,4) NOT NULL DEFAULT 0.0000,
    order_status_id INT NOT NULL DEFAULT 1,
    date_added DATETIME NOT NULL,
    date_modified DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS oc_customer (
    customer_id INT AUTO_INCREMENT PRIMARY KEY,
    firstname VARCHAR(32) NOT NULL,
    lastname VARCHAR(32) NOT NULL,
    email VARCHAR(96) NOT NULL,
    telephone VARCHAR(32) NOT NULL,
    password VARCHAR(255) NOT NULL,
    status TINYINT(1) NOT NULL DEFAULT 1
);

-- 3. Populate Sample Records
INSERT INTO oc_product (product_id, model, quantity, price, status) VALUES
(1, 'STROLL-01', 50, 199.9900, 1),
(2, 'CRIB-02', 20, 299.5000, 1);

INSERT INTO oc_product_description (product_id, language_id, name, description) VALUES
(1, 1, 'Ergonomic Baby Stroller', 'Lightweight compact stroller'),
(2, 1, 'Organic Wood Crib', 'Solid pine baby crib');

INSERT INTO oc_product_option_value (product_id, option_id, option_value_id, quantity, price) VALUES
(1, 1, 1, 45, 0.0000),
(2, 2, 3, 20, 0.0000);

INSERT INTO oc_order (order_id, total, date_added, date_modified) VALUES
(1001, 199.9900, NOW(), NOW());