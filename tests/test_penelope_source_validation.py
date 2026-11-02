"""Copy-only software controls; these are not new source observations."""

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from rdflib import RDF

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "penelope_validator", ROOT / "scripts/validate_penelope_source.py"
)
v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v)
SOURCE = ROOT / "research/actionable-evidence-1/source/workbook-extraction-v1.json"


def fixture():
    source = json.loads(SOURCE.read_text())
    source["workbooks"] = source["workbooks"][:1]
    source["workbooks"][0]["records"] = source["workbooks"][0]["records"][:1]
    return copy.deepcopy(source)


def check(source):
    graph = v.project(source)
    conforms, actual, _report, _readable = v.shacl_checks(graph)
    assert actual == v.python_checks(source)
    assert conforms == (not actual)
    return actual


def test_equal_endpoints():
    source = fixture()
    record = source["workbooks"][0]["records"][0]
    for start, end in v.PAIRS:
        record["values"][end] = record["values"][start]
    assert check(source) == set()


def test_missing_and_wrong_type_do_not_order():
    for field in ("x_init_mm", "x_end_mm", "sample_init", "sample_end"):
        for value, kind in ((None, "required"), ("bad", "type"), (True, "type")):
            source = fixture()
            record = source["workbooks"][0]["records"][0]
            record["values"][field] = value
            assert check(source) == {(record["id"], field, kind)}


def test_descending_intervals_independent_and_requests():
    source = fixture()
    record = source["workbooks"][0]["records"][0]
    for start, end in v.PAIRS:
        record["values"][start] = 9
        record["values"][end] = 2
    failures = check(source)
    assert failures == {(record["id"], start, "order") for start, _ in v.PAIRS}
    actions = v.requests(source, failures)
    assert len(actions) == 2
    assert all(r["action"] == "request_source_confirmation" for r in actions)
    assert actions[0]["source_file_sha256"] == source["workbooks"][0]["sha256"]
    record["values"]["sample_init"] = None
    assert any(
        r["action"] == "request_evidence" for r in v.requests(source, check(source))
    )


def test_unknown_and_wrong_namespace_references():
    for reference in (
        "PP3:defect_code:9999",
        "PP4:defect_code:2",
        "PP3:welding_settings_code:2",
    ):
        source = fixture()
        record = source["workbooks"][0]["records"][0]
        record["dictionary_refs"]["defect"] = reference
        assert check(source) == {(record["id"], "defect", "reference")}
    source = fixture()
    record = source["workbooks"][0]["records"][0]
    record["dictionary_refs"]["defect"] = None
    assert check(source) == {
        (record["id"], "defect", "required"),
        (record["id"], "defect", "reference"),
    }


def test_wrong_class_and_valid_but_wrong_code_rdf_controls():
    source = fixture()
    graph = v.project(source)
    record = source["workbooks"][0]["records"][0]
    ref = v.reference_uri(record["dictionary_refs"]["defect"])
    graph.remove((ref, RDF.type, v.P.DefectCode))
    graph.add((ref, RDF.type, v.P.SettingCode))
    assert v.shacl_checks(graph)[1] == {(record["id"], "defect", "reference")}
    source = fixture()
    record = source["workbooks"][0]["records"][0]
    record["dictionary_refs"]["defect"] = "PP3:defect_code:1"
    assert check(source) == {(record["id"], "defect", "reference")}


def test_cli_exclusive_and_artifacts(tmp_path):
    source_path = tmp_path / "copy.json"
    source_path.write_text(json.dumps(fixture()))
    output = tmp_path / "output"
    command = [
        sys.executable,
        str(ROOT / "scripts/validate_penelope_source.py"),
        "--input",
        str(source_path),
        "--output-dir",
        str(output),
    ]
    assert subprocess.run(command, capture_output=True, check=False).returncode == 0
    assert (output / "input.json").read_bytes() == source_path.read_bytes()
    manifest = json.loads((output / "manifest.json").read_text())
    assert set(manifest["hashes"]) == {
        "input.json",
        "validator.py",
        "shapes.ttl",
        "contract.md",
        "uv.lock",
    }
    for name in (
        "data.ttl",
        "report.ttl",
        "report.txt",
        "records.json",
        "requests.json",
        "summary.json",
    ):
        assert (output / name).exists()
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    assert subprocess.run(command, capture_output=True, check=False).returncode != 0
    assert before == {p.name: p.read_bytes() for p in output.iterdir()}


def test_unsupported_schema_preserves_failed_attempt(tmp_path):
    source = fixture()
    source["schema_version"] = "unsupported"
    source_path = tmp_path / "copy.json"
    source_path.write_text(json.dumps(source))
    output = tmp_path / "failed"
    command = [
        sys.executable,
        str(ROOT / "scripts/validate_penelope_source.py"),
        "--input",
        str(source_path),
        "--output-dir",
        str(output),
    ]
    assert subprocess.run(command, capture_output=True, check=False).returncode != 0
    assert "unsupported source schema_version" in (output / "failure.txt").read_text()
    assert (output / "input.json").read_bytes() == source_path.read_bytes()
    assert (output / "manifest.json").exists()
