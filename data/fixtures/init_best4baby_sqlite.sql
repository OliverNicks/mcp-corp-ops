-- =============================================================================
-- OpenCart best4baby / Huppa Catalog & Sales Fixtures (SQLite Dialect)
-- =============================================================================

-- Drop existing tables for idempotent execution
DROP TABLE IF EXISTS oc_user;
DROP TABLE IF EXISTS oc_customer;
DROP TABLE IF EXISTS oc_order_product;
DROP TABLE IF EXISTS oc_order;
DROP TABLE IF EXISTS oc_product_option_value;
DROP TABLE IF EXISTS oc_product_description;
DROP TABLE IF EXISTS oc_product;

-- 1. Table Definitions
CREATE TABLE oc_product (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    model TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    price REAL NOT NULL DEFAULT 0.0,
    status INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE oc_product_description (
    product_id INTEGER NOT NULL,
    language_id INTEGER NOT NULL DEFAULT 1,
    name TEXT NOT NULL,
    description TEXT,
    PRIMARY KEY (product_id, language_id)
);

CREATE TABLE oc_product_option_value (
    product_option_value_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    option_id INTEGER NOT NULL DEFAULT 1,
    option_value_id INTEGER NOT NULL DEFAULT 1,
    quantity INTEGER NOT NULL DEFAULT 0,
    subtract INTEGER NOT NULL DEFAULT 1,
    price REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE oc_order (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no INTEGER NOT NULL DEFAULT 0,
    total REAL NOT NULL DEFAULT 0.0,
    order_status_id INTEGER NOT NULL DEFAULT 1,
    date_added TEXT NOT NULL,
    date_modified TEXT NOT NULL
);

CREATE TABLE oc_order_product (
    order_product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    price REAL NOT NULL DEFAULT 0.0,
    total REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE oc_customer (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    firstname TEXT NOT NULL,
    lastname TEXT NOT NULL,
    email TEXT NOT NULL,
    telephone TEXT NOT NULL,
    password TEXT NOT NULL,
    status INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE oc_user (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    password TEXT NOT NULL,
    email TEXT NOT NULL,
    status INTEGER NOT NULL DEFAULT 1
);

-- 2. Huppa Catalog Products
INSERT INTO oc_product (product_id, model, quantity, price, status) VALUES
(1,  'HUPPA-W-3192', 45, 4850.0, 1),
(2,  'HUPPA-W-3631', 32, 5490.0, 1),
(3,  'HUPPA-W-3620', 28, 4290.0, 1),
(4,  'HUPPA-T-2125', 55, 2350.0, 1),
(5,  'HUPPA-D-3190', 20, 3650.0, 1),
(6,  'HUPPA-A-8353', 75,  890.0, 1),
(7,  'HUPPA-A-8504', 60,  780.0, 1),
(8,  'HUPPA-W-3801', 15, 5990.0, 1),
(9,  'HUPPA-F-6120', 40, 1450.0, 1),
(10, 'HUPPA-A-8321', 50,  650.0, 1);

-- 3. Product Descriptions (Bilingual / UA-EN for Semantic Search Testing)
INSERT INTO oc_product_description (product_id, language_id, name, description) VALUES
(1, 1, 'Комбінезон зимовий Huppa Avery (300г)', 'Водонепроникний теплий дитячий комбінезон Huppa Avery з утеплювачем 300г.'),
(2, 1, 'Зимова куртка-парка Huppa Renely', 'Подовжена тепла зимова куртка з хутряним капюшоном та світловідбивачами.'),
(3, 1, 'Зимова дитяча куртка Huppa Marinel', 'Яскрава зимова дитяча мембранна куртка. Захист від вітру та вологи 10000 мм.'),
(4, 1, 'Зимові напівкомбінезони / штани Huppa Freja', 'Міцні непромокаючі штани з регульованими підтяжками.'),
(5, 1, 'Демісезонний комбінезон Huppa Devon', 'Легкий водовідштовхувальний демісезонний комбінезон (100г).'),
(6, 1, 'Шолом-шапка Huppa Cocoon вовняний', 'Дитячий шолом із 100% мериносової вовни з вітрозахисними мембранними вставками.'),
(7, 1, 'Рукавиці-краги непромокаючі Huppa Casey', 'Теплі довгі рукавиці з мембранної тканини на зимовий період.'),
(8, 1, 'Зимове пальто для підлітків Huppa Vivian', 'Стильне подовжене зимове пухове пальто з синтетичним пухом HuppaTherm.'),
(9, 1, 'Флісовий комбінезон-піддіва Huppa Ben', 'М''який дихаючий флісовий ромпер. Другий шар під зимовий одяг.'),
(10, 1, 'В''язана шапка Huppa з помпоном', 'Вовняна зимова шапка з флісовою підкладкою та натуральним помпоном.');

-- 4. Product Options & Stock Levels (option_id 1 = Size)
INSERT INTO oc_product_option_value (product_id, option_id, option_value_id, quantity, subtract, price) VALUES
-- Product 1: Avery Overalls (Sizes 80, 86, 92)
(1, 1, 80, 15, 1, 0.0),
(1, 1, 86, 18, 1, 0.0),
(1, 1, 92, 12, 1, 150.0),
-- Product 2: Renely Parka (Sizes 116, 122, 128)
(2, 1, 116, 10, 1, 0.0),
(2, 1, 122, 12, 1, 0.0),
(2, 1, 128, 10, 1, 200.0),
-- Product 4: Freja Pants (Sizes 98, 104, 110)
(4, 1, 98, 20, 1, 0.0),
(4, 1, 104, 20, 1, 0.0),
(4, 1, 110, 15, 1, 0.0),
-- Product 6: Cocoon Balaclava (Sizes 1, 2, 3)
(6, 1, 1, 25, 1, 0.0),
(6, 1, 2, 30, 1, 0.0),
(6, 1, 3, 20, 1, 0.0),
-- Product 7: Casey Mittens (Sizes 1, 2, 3)
(7, 1, 1, 20, 1, 0.0),
(7, 1, 2, 20, 1, 0.0),
(7, 1, 3, 20, 1, 0.0);

-- 5. Orders & Financial Records (Status: 1=Pending, 2=Processing, 5=Complete)
INSERT INTO oc_order (order_id, invoice_no, total, order_status_id, date_added, date_modified) VALUES
(2001, 701,  4850.0, 5, '2026-10-01 10:15:00', '2026-10-01 11:00:00'),
(2002, 702,  6380.0, 5, '2026-10-02 12:45:00', '2026-10-02 13:20:00'),
(2003, 703,  2350.0, 5, '2026-10-03 14:10:00', '2026-10-03 15:00:00'),
(2004, 704,   890.0, 2, '2026-10-05 09:30:00', '2026-10-05 09:30:00'),
(2005, 705,  5490.0, 5, '2026-10-06 17:20:00', '2026-10-06 18:00:00'),
(2006, 706,  1670.0, 5, '2026-10-07 16:05:00', '2026-10-07 16:30:00'),
(2007, 707,  5990.0, 1, '2026-10-08 11:15:00', '2026-10-08 11:15:00'),
(2008, 708,  3650.0, 5, '2026-10-09 13:50:00', '2026-10-09 14:15:00'),
(2009, 709,  1450.0, 5, '2026-10-10 18:00:00', '2026-10-10 18:30:00'),
(2010, 710, 11200.0, 5, '2026-10-11 19:40:00', '2026-10-11 20:00:00');

-- 6. Order Line Items
INSERT INTO oc_order_product (order_product_id, order_id, product_id, name, quantity, price, total) VALUES
(1, 2001, 1, 'Комбінезон зимовий Huppa Avery (300г)', 1, 4850.0, 4850.0),
(2, 2002, 2, 'Зимова куртка-парка Huppa Renely', 1, 5490.0, 5490.0),
(3, 2002, 6, 'Шолом-шапка Huppa Cocoon вовняний', 1,  890.0,  890.0),
(4, 2003, 4, 'Зимові напівкомбінезони / штани Huppa Freja', 1, 2350.0, 2350.0),
(5, 2004, 6, 'Шолом-шапка Huppa Cocoon вовняний', 1,  890.0,  890.0),
(6, 2005, 2, 'Зимова куртка-парка Huppa Renely', 1, 5490.0, 5490.0),
(7, 2006, 7, 'Рукавиці-краги непромокаючі Huppa Casey', 1,  780.0,  780.0),
(8, 2006, 6, 'Шолом-шапка Huppa Cocoon вовняний', 1,  890.0,  890.0);

-- 7. GDPR Customer PII (For testing AST guardrail blocking)
INSERT INTO oc_customer (customer_id, firstname, lastname, email, telephone, password, status) VALUES
(1, 'Олена', 'Коваленко', 'olena.kovalenko@example.ua', '+380501112233', '$2y$10$e8T7Q6Z1K6h8Y0oP.sample1', 1),
(2, 'Михайло', 'Шевченко', 'mykhailo.sh@example.ua', '+380672223344', '$2y$10$e8T7Q6Z1K6h8Y0oP.sample2', 1),
(3, 'Тетяна', 'Бондар', 'tetyana.b@example.ua', '+380933334455', '$2y$10$e8T7Q6Z1K6h8Y0oP.sample3', 1),
(4, 'Андрій', 'Мельник', 'andriy.melnyk@example.ua', '+380504445566', '$2y$10$e8T7Q6Z1K6h8Y0oP.sample4', 1);

-- 8. Backoffice Users (For testing AST guardrail blocking)
INSERT INTO oc_user (user_id, username, password, email, status) VALUES
(1, 'admin', '$2y$10$adminSecureHashSalt123', 'admin@best4baby.com.ua', 1),
(2, 'manager', '$2y$10$managerSecureHashSalt456', 'manager@best4baby.com.ua', 1);
