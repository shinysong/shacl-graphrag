CREATE TABLE order_items(line_id TEXT PRIMARY KEY, order_id TEXT REFERENCES orders(order_id), sku TEXT REFERENCES products(sku), quantity INTEGER);

CREATE TABLE orders(order_id TEXT PRIMARY KEY, placed_at TEXT, status TEXT);

CREATE TABLE products(sku TEXT PRIMARY KEY, label TEXT NOT NULL, category TEXT);
