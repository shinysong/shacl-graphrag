# Explicit modelling-rule inventory

Four pinned MachineTool/IA XML files are inspected for explicit forward UA
`HasModellingRule` references. Each source is a separate retained slot; duplicate
references on a node are set-deduplicated. Labels are six identifier-name facts
from the source-linked OPC Foundation NodeIds CSV. Original XML MIT 1.00 notices
remain in their files. The CSV license was not separately verified, so the CSV
is not redistributed here. Downloaded specification HTML remains private.

Run from the repository root with `uv run --locked python` followed by `check.py`
or `inventory.py` in this directory. Successful source slots have 371, 76, 407,
76 explicitly marked nodes respectively. These are repeated node occurrences
across versions, not 930 independent examples. `raw-xml-audit.json` records a
separate coordinator enumeration without importing the runtime implementation.

Version 001 was blocked before measurement because malformed hash-matching XML
could escape the per-source exception boundary. Version 002 catches ParseError
and checks preservation of all four slots. Both versions and reviews remain.

This is not inherited InstanceDeclarationHierarchy computation, generated SHACL,
physical asset conformance, compatibility resolution or a benchmark. The prior
ObjectType closure experiments do not implement these modelling-rule semantics.
