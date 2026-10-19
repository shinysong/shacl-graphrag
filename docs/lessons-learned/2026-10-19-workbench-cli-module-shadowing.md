# 2026-10-19 — CLI filename shadowed the library

## Context

Before publishing accumulated work, CI was expanded to install workbench dependencies and discover both unittest and pytest tests.

## Incident

Full pytest collection failed because older tests prepend `scripts/` to the Python import path. The file `scripts/rule_workbench.py` then shadowed the `rule_workbench` package. Scoped workbench tests had passed because their import order differed. The failure was preserved before changing code.

## Lesson

A CLI wrapper should not share its filename with an importable package when scripts and libraries can share the module search path. Scoped tests do not replace a full collection check before publication.

## Follow-up

- [x] Rename the unchanged CLI wrapper to `scripts/run_rule_workbench.py` and update the current usage guide.
- [x] Obtain independent review before rerunning checks.
- [x] Execute the renamed CLI with real offline demo validation and export.
