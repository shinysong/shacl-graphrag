# Optional upstream execution and saved-result usability

Review the current changed files and the bounded paths below. This is a software
and integration gate, not a claim of full compound-question or semantic efficacy.

## Native reasoning boundary

`apps/factory_lab/open_ontologies_runner.py` separates the process per-file scratch
ceiling (16 MiB) from returned-file evidence limits (service: 128 KiB). Actual old
browser run `oo-run-20261119T152934753273Z` failed with exit -25. The pinned upstream
initializes a SQLite state database even for an in-memory graph. Direct diagnostic
in `_workspace/extensions-20261119/reasoning-resource-fix/` identifies its WAL as the
first limit failure; the modified runner completed the same input. These actual
observations do not replace independent review or the next real browser run.

Inspect bounded stdout/stderr/event parsing, closure/certificate prefixes and hash
scope, timeout/failure retention, reservation compatibility and hard wall/memory
limits. The limit is per file, not a total disk or network/process sandbox. Raw
certificates are unverified; uploaded RDF membership in a workspace is unverified.
No reasoning receipt approves mappings or claims external truth.

## Native auto-ontology bridge

Inspect new `auto_ontology_bridge.py`, `auto_ontology_cli.py` and their workspace
tests when present. The operator selects a registered immutable source and an
installed pinned upstream, not an uploaded executable. Catalog-only execution
must not activate a model. Semantic execution requires explicit trusted gateway
configuration and remains subject to the existing cumulative budget and deadline.
Tested fake subprocesses are not evidence of actual upstream execution. No paid
launch is authorized by this review task. Preserve input/version hashes, stage
failures, native exports and the pending-review boundary. Unsupported larger
sources must be rejected explicitly rather than silently truncated or declared
supported. Fresh native invocations must not accidentally reuse another source's
catalog or previously generated semantic results.

## Browser usability correction

Actual generic browser run `browser-run-20261119T152934764536Z` passed ten bounded
source-only cases over three small and two medium authored snapshots. Recovered
native semantic export hash was
`3abe811db181e8532644cbabea335d4177d1e42c071184aeecda9c68888b50f7`.
Visual review nevertheless found confusing terminal recovery messaging, hidden
saved query conditions and cramped mobile approval comparison.

Review current workspace.js/css and private generic-db/check_browser.py:
terminal saved requests may collapse but unknown/running recovery and idempotency
must remain intact; saved predicates must come from the saved operation/result,
not the current form; mobile confirmation must expose prior/proposed meaning,
physical target and effect before explicit approval. Preserve raw provenance.
Check actual OO browser harness too; its pre/post comparison is raw text position
difference, not semantic RDF change analysis.

## Gates and limits

The previous implementation review identified a real connector-resolution gap:
creating a connector alone does not bind upstream semantic profiling or export's
global resolver. Require the revised child to resolve exactly its invocation
snapshot through the native resolver, reject unrelated saved connections without
deleting them, and test this binding for different sources. Preserve that review.
Root's private `generic-auto-bridge/run_catalog_acceptance.py` is a proposed actual
catalog-only driver: two registered small sources, existing owned stopped service,
explicit private config, no model gateway, bounded readiness check and finally
stop. Review its scope before use; no actual invocation has yet been performed.

Run registered workspace-tests and research-ops-tests only after both independent
reviewers accept. Then root may run actual generic and OO desktop/mobile harnesses.
Pass the recovered export explicitly. Keep all prior failures and skipped cases.
Do not modify source or tests while this job is frozen. Reviewers write only their
own result and do not inspect one another's outputs, secrets or posthoc gold.

Remaining full-goal work includes reusable compound queries, policy documents,
approved relation execution, all predeclared question types, own-data actual
upstream bridge execution and public reproducible setup/limitations. Exact-field
source reuse alone must not be relabeled as completing those requirements.
