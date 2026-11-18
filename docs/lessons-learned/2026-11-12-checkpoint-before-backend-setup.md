# 2026-11-12 — Checkpoint before graph-backend setup

## Context

The offline query-selection diagnostic declared 24 request/arm/backend slots and
saved the record after each attempted slot.

## Incident

Independent implementation review found that Views, SQLite and RDFLib initialization
preceded the first save. A setup exception would therefore leave no result artifact,
even though per-slot failures were retained. This was caught before the actual run;
no lost experimental result was observed.

## Lesson

Persist the complete planned denominator before initializing execution backends.
Preserve setup failure separately from query failure, leaving never-attempted slots
explicitly unattempted. Close any backend initialized before a later failure.

## Follow-up

- [x] Correct initialization order and preserve setup_status/setup_error.
- [x] Inject a Views setup failure and check all 24 unattempted slots survive.
- [x] Retain the initial blocked review and obtain fresh independent reviews.
- [x] Run the corrected diagnostic and retain all original output slots.
