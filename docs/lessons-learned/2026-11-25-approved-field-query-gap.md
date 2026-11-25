# 2026-11-25 — Field approval and executable source reads

## Context

A workspace had approved product identifiers, names and recorded quantities, but a question asking for positive remaining quantities returned no query evidence.

## Incident

The saved planner received an empty approved-query catalog and selected no calls. Field review had not created a reusable query approval. The model therefore had no business-query operation for the requested filter, despite permission to reuse the source fields. The server returned a generic English no-evidence message. This was an execution-capability gap, not a SHACL validation result or evidence that the source lacked products.

## Lesson

Separate reading approved source fields from approving reusable joins, business decisions and policy applications. A fixed single-table tool can expose bounded typed filters and approved projections without accepting model-generated SQL. Validate field permissions, source hashes and current review versions on every execution; retain counts, omitted rows, type exclusions and child execution records. A positive recorded quantity does not establish current stock or full order eligibility.

## Follow-up

- [x] Add actual snapshot and service tests for private fields, numeric types, NULL, truncation, source drift, cancellation, revision changes and replay.
- [x] Keep original failed/no-execution outcomes and distinguish the new routing version.
- [x] Explain future no-execution outcomes separately from empty matching results.

Software checks do not establish general natural-language selection accuracy. A separate actual-model run is recorded privately; its outcome must be assessed independently of these checks.
