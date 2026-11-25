"""Create an authored SQLite + policy example, without network or model calls.

Run with uv run --locked python <this-file> --output <new-directory>.
The directory must not exist. These records are synthetic, not customer data.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3


def create(output: Path):
    output.mkdir(parents=True, exist_ok=False)
    database = output / 'commerce.sqlite'
    with sqlite3.connect(database) as con:
        con.execute('PRAGMA foreign_keys=ON')
        con.executescript('''
            CREATE TABLE products (product_id TEXT PRIMARY KEY, label TEXT NOT NULL);
            CREATE TABLE orders (order_id TEXT PRIMARY KEY, status TEXT NOT NULL);
            CREATE TABLE order_items (
                item_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL REFERENCES orders(order_id),
                product_id TEXT NOT NULL REFERENCES products(product_id),
                quantity INTEGER CHECK(quantity > 0),
                unit_price_cents INTEGER CHECK(unit_price_cents >= 0)
            );
        ''')
        con.executemany('INSERT INTO products VALUES (?,?)',
                        [(f'P{i:03}', f'Example product {i}') for i in range(20)])
        con.executemany('INSERT INTO orders VALUES (?,?)',
                        [(f'O{i:03}', ('delivered', 'processing', 'cancelled')[i % 3])
                         for i in range(40)])
        con.executemany('INSERT INTO order_items VALUES (?,?,?,?,?)',
                        [(f'I{i:03}', f'O{i // 3:03}', f'P{i % 20:03}',
                          1 + i % 4, 500 + (i % 20) * 125) for i in range(120)])
    (output / 'returns.txt').write_text(
        'Authored example policy, version 1. Returns require delivered status, '
        'a request within 30 days of delivery, and unused condition. '
        'This database does not record delivery dates or item condition; '
        'status alone cannot establish return eligibility.\n', encoding='utf-8')
    (output / 'quantities.txt').write_text(
        'Authored reporting note, version 1. Quantity is recorded per order item; '
        'prices use integer cents. Sum item quantities by order when reporting '
        'recorded quantities. Cancelled orders remain in the source.\n', encoding='utf-8')
    paths = [database, output / 'returns.txt', output / 'quantities.txt']
    manifest = {
        'origin': 'authored synthetic example', 'license': 'Apache-2.0',
        'tables': {'products': 20, 'orders': 40, 'order_items': 120},
        'documents': 2, 'document_format': 'UTF-8 plain text',
        'files': {p.name: {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                           'bytes': p.stat().st_size} for p in paths},
        'runtime_questions': [
            'List recorded delivered orders with their item quantities.',
            'Sum recorded item quantities per delivered order.',
            'Can these delivered items be returned under the supplied policy? '
            'Identify evidence that is unavailable.',
        ],
        'limits': ['No observed customers or business outcomes.',
                   'No policy eligibility inferred from status alone.',
                   'Generated files are inputs, not approved mappings or answers.'],
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(create(args.output), indent=2))
