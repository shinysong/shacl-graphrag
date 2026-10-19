# 2026-10-19 — Connector display names and source identity

## Context

Four domain fixtures were exported as CSV, Excel, SQLite and JSON for identical row-level checks.

## Incident

Independent review found that the test adapter treated an Excel display name as a table identifier. The connector labels a sheet `data.xlsx / WorkOrders`, while its source metadata records `sheet: WorkOrders`. The assumption would break the test's explicit fixture mapping. Review blocked execution; no labels or data were changed to make the check pass.

## Lesson

Use connector provenance fields (`source.sheet`, `source.table`, or the known CSV source filename) for explicit fixture bindings. Keep user-facing display names separate from stable IDs. This binding is an authored test adapter, not automatic schema matching.

## Follow-up

- [x] Correct runner and tests, then obtain fresh independent reviews.
- [x] Verify every row status across four formats and four 200-row domain fixtures.
