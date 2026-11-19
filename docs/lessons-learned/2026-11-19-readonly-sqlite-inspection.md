# 2026-11-19 — Read-only inspection of historical SQLite runs

## Context

A browser recovery copied an earlier failed workspace into a new run directory. The recovery used SQLite's backup API with a read-only source connection and checked the source file hash before and after execution.

## Incident

The recovery finished with its original-file hash assertion passing. A later coordinator check opened the historical file with the application’s `WorkspaceStore` constructor. That constructor initializes tables and writes `PRAGMA user_version=1`, even when the caller only intends to read existing operations. The SQLite file hash changed after the recovery had finished. The original failure outcome remained recorded; no new question was inserted into the historical database. The pre-inspection hash and changed-file hash were retained rather than reconstructing a guessed header.

## Lesson

Inspect historical artifacts through `sqlite3.connect("file:path?mode=ro", uri=True)`, not through an application store that runs migrations. A read method does not make its constructor read-only. Distinguish logical row preservation from byte-for-byte file identity.

## Follow-up

- [x] Retain the failed check and pre/post physical hashes in the private recovery record.
- [x] Use an explicit read-only connection for the new-operation identity check.
- [ ] Audit other historical inspection helpers before reuse; no repository-wide audit is claimed.
