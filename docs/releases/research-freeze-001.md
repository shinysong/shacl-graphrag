# Research freeze before the public Factory Lab demo

## Scope and version boundary

The baseline manifest at `research/factory-lab-release-1/baseline-001/manifest.json` identifies the Git base and exact working-tree bytes before public-demo development. The worktree contains unpublished changes, so the Git commit alone does not identify the baseline. A private allowlisted archive preserves those bytes; historical execution manifests remain the authority for which files each study actually used.

The released demo will be versioned separately. UI, prompts, adapters and example changes after this boundary are software changes, not retrospectively validated experimental results.

## Observed results

- The Factory complexity campaign completed 12 draft and 36 reviewed final answers in 75 calls. Its independent audit found no clear wrong bounded core judgments, but retained unsupported contention wording, applicability-reason errors, projection omissions and disagreements. See `docs/experiments/records/2026-11-11-factory-complexity-llm.json`.
- The two-model query selector campaign completed 32 calls. Both models made the same selections; one needed query was excluded by retrieval. This measured selection with supplied decomposition, not autonomous query composition. See `docs/experiments/query-model-selection.md`.
- The compound-query campaign completed four original-question decompositions, model-written dependency plans, actual fixed-query execution and twelve final answers across full/retrieved/checked conditions. It used 24 calls and 57 RDFLib queries after preserved manual format recovery. All 16 reference needs were represented in decomposition according to both independent auditors. Four rating disagreements remain. See `docs/experiments/records/2026-11-16-query-composition-live.json`.
- The compound comparison observed no connection vetoes and identical evidence per question across conditions. Incremental checking benefit was not established. Catalog 6/24/72 expansion remains a separate offline preparation, not a paid efficacy result.

## Unverified claims

These experiments do not establish general answer accuracy, an RDF/SHACL-specific advantage over matched Python policy, full-source completeness, measured maintenance labor savings or deployment reliability. They do not authorize physical factory operations. Source absence, selected-view omissions, model interpretation, procedural conformance and external factual truth remain distinct.

## Demo development boundary

The first public release targets installation, understandable execution, evidence lineage, unresolved needs and a small extension example. It does not add another efficacy experiment. Saved historical answers must be labeled replay; local deterministic queries must not be called new LLM execution. No paid API call or cloud start is part of release preparation.
