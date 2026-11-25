# External approval and local reasoning boundary

Review current implementation read-only at these paths:
- apps/factory_lab/workspace_extension_review.py
- apps/factory_lab/workspace_service.py
- apps/factory_lab/preparation.py
- apps/factory_lab/workspace_lookup.py
- apps/factory_lab/workspace_extensions.py
- apps/factory_lab/open_ontologies_runner.py
- tests/test_workspace_extension_review.py
- tests/test_workspace_open_ontologies.py

Scope: external native YAML import remains pending; an explicit human batch decision binds supported physical fields to existing workspace entries, uses existing mapping approval and creates one atomic revision. Preserve raw imports, failure attempts, idempotency, stale source/revision protection and prior approvals. Provenance describes user-selected correspondence, not proof that the CSV came from an exported DB. Canonical targets and source-only mappings use existing checks. Unselected original candidates become stale after a successful batch. Restore/export preserve provenance; refresh invalidates active annotations. Row lookup receives bounded provenance.

Local OpenOntologies adapter is separate and unintegrated: fixed load/reason/save through trusted operator executable, <=1MB input, process/time/output limits, isolated config, raw facts/closure/derivation artifacts, no inherited keys or automatic approval. Partial fixpoint must remain partial. This is not a network sandbox or certified verification. Source binaries are trusted. Inspect failure retention and misleading-completion risks before an actual bounded upstream smoke invocation. Build may still be running; no actual reasoning execution is yet claimed.

Reviewers may read these explicit source/tests and supporting local modules needed to understand call contracts; do not read another review, secret env files, raw historical model answers or evaluation gold. Write only designated review result. Existing focused tests are software fixtures, not actual semantic efficacy. UI is being independently implemented and is excluded from this backend review; no claim of browser acceptance.

Registered checks: workspace-tests and research-ops-tests. Full goal also requires actual upstream semantic compilation, real RDF receipts displayed in UI, three small/two medium domains and browser/docs verification; these remain incomplete. No paid calls are covered by this review.

Updated review scope includes actual UI implementation at apps/factory_lab/public_static/workspace.js and workspace.css. Inspect optional import, saved result browsing, staged batch approval, stale state and pending request recovery. Exact payload/key is retained before sending; unknown/not-recorded must retain identity and only explicit same-key replay is permitted. Existing local generator/recovery/navigation must remain functional. Browser acceptance is pending and cannot be inferred from syntax/tests.

Prior review found timeout erased already-written closure/certificates. Current runner extracts bounded artifacts after success/failure/timeout and labels noncompleted output unverified_partial. Inspect this correction. Prior raw critique retained; a post-edit submission was rejected by frozen-input protection rather than overridden. This is a fresh job for final frozen source.

Second correction: saved completed extension approval now refreshes the current row even for the same workspace. Volatile external drafts have an independent guard used by canLeave/beforeunload; ordinary review-buffer save/restore retains that protection and states external drafts are excluded. Uncertain extension send renders recovery controls immediately without clearing payload/key/draft maps. Verify these changes and remaining interactions; prior reviews were submitted as revise before mutation, not overridden.

Third correction: terminal extension identity is now cleared only after current-row reconciliation and saved result rendering succeed. A cancelled canLeave or failed fetch preserves the original request identity. Normal completed approval fetches current row before show clears stale drafts; no earlier manual deletion. Check this ordering before gates. Private browser harness at _workspace/extensions-20261119/browser/check_extensions.py is prepared but unexecuted; it uses actual catalog-only export, local scripted response loss and no paid/model gateway.
