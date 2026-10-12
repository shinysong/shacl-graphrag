"""Run E0 and retain every result; publish only explicitly selected metadata."""

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from importlib.metadata import distributions
from pathlib import Path

from pyshacl import validate
from rdflib import Graph, RDF, SH

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "experiments/e0"
PREFIXES = (
    "@prefix ex: <https://example.org/lab/> .\n"
    "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
)
INPUTS = [
    "scripts/run_validation_experiment.py",
    "experiments/e0/data.ttl",
    "experiments/e0/shapes.ttl",
    "experiments/e0/cases.json",
    "docs/experiments/specification.md",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
]


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def score(rows):
    counts = dict(tp=0, tn=0, fp=0, fn=0, errors=0, exact=0)
    for row in rows:
        if row["status"] == "error":
            counts["errors"] += 1
            continue
        positive = bool(row["expected"])
        detected = not row["conforms"]
        counts["tp" if positive and detected else "fn" if positive else
               "fp" if detected else "tn"] += 1
        counts["exact"] += int(row["matches_expected"])
    counts["total"] = len(rows)
    counts["recall"] = ratio(counts["tp"], counts["tp"] + counts["fn"])
    counts["false_positive_rate"] = ratio(counts["fp"], counts["fp"] + counts["tn"])
    counts["error_rate"] = ratio(counts["errors"], len(rows))
    return counts


def run_case(case, directory):
    row = {"id": case["id"], "expected": sorted(case["expected"])}
    try:
        graph = Graph().parse(FIXTURES / "data.ttl", format="turtle")
        for triple in Graph().parse(data=PREFIXES + case["remove"], format="turtle"):
            if triple not in graph:
                raise ValueError("Mutation removes a triple absent from the base graph")
            graph.remove(triple)
        for triple in Graph().parse(data=PREFIXES + case["add"], format="turtle"):
            graph.add(triple)
        graph.serialize(directory / f"{case['id']}.ttl", format="turtle")
        shapes = Graph().parse(FIXTURES / "shapes.ttl", format="turtle")
        started = time.perf_counter()
        conforms, report, _ = validate(
            graph, shacl_graph=shapes, inference="none", abort_on_first=False,
            allow_infos=False, allow_warnings=False, advanced=False, js=False,
        )
        elapsed = (time.perf_counter() - started) * 1000
        if not isinstance(report, Graph):
            raise RuntimeError("Validator returned a failure instead of a report graph")
        report.serialize(directory / f"{case['id']}-report.ttl", format="turtle")
        actual = sorted({
            tuple(str(report.value(result, predicate)) for predicate in
                  (SH.focusNode, SH.resultPath, SH.sourceConstraintComponent))
            for result in report.subjects(RDF.type, SH.ValidationResult)
        })
        expected = sorted(tuple(item) for item in case["expected"])
        row.update(
            status="completed", conforms=bool(conforms), actual=actual,
            validation_ms=round(elapsed, 3),
            matches_expected=actual == expected and bool(conforms) == (not expected),
        )
    except Exception as exc:
        # Detailed exception remains local; public metadata contains only the type.
        (directory / f"{case['id']}-error.txt").write_text(str(exc), encoding="utf-8")
        row.update(status="error", error_type=type(exc).__name__, matches_expected=False)
    return row


def markdown(record, public=True):
    metrics = record["metrics"]
    lines = [
        f"# {record['run_id']}", "", "사전 점검 · 합성 RDF 검증 실행 기록. GraphRAG 성능 비교 결과가 아니다.", "",
        f"- 상태: {record['status']}",
        f"- 시작 시각 UTC: {record['started_at']}",
        f"- Git commit: `{record['git_commit']}`",
        f"- 미커밋 변경 포함: {record['working_tree_dirty']}",
        f"- 기대값 정확 일치: {metrics['exact']}/{metrics['total']}",
        f"- TP / TN / FP / FN / 오류: {metrics['tp']} / {metrics['tn']} / "
        f"{metrics['fp']} / {metrics['fn']} / {metrics['errors']}",
        "", "| 사례 | 판정 | 기대값 일치 | 검증 시간 ms |",
        "| --- | --- | --- | --- |",
    ]
    for row in record["cases"]:
        decision = "오류" if row["status"] == "error" else "통과" if row["conforms"] else "위반"
        lines.append(f"| {row['id']} | {decision} | {row['matches_expected']} | "
                     f"{row.get('validation_ms', '미측정')} |")
    details = f"{record['run_id']}.json" if public else "record.json"
    index = " · [실행 목록](index.md)" if public else ""
    lines += [
        "", "시간은 단일 실행 참고값이며 입력 파싱과 보고서 저장 시간은 제외한다.", "",
        f"[JSON 환경 정보와 상세 판정]({details}){index}", "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-only", action="store_true", help="Write only to ignored runs/")
    args = parser.parse_args()
    started = datetime.now(timezone.utc)
    run_id = started.strftime("%Y%m%dT%H%M%S%fZ") + "-e0-" + uuid.uuid4().hex[:8]
    output = ROOT / "runs" / run_id
    output.mkdir(parents=True, exist_ok=False)
    record = {
        "schema_version": 1, "experiment": "E0", "run_id": run_id,
        "started_at": started.isoformat(), "status": "running",
        "command": "uv run --locked python scripts/run_validation_experiment.py"
        + (" --local-only" if args.local_only else ""),
        "git_commit": git("rev-parse", "HEAD"),
        "working_tree_dirty": bool(git("status", "--porcelain")),
        "python": platform.python_version(), "os": platform.system(),
        "architecture": platform.machine(),
        "packages": dict(sorted((d.metadata["Name"], d.version) for d in distributions())),
        "settings": {
            "inference": "none", "abort_on_first": False, "llm_calls": 0,
            "allow_infos": False, "allow_warnings": False, "advanced": False, "js": False,
        },
        "sha256": {},
    }
    manifest = output / "record.json"
    manifest.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for relative in INPUTS:
        source = ROOT / relative
        record["sha256"][relative] = hashlib.sha256(source.read_bytes()).hexdigest()
        target = output / "inputs" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    cases = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))
    ids = [case["id"] for case in cases]
    if not cases or len(ids) != len(set(ids)) or any(not re.fullmatch(r"[a-z_]+", i) for i in ids):
        raise ValueError("Case IDs must be unique, nonempty lowercase identifiers")
    record["cases"] = [run_case(case, output) for case in cases]
    record["metrics"] = score(record["cases"])
    passed = all(row["matches_expected"] for row in record["cases"])
    record["status"] = "passed" if passed else "failed"
    record["finished_at"] = datetime.now(timezone.utc).isoformat()
    serialized = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    manifest.write_text(serialized, encoding="utf-8")
    (output / "summary.md").write_text(markdown(record, public=False), encoding="utf-8")
    if not args.local_only:
        public = ROOT / "docs/experiments/records"
        public.mkdir(parents=True, exist_ok=True)
        (public / f"{run_id}.json").write_text(serialized, encoding="utf-8")
        (public / f"{run_id}.md").write_text(markdown(record), encoding="utf-8")
        index = public / "index.md"
        index.write_text(index.read_text(encoding="utf-8").replace(
            "<!-- RUNS -->", f"<!-- RUNS -->\n\n- [{run_id}]({run_id}.md) — {record['status']}", 1
        ), encoding="utf-8")
    print(f"{run_id}: {record['status']}; {record['metrics']}")
    print(f"Local artifacts: {output.relative_to(ROOT)}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
