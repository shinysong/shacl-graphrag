"""Generate only authored source databases; no scoring, model calls or approval.

Usage: uv run --locked python examples/factory_lab/extensions/domain-packs/generate.py --output _workspace/public-domain-packs
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import shutil
import sqlite3

ROOT = Path(__file__).resolve().parent
SNAP = "2026-11-19"

def table(c, name, columns, rows):
    c.execute(f'CREATE TABLE {name} ({columns})')
    rows = list(rows)
    placeholders = ','.join('?' for _ in rows[0])
    c.executemany(f'INSERT INTO {name} VALUES ({placeholders})', rows)

def ref(name):
    return f'INTEGER REFERENCES {name}(id)'

def manufacture(c):
    table(c, 'suppliers', 'id INTEGER PRIMARY KEY, name TEXT, qualified_until TEXT', ((i, f'Supplier {i}', '2026-12-31' if i % 3 else '2026-10-31') for i in range(10)))
    table(c, 'parts', f'id INTEGER PRIMARY KEY, supplier_id {ref("suppliers")}, revision TEXT', ((i, i % 10, 'B' if i % 2 else 'A') for i in range(40)))
    table(c, 'products', 'id INTEGER PRIMARY KEY, name TEXT, release_state TEXT', ((i, f'Assembly {i}', 'released' if i % 3 else 'prototype') for i in range(20)))
    table(c, 'bom', f'id INTEGER PRIMARY KEY, product_id {ref("products")}, part_id {ref("parts")}, quantity INTEGER, valid_from TEXT, valid_to TEXT', ((i, i // 4, (i // 4 * 3 + i % 4) % 40, 1 + i % 4, '2026-01-01', '2026-12-31') for i in range(80)))
    table(c, 'inspections', f'id INTEGER PRIMARY KEY, part_id {ref("parts")}, inspected_at TEXT, outcome TEXT', ((i, i % 40, f'2026-11-{1 + i // 40:02d}', 'fail' if i % 7 == 0 else 'pass') for i in range(120)))
    table(c, 'waivers', f'id INTEGER PRIMARY KEY, part_id {ref("parts")}, scope TEXT, expires_at TEXT, approved INTEGER', ((i, i * 4, 'cosmetic-only', '2026-12-01' if i % 2 else '2026-10-01', i % 2) for i in range(10)))

def orgsmall(c):
    table(c, 'teams', 'id INTEGER PRIMARY KEY, name TEXT', ((i, f'Team {i}') for i in range(10)))
    table(c, 'employees', f'id INTEGER PRIMARY KEY, team_id {ref("teams")}, name TEXT, active INTEGER', ((i, i % 10, f'Employee {i}', int(i % 11 != 0)) for i in range(60)))
    table(c, 'projects', f'id INTEGER PRIMARY KEY, owner_team_id {ref("teams")}, name TEXT, deadline TEXT', ((i, i % 10, f'Project {i}', '2026-12-31') for i in range(20)))
    table(c, 'assignments', f'id INTEGER PRIMARY KEY, employee_id {ref("employees")}, project_id {ref("projects")}, valid_from TEXT, valid_to TEXT, role TEXT', ((i, i % 60, (i // 60 * 7 + i) % 20, '2026-01-01', '2026-12-31' if i % 5 else '2026-10-31', 'reviewer' if i % 2 else 'contributor') for i in range(120)))
    table(c, 'approvals', f'id INTEGER PRIMARY KEY, project_id {ref("projects")}, approver_id {ref("employees")}, decided_at TEXT, decision TEXT', ((i, i % 20, i * 7 % 60, f'2026-11-{1 + i // 20:02d}', 'rejected' if i % 7 == 0 else 'approved') for i in range(60)))
    table(c, 'exceptions', f'id INTEGER PRIMARY KEY, project_id {ref("projects")}, reason TEXT, expires_at TEXT', ((i, i * 2, 'owner-review-required', '2026-12-01' if i % 2 else '2026-10-01') for i in range(10)))

def commerce(c):
    table(c, 'categories', 'id INTEGER PRIMARY KEY, name TEXT', ((i, f'Category {i}') for i in range(10)))
    table(c, 'suppliers', 'id INTEGER PRIMARY KEY, name TEXT, suspended INTEGER', ((i, f'Supplier {i}', int(i % 9 == 0)) for i in range(40)))
    table(c, 'products', f'id INTEGER PRIMARY KEY, category_id {ref("categories")}, supplier_id {ref("suppliers")}, price_cents INTEGER', ((i, i % 10, i % 40, 1000 + i * 7) for i in range(400)))
    table(c, 'warehouses', 'id INTEGER PRIMARY KEY, region TEXT', ((i, f'Region {i % 3}') for i in range(10)))
    table(c, 'inventory', f'id INTEGER PRIMARY KEY, product_id {ref("products")}, warehouse_id {ref("warehouses")}, available INTEGER, observed_at TEXT', ((i, i % 400, i // 400, i % 31, SNAP) for i in range(4000)))
    table(c, 'customers', 'id INTEGER PRIMARY KEY, region TEXT, tier TEXT', ((i, f'Region {i % 3}', 'business' if i % 4 == 0 else 'retail') for i in range(1000)))
    table(c, 'orders', f'id INTEGER PRIMARY KEY, customer_id {ref("customers")}, placed_at TEXT, status TEXT', ((i, i % 1000, '2026-11-01', 'cancelled' if i % 10 == 0 else 'confirmed') for i in range(2000)))
    table(c, 'order_items', f'id INTEGER PRIMARY KEY, order_id {ref("orders")}, product_id {ref("products")}, quantity INTEGER, unit_price_cents INTEGER', ((i, i // 3, i * 7 % 400, 1 + i % 4, 1000 + i * 7 % 400 * 7) for i in range(6000)))
    table(c, 'shipments', f'id INTEGER PRIMARY KEY, order_id {ref("orders")}, warehouse_id {ref("warehouses")}, shipped_at TEXT, state TEXT', ((i, i, i % 10, '2026-11-05', 'held' if i % 13 == 0 else 'shipped') for i in range(1600)))
    table(c, 'returns', f'id INTEGER PRIMARY KEY, order_item_id {ref("order_items")}, requested_at TEXT, reason TEXT, status TEXT', ((i, i * 17, '2026-11-15', 'damaged' if i % 2 else 'unwanted', 'approved' if i % 3 else 'pending') for i in range(200)))
    table(c, 'promotions', 'id INTEGER PRIMARY KEY, starts_at TEXT, ends_at TEXT, required_tier TEXT, discount_percent INTEGER', ((i, '2026-11-01', '2026-12-01' if i % 2 else '2026-11-10', 'business' if i % 3 else 'retail', 5 + i % 4 * 5) for i in range(20)))
    table(c, 'promotion_products', f'id INTEGER PRIMARY KEY, promotion_id {ref("promotions")}, product_id {ref("products")}', ((i, i % 20, i) for i in range(400)))

def orgmedium(c):
    table(c, 'teams', 'id INTEGER PRIMARY KEY, name TEXT', ((i, f'Team {i}') for i in range(30)))
    table(c, 'employees', f'id INTEGER PRIMARY KEY, team_id {ref("teams")}, active INTEGER', ((i, i % 30, int(i % 17 != 0)) for i in range(1000)))
    table(c, 'roles', 'id INTEGER PRIMARY KEY, name TEXT, can_approve INTEGER', ((i, f'Role {i}', int(i < 5)) for i in range(20)))
    table(c, 'role_grants', f'id INTEGER PRIMARY KEY, employee_id {ref("employees")}, role_id {ref("roles")}, valid_from TEXT, valid_to TEXT', ((i, i % 1000, (i // 1000 * 7 + i) % 20, '2026-01-01', '2026-12-31' if i % 7 else '2026-10-01') for i in range(2000)))
    table(c, 'projects', f'id INTEGER PRIMARY KEY, owner_team_id {ref("teams")}, deadline TEXT', ((i, i % 30, '2026-12-31') for i in range(200)))
    table(c, 'assignments', f'id INTEGER PRIMARY KEY, employee_id {ref("employees")}, project_id {ref("projects")}, allocation_percent INTEGER', ((i, i % 1000, (i // 1000 * 31 + i) % 200, 10 + i % 4 * 10) for i in range(3000)))
    table(c, 'milestones', f'id INTEGER PRIMARY KEY, project_id {ref("projects")}, due_at TEXT, state TEXT', ((i, i // 5, '2026-12-15', 'complete' if i % 3 == 0 else 'pending') for i in range(1000)))
    table(c, 'dependencies', f'id INTEGER PRIMARY KEY, predecessor_id {ref("milestones")}, successor_id {ref("milestones")}, relation TEXT', ((i, i // 4 * 5 + i % 4, i // 4 * 5 + i % 4 + 1, 'finish-to-start') for i in range(800)))
    table(c, 'approval_requests', f'id INTEGER PRIMARY KEY, project_id {ref("projects")}, requester_id {ref("employees")}, requested_at TEXT, status TEXT', ((i, i % 200, i % 1000, '2026-11-10', 'open' if i % 3 else 'closed') for i in range(2000)))
    table(c, 'approval_events', f'id INTEGER PRIMARY KEY, request_id {ref("approval_requests")}, actor_id {ref("employees")}, decided_at TEXT, decision TEXT', ((i, i % 2000, (i * 3 + 1) % 1000, f'2026-11-{11 + i // 2000:02d}', 'approved' if i % 4 else 'rejected') for i in range(3000)))
    table(c, 'exceptions', f'id INTEGER PRIMARY KEY, project_id {ref("projects")}, scope TEXT, expires_at TEXT, status TEXT', ((i, i, 'manual-signoff', '2026-12-31' if i % 2 else '2026-10-01', 'open' if i % 3 else 'closed') for i in range(200)))
    table(c, 'audit_events', f'id INTEGER PRIMARY KEY, request_id {ref("approval_requests")}, recorded_at TEXT, event_type TEXT', ((i, i % 2000, f'2026-11-{10 + i // 2000:02d}', 'created' if i < 2000 else 'reviewed') for i in range(4000)))

BUILDERS = {"manufacturing-small": manufacture, "organization-small": orgsmall,
            "commerce-medium": commerce, "organization-medium": orgmedium}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True,
                        help="New output directory (existing paths are refused)")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    protocol = json.loads((ROOT / "protocol.json").read_text())
    expected = json.loads((ROOT / "source-hashes.json").read_text())
    manifests = {}
    for name, spec in protocol["packs"].items():
        pack = output / name
        pack.mkdir()
        for filename in ("domain-config.json", "runtime-questions.json", "schema.sql", "query-config.json"):
            shutil.copyfile(ROOT / name / filename, pack / filename)
        shutil.copytree(ROOT / name / "documents", pack / "documents")
        db = pack / "source.sqlite"
        if name == "commerce-small":
            shutil.copyfile(ROOT / name / "source.seed.sqlite", db)
        with sqlite3.connect(db) as conn:
            if name in BUILDERS:
                conn.execute("PRAGMA foreign_keys=ON")
                BUILDERS[name](conn)
                conn.commit()
            counts = {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                      for t in spec["tables"]}
            if counts != spec["tables"]:
                raise ValueError(f"Unexpected row counts: {name}")
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError(f"Integrity failure: {name}")
            if conn.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError(f"Foreign key failure: {name}")
            actual_schema = "\n\n".join(r[0]+";" for r in conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name"))+"\n"
            if actual_schema != (pack / "schema.sql").read_text():
                raise ValueError(f"Schema mismatch: {name}")
        docs = sorted((pack / "documents").glob("*.txt"))
        characters = sum(len(p.read_text()) for p in docs)
        hashes = {str(p.relative_to(pack)): sha(p) for p in sorted(pack.rglob("*")) if p.is_file()}
        identity = {k: hashes.get(k) == v for k, v in expected[name].items()}
        manifests[name] = {
            "row_counts": counts, "total_rows": sum(counts.values()),
            "table_count": len(counts), "documents": len(docs),
            "document_characters": characters,
            "estimated_document_tokens": math.ceil(characters / 4),
            "estimated_document_pages": math.ceil(characters / 3000),
            "sqlite_version": sqlite3.sqlite_version,
            "hashes": hashes, "original_source_hash_matches": identity,
            "checks": {"integrity": "ok", "foreign_key_violations": 0},
            "scope": "Source generation only; no runtime answers, model calls or approvals",
        }
    (output / "manifest.json").write_text(json.dumps(manifests, indent=2)+"\n")
    print(json.dumps({"output": str(output), "packs": len(manifests),
                      "original_hashes_all_match": all(all(m["original_source_hash_matches"].values()) for m in manifests.values())}))


if __name__ == "__main__":
    main()
