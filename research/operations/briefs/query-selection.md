# Offline selection diagnostic, meaningful competing queries

Scope: six executable contract tools, six operator-authored compound requests with
15 task obligations, consumed case01 graph. Old paid scopes closed, no LLM/AWS/push.
Permitted source paths: experiments/query_contracts/{core,competing,selection}.py,
scripts/query_selection_diagnostic.py, scripts/score_query_selection.py,
tests/test_query_contracts.py, experiments/factory_complexity/tools.py,
apps/factory_lab/{graph,rdf_graph,evidence}.py. Fixtures permitted:
research/query-contracts-1/selection-development-001/{catalog,requests,scoring}.json.
These authored development intentions are explicitly allowed for reviewer/scorer
inspection, never imported or supplied to runtime selection. No held-out gold,
secrets, other reviews or historical raw calls. Reviewers only write own output.

New fixed actual SQL/SPARQL queries: assigned_machines (ASSIGNED_TO inverse, not
capability candidates); current_qualification_records inclusive date window;
expired_qualification_records valid_until before as_of. These are date-filtered
records, not product-specific eligibility or renewal authenticity. All same selected
view, ISO-date development fixture. SQL and SPARQL independent query implementations;
shared decoding/data/policy, not performance comparison. Catalog six consists of
old3 composer tools plus new3, excluding other3 legacy tools not enabled here.

Compare deterministic lexical top1 with top3 then input/output type filter. Same
full metadata and frozen operator decomposition/bindings, same BM25 top3 score list,
same selected-view registry and12calls per slot. No learned selector, dense search,
LLM, automatic decomposition, automatic semantic intent validation or new domain.
Top3 type filtering and larger search choice are bundled: no claim attributing any
gain solely to type checking vs candidate count. Same-type semantic mismatches can
pass. Zero overlap/empty shortlist unselected. Invalid plans skip all graph queries;
report selections per obligation separately from plan/execution outcomes to avoid
counting one invalid binding as all semantic choices wrong. No fallback/retry.

24 predeclared slots (6requests x2arms x2backends) retained incl failed/unattempted,
checkpointed. Independent posthoc script scores15intentions once per arm using
SQLite lineage; RDFLib slots only parity duplicates. Unsupported delivery/document
authenticity accepted list empty. Correct selection vs wrong selection vs unnecessary
unselected vs correct unselected vs failure denominator explicit. Accepted tools are
manual development labels, not external truth or answer quality. Do not tune after
seeing these results and relabel as held-out. Prototype source and fixtures hashed
in source-manifest.json context before checks and actual diagnostic.

Existing composer conservative multi-capability failure persists; no silent fix.
No answer/SHACL verdict generated. Keep old diagnostic-001 and prior reviewed artifacts.
Registered checks query-contract-tests and factory-complexity-tests. After both
reviewers ready and checks pass, run saved offline selection then separate scorer.
Report failures/negative results candidly. Do not require success before preserving
an output. Identify blockers vs future unsupported features.

V2 correction before execution: checkpoint all24slots before Views/SQL/RDF setup.
On setup failure preserve setup_error and unattempted slots, then fail; close any
initialized SQL backend. Added injected setup-failure control. Original v1 review
blocker preserved; no v1 checks/diagnostic executed.
