# Generic approved relational queries and source paragraphs

Review new workspace_query_contracts.py, workspace_source_documents.py,
workspace_query_service.py, workspace_document_service.py and integration in
workspace_service.py/public_server.py plus new matching workspace tests.

Goal gap: registered sources currently expose only exact field lookup. This
increment adds domain-independent approved single-FK child-to-parent LEFT joins,
typed filters, grouped SUM/COUNT/COUNT DISTINCT over complete immutable snapshots,
plus separate hashed text paragraph registration/review/reuse. It is not the full
UI/LLM/domain acceptance. No paid run or upstream execution in this increment.

The executor artifacts are outside existing adapter drafts. Service clients send
pending specs, then explicitly approve saved proposals by operation IDs. They
cannot submit approved artifacts directly. Store-scoped operation IDs load
relations/query approvals, preserve idempotency and failures, and runtime checks
exact field and relation fingerprints against current source/review bindings.
Inspect parent uniqueness, join grain, null/date/numeric semantics, result count
before truncation, runtime/resource bounds and provenance. Review metadata is a
local annotation, not authenticated identity or semantic correctness.

DocumentSources is operator-injected, no HTTP filesystem paths. It preserves
original UTF8 text/markdown with hash-bound paragraphs and source DB snapshot,
rejects unsupported inputs rather than claiming PDF parsing. Source changes do
not rewrite old bytes. Service paragraph approval is a reference approval, not
an executable policy or a statement that it applies. Query service accepts only
saved paragraph-review IDs as policy_references and rechecks content/binding.
Engine annotations alone do not verify documents. Check failures and stale scope.

No UI has been added for these new actions yet. New tests have not been run before
this gate. Use registered workspace-tests and research-ops-tests after both
independent reviews READY. Reviewers read only their own request/source; do not
read another review, secrets or posthoc gold, modify code or execute checks.
Actual browser, complete five-pack questions, external relation provenance,
full own-data documentation and public reproducible examples remain required.

## Revision after 43a7f1

Both prior reviews are preserved as revise. Correct parent/child comparison
semantics for mixed SQLite affinities and verify child-root multiplicity; keep the
same predicate in unmatched-parent diagnostics. Regression uses parent TEXT keys
'01'/'1' and INTEGER child1. Add bounded original paragraph preview before any
approval, with a test asserting preview creates no review operation. The query
execution timeout does not include prior registry/contract-validation work;
individual earlier queries retain registry deadlines, not one global deadline.

After registered checks root may execute private
_workspace/extensions-20261119/query-contracts/check_commerce_actual.py: actual
existing commerce-small full snapshot and authored return paragraph, scripted
(not independent human) decisions through service, FK group SUM over delivered
orders, saved citation and execution. No model/network/service launch. This is
one authored compound-query integration, not five-domain acceptance or efficacy.

The prior workspace-tests registration uses unittest discovery and does NOT run
pytest function tests. Add fixed registered workspace-extension-pytest covering
new executor/service/document modules and existing DB adapter/service tests;
review scripts/research_ops.py new constant command. Do not count unittest-only
passes as validating pytest functions. Both discovery styles are required here.
