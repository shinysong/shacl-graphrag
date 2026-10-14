#!/usr/bin/env python3
"""Independent artifact/score audit against declared fixtures, not independent gold."""

import argparse
import collections
import hashlib
import json
from pathlib import Path


def analyze(root):
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["status"] == "completed"
    for name, digest in manifest["sha256"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name
    cases = {c["case_id"]: c for c in json.loads((root / "cases.json").read_text())}
    packets = json.loads((root / "runtime_packets.json").read_text())
    assert len(cases) == 36 and len(packets) == 36
    for p in packets:
        assert p["packet"] == cases[p["case_id"]]["packet"]
        assert not {"expected", "scenario", "gold"} & p["packet"].keys()
    rows = [json.loads(s) for s in (root / "rows.jsonl").read_text().splitlines()]
    arms = ("raw_lookup", "typed_json", "typed_rdf")
    assert len(rows) == 108
    assert len({(r["case_id"], r["arm"]) for r in rows}) == 108
    assert {(r["case_id"], r["arm"]) for r in rows} == {
        (c, a) for c in cases for a in arms
    }
    counts = collections.defaultdict(collections.Counter)
    indexed = {}
    for r in rows:
        assert "error" not in r, r
        c = cases[r["case_id"]]
        a = r["answer"]
        e = c["expected"]
        assert r["task"] == c["packet"]["task"]
        decision = (a["status"], a["value"]) == (e["status"], e["value"])
        evidence = a["evidence_ids"] == e["evidence_ids"]
        assert decision == r["decision_correct"] and evidence == r["evidence_correct"]
        assert set(a["evidence_ids"]) <= {
            x["id"] for x in c["packet"]["observed_records"]
        }
        counter = counts[(r["task"], r["arm"])]
        counter.update(
            total=1, decision_correct=int(decision), evidence_correct=int(evidence)
        )
        indexed[(r["case_id"], r["arm"])] = a
    parity = sum(indexed[(c, "typed_json")] == indexed[(c, "typed_rdf")] for c in cases)
    return {
        "scope": "Declared synthetic fixtures; not independent factual gold",
        "cases": len(cases),
        "rows": len(rows),
        "json_rdf_exact_parity": parity,
        "groups": [dict(task=t, arm=a, **v) for (t, a), v in sorted(counts.items())],
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("run")
    a = p.parse_args()
    print(json.dumps(analyze(a.run), ensure_ascii=False, indent=2))
