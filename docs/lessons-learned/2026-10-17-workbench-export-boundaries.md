# 2026-10-17 Workbench export boundaries

## Context

The local rule workbench exports reviewed rules separately from opt-in source records. Users can reload a metadata-only JSON workspace and reconnect data later.

## Incident

The first implementation converted reference-table values into SHACL `sh:in` lists. Omitting `data.ttl` was insufficient: those values still appeared in `shapes.ttl`. Independent review also found that a reloaded redacted table was classified as a genuinely empty table, and malformed allowed-value parameters could pass import validation but crash the editor.

## Lesson

Check every exported artifact for source-derived values, not only files named as data. Reference membership now uses class assertions in the RDF data graph; shapes contain the structural condition. A sentinel regression checks default archive members. Redacted source absence is reported as unknown, while a genuinely empty mapped table remains not applicable. Validate parameter structure before rendering imported projects.

## Follow-up

- [x] Preserve reference values only in opt-in RDF data.
- [x] Test metadata-only reload and malformed parameter imports.
- [x] Revalidate exported RDF and SHACL and compare individual violation pairs.
- [x] Keep failed review records and obtain fresh independent reviews after changes.
- [ ] Verify the PostgreSQL connector against an authorized live database before claiming live integration coverage.
