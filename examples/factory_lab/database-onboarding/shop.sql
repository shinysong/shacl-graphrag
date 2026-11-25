-- Authored synthetic SQLite example. CC0-1.0. No customer personal data.
PRAGMA foreign_keys=ON;
CREATE TABLE products (
  sku TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  available INTEGER NOT NULL CHECK (available >= 0)
);
CREATE TABLE orders (
  order_no TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  requested_date TEXT
);
CREATE TABLE order_items (
  line_no TEXT PRIMARY KEY,
  order_no TEXT NOT NULL REFERENCES orders(order_no),
  sku TEXT NOT NULL REFERENCES products(sku),
  quantity INTEGER NOT NULL CHECK (quantity > 0)
);
INSERT INTO products VALUES
 ('P-101','면 티셔츠',12),('P-102','머그컵',0),('P-103','캔버스 가방',7),
 ('P-104','노트',21),('P-105','볼펜',34),('P-106','텀블러',5);
INSERT INTO orders VALUES ('ORD-1001','접수','2026-11-26'),('ORD-1002','출고','2026-11-25');
INSERT INTO order_items VALUES ('L-01','ORD-1001','P-101',2),('L-02','ORD-1001','P-102',1),('L-03','ORD-1002','P-106',1);
