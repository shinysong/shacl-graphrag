# Actual reviewed-query browser acceptance

Review only new _workspace/extensions-20261119/query-contracts/browser_acceptance.py
and current UI/service as needed. Product code unchanged from passed2f21f4:
workspace175pass1skip, extensionpytest67pass, ops exit0. Reuse those results.
This new harness uses isolated SQLite/document registries, actual local server,
Playwright1440/375, original authored commerce snapshot/policy, UI-only proposals,
approvals and execution. No paid model or upstream calls. Reference SQL is read
only after runtime response and must never repair output. Own server shuts down.

Inspect actual selectors, page state observation vs mutations, same-source hash,
request recording, whole output parity/truncation, no implicit approvals, source
paragraph text, and failure preservation. Scope excludes pagination/recovery/stale
edge cases, model interpretation, independent human or business efficacy.
After independent ready gates run research-ops-tests then actual harness. Do not
rerun unchanged product suite or claim all UI/domain scope completed by smoke.
Reviewers do not execute, edit, inspect each other or evaluation-gold/secrets.
