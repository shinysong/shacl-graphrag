# 2026-10-29 — Explicit static demo assets in Chirpy

## Context

The actionable evidence demo passed source-directory browser checks. Canonical
Markdown pages linked to its standalone HTML page.

## Incident

The first Chirpy build generated the Markdown pages but omitted the new HTML,
JavaScript, CSS and font assets. `prepare_chirpy.py` copied only previously named
demo directories. The site checker failed on two missing demo links; a subsequent
browser check timed out because the case selector was absent. Neither failure was
reported as a successful site check.

## Lesson

A source-directory browser pass does not verify the final published artifact.
Register standalone public assets explicitly in the site preparation script and
check the final output before reporting site readiness. Keep private workspace
files outside this asset list.

## Follow-up

- Added an explicit eight-file list for the new demo, including the font license.
- Preserved the failed build and browser attempt records.
- Require final-site asset byte comparison, browser checks and fresh independent
  review after this build-script change.
