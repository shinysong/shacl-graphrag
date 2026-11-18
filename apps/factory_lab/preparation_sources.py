"""Bounded, lossless source inspection for data preparation.

This module proposes no business truth and executes no uploaded content.
Record numbers are CSV logical records; line ranges are physical source lines.
"""
import csv
from hashlib import sha256
import io
import json
from pathlib import PurePosixPath
import re

MAX_FILES = 24
MAX_FILE_BYTES = 1_000_000
MAX_TOTAL_BYTES = 4_000_000
MAX_ROWS = 200
MAX_COLUMNS = 64
MAX_RELATIONS = 256
MAX_RELATION_BYTES = 1_000_000
MAX_PARAGRAPHS = 256


def _kind(value):
    if value == "":
        return "missing"
    if value in ("true", "false"):
        return "boolean"
    if re.fullmatch(r"-?(0|[1-9][0-9]*)", value):
        return "integer"
    return "text"


def inspect_sources(files):
    """Accept [{name, content}], retaining exact UTF-8 strings and hashes.

    Blank CSV cells remain blank (not zero, false, or an invented record).
    Duplicate names/headers and ragged records are rejected rather than repaired.
    """
    if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES:
        raise ValueError(f"Provide 1..{MAX_FILES} files")
    names = set()
    total = 0
    sources = []
    for item in files:
        if not isinstance(item, dict) or set(item) != {"name", "content"}:
            raise ValueError("Each file requires name and content only")
        name, content = item["name"], item["content"]
        if (not isinstance(name, str) or not 1 <= len(name) <= 120
                or PurePosixPath(name).name != name or "\\" in name
                or any(ord(c) < 32 for c in name) or name in names):
            raise ValueError("File names must be unique plain names")
        suffix = PurePosixPath(name).suffix.lower()
        if suffix not in (".csv", ".txt", ".md"):
            raise ValueError("Only CSV, TXT and Markdown are supported")
        if not isinstance(content, str) or "\x00" in content:
            raise ValueError("File content must be UTF-8 text without NUL")
        try:
            raw = content.encode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise ValueError("Invalid UTF-8 text") from exc
        total += len(raw)
        if len(raw) > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
            raise ValueError("Input byte limit exceeded")
        names.add(name)
        source = {"name": name, "content": content, "bytes": len(raw),
                  "sha256": sha256(raw).hexdigest(), "kind": "table" if suffix == ".csv" else "document"}
        if suffix == ".csv":
            source.update(_table(content))
        else:
            source["paragraphs"] = _paragraphs(content)
        sources.append(source)
    return sources


def _table(content):
    reader = csv.reader(io.StringIO(content.removeprefix("\ufeff"), newline=""), strict=True)
    try:
        headers = next(reader, [])
        if (not headers or len(headers) > MAX_COLUMNS or len(set(headers)) != len(headers)
                or any(not h.strip() or len(h) > 200 for h in headers)):
            raise ValueError("CSV requires unique nonempty headers, at most 64 columns")
        rows, locations = [], []
        previous = reader.line_num
        for values in reader:
            start, end = previous + 1, reader.line_num
            previous = end
            if len(values) != len(headers):
                raise ValueError(f"CSV record at line {start} has wrong column count")
            if len(rows) >= MAX_ROWS:
                raise ValueError("CSV exceeds 200 data records")
            rows.append(dict(zip(headers, values)))
            locations.append({"record": len(rows), "line_start": start, "line_end": end})
    except csv.Error as exc:
        raise ValueError(f"Invalid CSV: {exc}") from exc
    profiles = []
    for h in headers:
        values = [r[h] for r in rows]
        present = [v for v in values if v != ""]
        types = sorted({_kind(v) for v in present})
        profiles.append({"column": h, "observed_types": types,
                         "missing": len(values)-len(present), "distinct_nonempty": len(set(present)),
                         "duplicate_nonempty": len(present)-len(set(present)),
                         "key_candidate": bool(values) and len(present) == len(values) == len(set(values)),
                         "notice": "Observed values only; uniqueness does not establish an identifier"})
    return {"headers": headers, "rows": rows, "locations": locations, "profiles": profiles}


def _paragraphs(content):
    lines = content.splitlines(keepends=True)
    paragraphs, current, start = [], [], 1
    for number, line in enumerate(lines, 1):
        if line.strip():
            if not current:
                if len(paragraphs) >= MAX_PARAGRAPHS:
                    raise ValueError('Document exceeds 256 policy paragraphs')
                start = number
            current.append(line)
        elif current:
            paragraphs.append({"paragraph": len(paragraphs)+1, "line_start": start,
                               "line_end": number-1, "text": "".join(current)})
            current = []
    if current:
        paragraphs.append({"paragraph": len(paragraphs)+1, "line_start": start,
                           "line_end": len(lines), "text": "".join(current)})
    return paragraphs


def relation_candidates(sources, identifier_columns=frozenset()):
    """Value-overlap candidates, not confirmed joins or semantic equivalence.

    Only identifier-like columns participate. All ties remain visible.
    A zero-overlap declared relationship may still exist; it is not inferred here.
    """
    tables = [s for s in sources if s["kind"] == "table"]
    out = []
    output_bytes = 0
    identifier = re.compile(r"(^id$|[_-](id|code|key)$)", re.I)
    for source in tables:
        for column in source["headers"]:
            if not identifier.search(column) and (source['name'],column) not in identifier_columns:
                continue
            values = {r[column] for r in source["rows"] if r[column] != ""}
            if not values:
                continue
            for target in tables:
                if source["name"] == target["name"]:
                    continue
                for profile in target["profiles"]:
                    key = profile["column"]
                    if not profile["key_candidate"] or (not identifier.search(key) and (target['name'],key) not in identifier_columns):
                        continue
                    target_values = {r[key] for r in target["rows"]}
                    overlap = len(values & target_values)
                    if overlap:
                        if len(out) >= MAX_RELATIONS:
                            raise ValueError('Relation candidates exceed 256; split the input bundle or remove unrelated identifier columns')
                        candidate = {"source": {"file": source["name"], "column": column, "sha256": source["sha256"]},
                                    "target": {"file": target["name"], "column": key, "sha256": target["sha256"]},
                                    "matched_distinct": overlap, "source_distinct": len(values),
                                    "unmatched_values": sorted(values-target_values), "status": "pending",
                                    "reason": "Identifier-like names and overlapping values; meaning requires review"}
                        output_bytes += len(json.dumps(candidate, ensure_ascii=False).encode('utf-8'))
                        if output_bytes > MAX_RELATION_BYTES:
                            raise ValueError('Relation candidate output exceeds 1 MB; split the input bundle')
                        out.append(candidate)
    return out
