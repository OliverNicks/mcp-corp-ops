-- =============================================================================
-- OpenCart best4baby / Huppa Catalog & Sales Fixture
-- =============================================================================
CREATE DATABASE IF NOT EXISTS best4baby;
USE best4baby;

-- 1. Table Definitions
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

-- Clean existing data if reloading
TRUNCATE TABLE oc_product;
TRUNCATE TABLE oc_product_description;
TRUNCATE TABLE oc_product_option_value;
TRUNCATE TABLE oc_order;
TRUNCATE TABLE oc_customer;

-- 2. Huppa Catalog Products (UAH Pricing, Standard Winter/Demi-season Lineup)
INSERT INTO oc_product (product_id, model, quantity, price, status) VALUES
(1,  'HUPPA-W-3192', 45, 4850.0000, 1), -- Huppa Avery Winter Overall (300g)
(2,  'HUPPA-W-3631', 32, 5490.0000, 1), -- Huppa Renely Parka Jacket
(3,  'HUPPA-W-3620', 28, 4290.0000, 1), -- Huppa Marinel Winter Jacket
(4,  'HUPPA-T-2125', 55, 2350.0000, 1), -- Huppa Freja Winter Pants / Trousers
(5,  'HUPPA-D-3190', 20, 3650.0000, 1), -- Huppa Devon Demi-season Overalls
(6,  'HUPPA-A-8353', 75,  890.0000, 1), -- Huppa Cocoon Merino Wool Balaclava
(7,  'HUPPA-A-8504', 60,  780.0000, 1), -- Huppa Casey Waterproof Mittens
(8,  'HUPPA-W-3801', 15, 5990.0000, 1), -- Huppa Vivian Teen Winter Coat
(9,  'HUPPA-F-6120', 40, 1450.0000, 1), -- Huppa Ben Fleece Romper Underlayer
(10, 'HUPPA-A-8321', 50,  650.0000, 1); -- Huppa Knitted Beanie Hat

-- 3. Product Descriptions (Bilingual / UA-EN for Semantic Search Testing)
INSERT INTO oc_product_description (product_id, language_id, name, description) VALUES
(1, 1, 'Комбінезон зимовий Huppa Avery (300г)', 'Водонепроникний теплий дитячий комбінезон Huppa Avery з утеплювачем 300г. Мембрана 10000 мм, світловідбивачі, паропроникність 10000 г/м2.'),
(2, 1, 'Зимова куртка-парка Huppa Renely', 'Подовжена тепла зимова куртка з хутряним капюшоном. Світловідбиваючі елементи та вологозахисна мембрана.'),
(3, 1, 'Зимова дитяча куртка Huppa Marinel', 'Яскрава зимова дитяча мембранна куртка. Захист від вітру та вологи 10000 мм.'),
(4, 1, 'Зимові напівкомбінезони / штани Huppa Freja', 'Міцні непромокаючі штани з регульованими підтяжками та посиленими вставками на колінах.'),
(5, 1, 'Демісезонний комбінезон Huppa Devon', 'Легкий водовідштовхувальний демісезонний комбінезон без масивного утеплювача (100г). Ідеально для весни та осені.'),
(6, 1, 'Шолом-шапка Huppa Cocoon вовняний', 'Дитячий шолом із 100% мериносової вовни з вітрозахисними мембранними вставками на вухах.'),
(7, 1, 'Рукавиці-краги непромокаючі Huppa Casey', 'Теплі довгі рукавиці з мембранної тканини на зимовий період. Водонепроникні, з флісовою підкладкою.'),
(8, 1, 'Зимове пальто для підлітків Huppa Vivian', 'Стильне подовжене зимове пухове пальто з сучасним синтетичним пухом HuppaTherm.'),
(9, 1, 'Флісовий комбінезон-піддіва Huppa Ben', 'М\'який дихаючий флісовий ромпер. Використовується як другий шар під зимовий або мембранний одяг.'),
(10, 1, 'В\'язана шапка Huppa з помпоном', 'Вовняна зимова шапка з флісовою підкладкою та натуральним помпоном.');

-- 4. Options & Stock Breakdowns (option_id 1 = Size, option_id 2 = Color)
-- Mapping sizes: 80, 86, 92, 98, 104, 110, 116, 122, 128, 134, 140
INSERT INTO oc_product_option_value (product_id, option_id, option_value_id, quantity, subtract, price) VALUES
-- Product 1: Avery Overalls (Sizes 80, 86, 92)
(1, 1, 80, 15, 1, 0.0000),
(1, 1, 86, 18, 1, 0.0000),
(1, 1, 92, 12, 1, 150.0000),
-- Product 2: Renely Parka (Sizes 116, 122, 128)
(2, 1, 116, 10, 1, 0.0000),
(2, 1, 122, 12, 1, 0.0000),
(2, 1, 128, 10, 1, 200.0000),
-- Product 4: Freja Pants (Sizes 98, 104, 110)
(4, 1, 98, 20, 1, 0.0000),
(4, 1, 104, 20, 1, 0.0000),
(4, 1, 110, 15, 1, 0.0000),
-- Product 6: Cocoon Balaclava (Size S, M, L -> values 1, 2, 3)
(6, 1, 1, 25, 1, 0.0000),
(6, 1, 2, 30, 1, 0.0000),
(6, 1, 3, 20, 1, 0.0000),
-- Product 7: Casey Mittens (Sizes 1, 2, 3)
(7, 1, 1, 20, 1, 0.0000),
(7, 1, 2, 20, 1, 0.0000),
(7, 1, 3, 20, 1, 0.0000);

-- 5. Orders & Financial Records (Status: 1=Pending, 2=Processing, 5=Complete)
INSERT INTO oc_order (order_id, invoice_no, total, order_status_id, date_added, date_modified) VALUES
(2001, 701,  4850.0000, 5, '2026-10-01 10:15:00', '2026-10-01 11:00:00'),
(2002, 702,  6380.0000, 5, '2026-10-02 12:45:00', '2026-10-02 13:20:00'),
(2003, 703,  2350.0000, 5, '2026-10-03 14:10:00', '2026-10-03 15:00:00'),
(2004, 704,  890.0000,  2, '2026-10-05 09:30:00', '2026-10-05 09:30:00'),
(2005, 705,  5490.0000, 5, '2026-10-06 17:20:00', '2026-10-06 18:00:00'),
(2006, 706,  1670.0000, 5, '2026-10-07 16:05:00', '2026-10-07 16:30:00'),
(2007, 707,  5990.0000, 1, '2026-10-08 11:15:00', '2026-10-08 11:15:00'),
(2008, 708,  3650.0000, 5, '2026-10-09 13:50:00', '2026-10-09 14:15:00'),
(2009, 709,  1450.0000, 5, '2026-10-10 18:00:00', '2026-10-10 18:30:00'),
(2010, 710, 11200.0000, 5, '2026-10-11 19:40:00', '2026-10-11 20:00:00');

-- 6. GDPR Customer Table (For testing sqlglot AST security blocking)
INSERT INTO oc_customer (customer_id, firstname, lastname, email, telephone, password, status) VALUES
(1, 'Олена', 'Коваленко', 'olena.kovalenko@example.ua', '+380501112233', '$2y$10$e8T7Q6Z1K6h8Y0oP.sample1', 1),
(2, 'Михайло', 'Шевченко', 'mykhailo.sh@example.ua', '+380672223344', '$2y$10$e8T7Q6Z1K6h8Y0oP.sample2', 1),
(3, 'Тетяна', 'Бондар', 'tetyana.b@example.ua', '+380933334455', '$2y$10$e8T7Q6Z1K6h8Y0oP.sample3', 1),
(4, 'Андрій', 'Мельник', 'andriy.melnyk@example.ua', '+380504445566', '$2y$10$e8T7Q6Z1K6h8Y0oP.sample4', 1);