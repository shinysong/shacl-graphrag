# 2026-10-12 — Verify Git objects when publishing through a connector

## Context

Publish the validated E0 experiment and MkDocs site to GitHub Pages after explicit user authorization.

## Incident

The host had no Git HTTPS credentials, so `git push` failed. The connected GitHub app had repository write access and provided Git object APIs.

An initial bulk transfer through shell output produced a remote tree that did not match the local commit. Comparing blob hashes exposed a corrupted document and missing entries. The incorrect tree was never attached to the published branch.

Reading the remaining blobs as bounded base64 chunks, verifying each returned blob SHA, and constructing a tree from the complete local manifest produced the exact local tree SHA. The branch was then advanced with an expected-head check and without force.

## Lesson

Do not assume a large tool response preserves file bytes, even if its JSON can be parsed. Verify blob and tree hashes before updating a remote branch. Use bounded chunks when transferring large files through tool output.

## Follow-up

- [x] Verify the complete remote tree against the local commit before publication.
- [x] Align the local branch with the identical tree committed through the GitHub app.
- [ ] Configure host Git authentication if direct CLI pushes are needed later.
