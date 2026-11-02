# Source corpus and development-question interface review

Independent read-only review. Write only assigned output. No source edits,
network, API calls, installs or retrieval/generation campaign. No other reviewer
outputs, secrets, old raw QA traces or held-out gold. Explicitly authored
development references below are in-scope; not held-out evaluation gold.

Allowed evidence:
- scripts/build_graphrag_corpus.py
- tests/test_graphrag_corpus.py
- research/graphrag-evidence-1/source-corpus-v1.json
- research/graphrag-evidence-1/development-questions.json
- research/graphrag-evidence-1/development-references.json
- research/graphrag-evidence-1/input-output-contract.md
- research/actionable-evidence-1/source/workbook-extraction-v1.json
- docs/journal/2026-11-01-graphrag-source-contract.md
- docs/experiments/graphrag-evidence-study.md
- _workspace/graphrag-cycle1/{verification.json,corpus-build.log,tests.log}

Current deliverable: source-only corpus builder, deterministic consumed real
source artifacts, six selected consumed rows times four authored question types
(24developmentquestions,18sourceanswerable,6review-versionabsentfrombundle),
runtime/scorer split and PROPOSED runtime contract. Actual extraction is existing
243rows. New nodes243+85, edges486; all facts also in814textchunks forA/B.
Raw-cell/saved-value/codebook scopes crosschecked; no inferred design/workflow
edges. No fresh cohort, LLM experiment, vector baseline, SHACL runtime or
GraphRAG efficacy result. No claim missing from whole originalarchive/factory.

Methods: assess scope/claims, same-information comparator, repeatedcodebooks,
question provenance and denominators, sensible interpretation of nominalvalues,
runtime-scoring separation and unknown vsvalidationpass. DsameCevidence only;
report treatment notforcedveto; future noadditionalhiddenmetadata.

Implementation: inspect source-only builder, derivation hashes/exclusive output,
correct raw-cell/codebook resolution, reproducible counts/header/null retention,
source-attribution preservation, references/questions integrity. Check prospective
IO contract for implementability without treating deferred runtime as existing.
Do not report no leakage merely from filenames; access checks still planned.

Registeredchecks=[]; manual8unitchecks/build/artifactvalidation are logged
separately. Any source authenticity or physicaltruth not established here stays
unverified. User's8h deadline2026-11-01T12:14:01.046Z and paidAPIstop persist.
