# Query-contract foundation and old-study closure

Implement standalone offline prototype, no paid/AWS/UI changes. Main sources:
experiments/query_contracts/core.py, scripts/query_contract_diagnostic.py,
tests/test_query_contracts.py, research/query-contracts-1/catalog-proposal.json,
research/query-contracts-1/authored-request.json, docs/experiments/query-contracts.md.
Dependency allowed: experiments/factory_complexity/tools.py, apps/factory_lab/rdf_graph.py,
graph.py, evidence.py. Read scripts/research_ops.py and tests/test_research_ops.py
for new static query-contract-tests/research-ops-tests allowlists.
Do not inspect evaluation folders, secrets, other reviewers or historical raw calls.

BM25 ranks full metadata with English words/Korean word+bigrams, no embeddings.
Plan is caller authored, explicitly NOT selected from the returned rankings or
LLM-generated. The runtime request is supplied interpretation, NOT evaluation gold.
Three closed executable tools only: impact -> candidates -> qualifications. Other
catalog tools searchable but unsupported by this initial composer. Type checks use
full selected-view entity-kind registry (additional offline access; share and count
this equally in future comparisons), never full original source/evaluation.
No SQL/SPARQL text generated. Preserve order/product/capability context and exact
version/hash/as_of; per-row lineage, no implicit cross-product. Missing type,
wrong response binding/version/context, failures, budget exhaustion stay recorded.
Failures consume budget, no retry or repair. Limit flags propagate. Empty selected
view is not global absence. No qualification matching, truth, final answer or
semantic obligation satisfaction claimed. Single-record policy matching remains
downstream. Fields explicitly say answer/review coverage not evaluated.

Registered checks: query-contract-tests, research-ops-tests, factory-complexity-tests.
Then offline actual RDFLib/SQLite diagnostic using consumed case01 selected view,
30call cap each. Report full records and output parity only, not benchmark or
selector gain. Current 6 queries insufficient for generalization. New competing
queries and question compositions must precede reserved evaluation/model comparison.

Close existing post-answer comparison as bounded exploratory evidence: no clear
core judgment gain, some wrong reason-code corrections in both Python and SHACL,
no RDF-specific advantage; preserve report-introduced overstatement and failures.
No new paid scope is opened, unused prior budgets remain closed. No push/restart.
Please independently review methods validity / implementation failures; write only
own result. Main performs all edits. Mark missing future features as scope limits,
not as implemented. Block actual safety/correctness faults in this bounded scope.
