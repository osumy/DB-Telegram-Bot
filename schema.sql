-- Schema for restaurant project database (PostgreSQL / Neon)
-- Creates all tables used by the backend, plus one initial admin user.

-- Drop existing tables (optional, uncomment if you need a clean reset)
-- DROP TABLE IF EXISTS courier_score CASCADE;
-- DROP TABLE IF EXISTS item_score CASCADE;
-- DROP TABLE IF EXISTS comments CASCADE;
-- DROP TABLE IF EXISTS order_items CASCADE;
-- DROP TABLE IF EXISTS orders CASCADE;
-- DROP TABLE IF EXISTS couriers CASCADE;
-- DROP TABLE IF EXISTS users CASCADE;
-- DROP TABLE IF EXISTS customer_address CASCADE;
-- DROP TABLE IF EXISTS customer_phones CASCADE;
-- DROP TABLE IF EXISTS customers CASCADE;
-- DROP TABLE IF EXISTS menu_items CASCADE;

-- Customers and related tables
CREATE TABLE IF NOT EXISTS customers (
    id          SERIAL PRIMARY KEY,
    first_name  VARCHAR(50),
    last_name   VARCHAR(50),
    score       DOUBLE PRECISION DEFAULT 0
);

CREATE TABLE IF NOT EXISTS customer_phones (
    id          SERIAL PRIMARY KEY,
    phone       VARCHAR(15) NOT NULL UNIQUE,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS customer_address (
    id          SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id) ON DELETE CASCADE,
    address     TEXT UNIQUE
);

-- Menu items
CREATE TABLE IF NOT EXISTS menu_items (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    price         NUMERIC(10, 2) NOT NULL,
    category      VARCHAR(50),
    is_available  BOOLEAN DEFAULT TRUE,
    image_url     TEXT,
    average_score DOUBLE PRECISION DEFAULT 0
);

-- Couriers
CREATE TABLE IF NOT EXISTS couriers (
    id            SERIAL PRIMARY KEY,
    first_name    VARCHAR(50),
    last_name     VARCHAR(50),
    phone         VARCHAR(15),
    address       TEXT,
    motor_info    TEXT,
    status        VARCHAR(30),
    average_score DOUBLE PRECISION DEFAULT 0
);

-- Orders and order items
CREATE TABLE IF NOT EXISTS orders (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    courier_id      INTEGER REFERENCES couriers(id) ON DELETE SET NULL,
    delivery_address TEXT,
    order_type      VARCHAR(20),
    status          VARCHAR(30),
    payment_method  VARCHAR(30),
    total_price     NUMERIC(10, 2),
    created_at      TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    delivered_at    TIMESTAMP WITHOUT TIME ZONE
);

CREATE TABLE IF NOT EXISTS order_items (
    id           SERIAL PRIMARY KEY,
    order_id     INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    menu_item_id INTEGER NOT NULL REFERENCES menu_items(id) ON DELETE RESTRICT,
    quantity     INTEGER NOT NULL,
    unit_price   NUMERIC(10, 2),
    total_price  NUMERIC(10, 2)
);

-- Comments and scores
CREATE TABLE IF NOT EXISTS comments (
    id           SERIAL PRIMARY KEY,
    order_id     INTEGER REFERENCES orders(id) ON DELETE CASCADE,
    menu_item_id INTEGER REFERENCES menu_items(id) ON DELETE CASCADE,
    customer_id  INTEGER REFERENCES customers(id) ON DELETE CASCADE,
    score        INTEGER,
    text         TEXT,
    created_at   TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS courier_score (
    id          SERIAL PRIMARY KEY,
    courier_id  INTEGER REFERENCES couriers(id) ON DELETE CASCADE,
    score       INTEGER,
    customer_id INTEGER UNIQUE REFERENCES customers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS item_score (
    id          SERIAL PRIMARY KEY,
    item_id     INTEGER REFERENCES menu_items(id) ON DELETE CASCADE,
    score       INTEGER,
    customer_id INTEGER UNIQUE REFERENCES customers(id) ON DELETE CASCADE
);

-- Users (OTP-based auth, roles)
CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    role        VARCHAR(20) NOT NULL DEFAULT 'customer',
    customer_id INTEGER NOT NULL UNIQUE REFERENCES customers(id) ON DELETE CASCADE,
    otp_code    VARCHAR(6),
    otp_expire  TIMESTAMP WITHOUT TIME ZONE
);

-- Initial admin user

WITH new_customer AS (
    INSERT INTO customers (first_name, last_name, score)
    VALUES ('AmirAli', 'Araghi', 0)
    RETURNING id
),
new_phone AS (
    INSERT INTO customer_phones (phone, customer_id)
    SELECT '09919529364', id FROM new_customer
)
INSERT INTO users (role, customer_id)
SELECT 'admin', id FROM new_customer;

