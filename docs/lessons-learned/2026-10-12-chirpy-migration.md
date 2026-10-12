# 2026-10-12 — Preserve source documents when changing themes

## Context

The first published MkDocs site passed content and build checks but did not receive browser visual review. The user rejected its appearance and selected Chirpy.

## Incident

HTTP success and working links did not establish that the visual result met the user's expectations. Chirpy uses Jekyll, so applying the selected theme also required a different publication build.

## Lesson

Review desktop and mobile layouts before publishing a visual change. Keep experiment Markdown and JSON as canonical sources; generate theme-specific metadata and links in an isolated staging directory. Compare JSON bytes and check the existing URLs after migration.

## Follow-up

- [x] Keep source records in `docs/` and pin the Chirpy dependency.
- [x] Add checks for old URLs, internal links and private-file exclusions.
- [x] Review the built site in desktop and mobile browsers before publication.
