#!/usr/bin/env python3
"""Source-backed illustrative replay; not independent accuracy evaluation."""

import argparse
import csv
import hashlib
import io
import itertools
import json
from pathlib import Path
import shutil
import time
import zipfile

import run_business_questions_study as study

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/gleif/20261012T080000"
ROLES = {
    "IS_DIRECTLY_CONSOLIDATED_BY": "DIRECT_ACCOUNTING",
    "IS_ULTIMATELY_CONSOLIDATED_BY": "ULTIMATE_ACCOUNTING",
    "IS_FUND-MANAGED_BY": "FUND_MANAGER",
}


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def rows(path):
    with zipfile.ZipFile(path) as z:
        members = [n for n in z.namelist() if n.endswith(".csv")]
        assert len(members) == 1
        with io.TextIOWrapper(z.open(members[0]), encoding="utf-8-sig") as f:
            yield from csv.DictReader(f)


def convert_rr(raw, ident):
    """Keep period kinds separate; each relationship period becomes its own record."""
    if any(
        raw.get(f"Relationship.{node}Node.NodeIDType") != "LEI"
        for node in ("Start", "End")
    ):
        raise ValueError("Only LEI node identifiers supported")
    periods = [
        i
        for i in range(1, 6)
        if raw.get(f"Relationship.Period.{i}.periodType") == "RELATIONSHIP_PERIOD"
    ]
    result = []
    for i in periods or [None]:
        start = raw.get(f"Relationship.Period.{i}.startDate", "")[:10] if i else ""
        end = raw.get(f"Relationship.Period.{i}.endDate", "")[:10] if i else ""
        result.append(
            dict(
                id=f"{ident}-period-{i}",
                kind="relationship",
                subject=raw["Relationship.StartNode.NodeID"],
                object=raw["Relationship.EndNode.NodeID"],
                relation=ROLES.get(
                    raw["Relationship.RelationshipType"],
                    raw["Relationship.RelationshipType"],
                ),
                status=raw["Relationship.RelationshipStatus"],
                registration_status=raw["Registration.RegistrationStatus"],
                start=start or "9999-12-31",
                end=end or "9999-12-31",
                snapshot_date=study.ASOF,
            )
        )
    return result


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "protocol": "business-questions-gleif-1",
        "status": "running",
        "scope": "Purposeful source-backed illustrations; no independent gold, accuracy or current-world truth claim.",
        "paid_api_calls": 0,
        "source_hashes": {},
        "archive_rows_scanned": {},
    }
    save = lambda name, value: (output / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    )
    start_time = time.monotonic()
    try:
        release = json.loads((SOURCE / "manifest.json").read_text())
        manifest["source_release"] = release
        for name in ("lei2", "rr", "repex"):
            file = SOURCE / (name + ".csv.zip")
            h = sha(file)
            assert h == release["files"][name]["sha256"], name
            manifest["source_hashes"][file.name] = h
        (output / "source").mkdir()
        for name in (
            "run_business_questions_study.py",
            "run_business_questions_gleif.py",
        ):
            p = ROOT / "scripts" / name
            shutil.copyfile(p, output / "source" / name)
            manifest["source_hashes"][name] = sha(p)
        prefix = list(itertools.islice(rows(SOURCE / "rr.csv.zip"), 256))
        direct = next(
            r["Relationship.StartNode.NodeID"]
            for r in prefix
            if r["Relationship.RelationshipType"] == "IS_DIRECTLY_CONSOLIDATED_BY"
        )
        fund = next(
            r["Relationship.StartNode.NodeID"]
            for r in prefix
            if r["Relationship.RelationshipType"] == "IS_FUND-MANAGED_BY"
        )
        ultimate = list(
            dict.fromkeys(
                r["Relationship.StartNode.NodeID"]
                for r in prefix
                if r["Relationship.RelationshipType"] == "IS_ULTIMATELY_CONSOLIDATED_BY"
            )
        )[:2]
        assert len(ultimate) == 2
        selected = set([direct, fund] + ultimate)
        manifest["selection"] = {
            "prefix_rows": 256,
            "direct_example": direct,
            "fund_example": fund,
            "ultimate_pair": ultimate,
            "selected_entities": sorted(selected),
            "rule": "First direct/fund subjects and first two ultimate subjects in RR archive prefix; consumed convenience sample, not held out.",
        }
        records, retained = [], {"rr": [], "repex": [], "lei2": []}
        for kind, key in (
            ("rr", "Relationship.StartNode.NodeID"),
            ("repex", "LEI"),
            ("lei2", "LEI"),
        ):
            seen = set()
            for count, r in enumerate(rows(SOURCE / (kind + ".csv.zip")), 1):
                if time.monotonic() - start_time > 300:
                    raise TimeoutError("300-second limit")
                if r[key] not in selected:
                    continue
                retained[kind].append({"archive_row": count, "record": r})
                if kind == "rr":
                    records.extend(convert_rr(r, f"rr-{count}"))
                elif kind == "repex":
                    role = {
                        "DIRECT_ACCOUNTING_CONSOLIDATION_PARENT": "DIRECT_ACCOUNTING",
                        "ULTIMATE_ACCOUNTING_CONSOLIDATION_PARENT": "ULTIMATE_ACCOUNTING",
                    }.get(r["Exception.Category"], r["Exception.Category"])
                    records.append(
                        dict(
                            id=f"repex-{count}",
                            kind="exception",
                            subject=r["LEI"],
                            relation=role,
                            reason="|".join(
                                r[k]
                                for k in r
                                if k.startswith("Exception.Reason.") and r[k]
                            ),
                            status="ACTIVE",
                            start=study.ASOF,
                            end=study.ASOF,
                            snapshot_date=study.ASOF,
                        )
                    )
                else:
                    records.append(
                        dict(
                            id=f"lei-{count}",
                            kind="entity",
                            entity=r["LEI"],
                            legal_status=r["Entity.EntityStatus"],
                            registration_status=r["Registration.RegistrationStatus"],
                            snapshot_date=study.ASOF,
                        )
                    )
                    seen.add(r["LEI"])
                    if seen == selected:
                        break
            manifest["archive_rows_scanned"][kind] = count
        manifest["coverage"] = {
            "rr": "Full archive scan for selected subjects",
            "repex": "Full archive scan for selected subjects",
            "lei2": "Stop after first matching row per selected LEI; no whole-release duplicate audit",
            "exception_dates": "Adapter-local snapshot-day scope, not asserted source relationship periods",
            "open_end": "Blank relationship end represented by9999-12-31; missing start forced noncurrent; day-inclusive internal convention",
        }
        save("selected-source-records.json", retained)
        requests = [
            ("F1", {"entity": direct}),
            ("F1", {"entity": fund}),
            ("F2", {"entities": ultimate}),
            ("F3", {"entity": fund}),
        ]
        outputs = []
        for task, policy in requests:
            packet = dict(
                task=task,
                question={
                    "F1": "Reported direct accounting parent",
                    "F2": "Same reported ultimate accounting parent",
                    "F3": "Internal relationship review readiness",
                }[task],
                asof=study.ASOF,
                observed_records=records,
                published_schema={},
                internal_policy=policy,
            )
            # No scoring/gold: expose each actual arm output unchanged.
            outputs.append(
                {
                    "task": task,
                    "policy": policy,
                    "packet": packet,
                    "outputs": {
                        arm: (
                            study.raw_lookup(packet)
                            if arm == "raw_lookup"
                            else study.decide(
                                packet,
                                study.select_json(packet)
                                if arm == "typed_json"
                                else study.select_rdf(packet),
                            )
                        )
                        for arm in study.ARMS
                    },
                }
            )
        save("examples.json", outputs)
        manifest["examples"] = len(outputs)
        manifest["status"] = "complete"
    except BaseException as exc:
        manifest["status"] = "partial_failed"
        manifest["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        manifest["elapsed_seconds"] = time.monotonic() - start_time
        save("manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output)))
