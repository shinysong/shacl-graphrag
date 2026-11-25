CREATE TABLE bom (id INTEGER PRIMARY KEY, product_id INTEGER REFERENCES products(id), part_id INTEGER REFERENCES parts(id), quantity INTEGER, valid_from TEXT, valid_to TEXT);

CREATE TABLE inspections (id INTEGER PRIMARY KEY, part_id INTEGER REFERENCES parts(id), inspected_at TEXT, outcome TEXT);

CREATE TABLE parts (id INTEGER PRIMARY KEY, supplier_id INTEGER REFERENCES suppliers(id), revision TEXT);

CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, release_state TEXT);

CREATE TABLE suppliers (id INTEGER PRIMARY KEY, name TEXT, qualified_until TEXT);

CREATE TABLE waivers (id INTEGER PRIMARY KEY, part_id INTEGER REFERENCES parts(id), scope TEXT, expires_at TEXT, approved INTEGER);
