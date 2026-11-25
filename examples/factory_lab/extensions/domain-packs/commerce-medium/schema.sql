CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT);

CREATE TABLE customers (id INTEGER PRIMARY KEY, region TEXT, tier TEXT);

CREATE TABLE inventory (id INTEGER PRIMARY KEY, product_id INTEGER REFERENCES products(id), warehouse_id INTEGER REFERENCES warehouses(id), available INTEGER, observed_at TEXT);

CREATE TABLE order_items (id INTEGER PRIMARY KEY, order_id INTEGER REFERENCES orders(id), product_id INTEGER REFERENCES products(id), quantity INTEGER, unit_price_cents INTEGER);

CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id), placed_at TEXT, status TEXT);

CREATE TABLE products (id INTEGER PRIMARY KEY, category_id INTEGER REFERENCES categories(id), supplier_id INTEGER REFERENCES suppliers(id), price_cents INTEGER);

CREATE TABLE promotion_products (id INTEGER PRIMARY KEY, promotion_id INTEGER REFERENCES promotions(id), product_id INTEGER REFERENCES products(id));

CREATE TABLE promotions (id INTEGER PRIMARY KEY, starts_at TEXT, ends_at TEXT, required_tier TEXT, discount_percent INTEGER);

CREATE TABLE returns (id INTEGER PRIMARY KEY, order_item_id INTEGER REFERENCES order_items(id), requested_at TEXT, reason TEXT, status TEXT);

CREATE TABLE shipments (id INTEGER PRIMARY KEY, order_id INTEGER REFERENCES orders(id), warehouse_id INTEGER REFERENCES warehouses(id), shipped_at TEXT, state TEXT);

CREATE TABLE suppliers (id INTEGER PRIMARY KEY, name TEXT, suspended INTEGER);

CREATE TABLE warehouses (id INTEGER PRIMARY KEY, region TEXT);
