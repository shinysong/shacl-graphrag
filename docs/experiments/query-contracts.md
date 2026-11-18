# Reusable query contracts and compound-question coverage

Status: standalone lexical index and caller-authored composition prototype implemented;
a deterministic selector is now measured on authored development decomposition.
An LLM selector, answer integration and paid comparison are not yet implemented.
The existing fixed query tools are cataloged in
`research/query-contracts-1/catalog-proposal.json`. The executed coverage follow-up
is recorded separately in `research/factory-complexity-1/coverage-live-001/`.

## Problem and mechanism

A query can execute successfully while addressing the wrong subquestion, omitting
another required lookup, or returning evidence insufficient for the final claim.
The proposed intervention represents each reusable query with input/output bindings,
relation direction, supported evidence, nonclaims, result bounds and version scope.
A selector can then retrieve and compose query contracts while retaining unresolved
subquestions. Type compatibility is not verified intent or external truth.

## Initial comparison

1. Full-catalog model selection.
2. Catalog retrieval followed by model selection. Lexical and dense methods are
   separate arms when actually available; lexical search is not a dense baseline.
3. Retrieval with explicit binding and scope checks before composition.

All conditions must have the same catalog information available, frozen source
access, generator configuration, total token/tool-call limits and failure handling.
For selector attribution, freeze the same question decomposition across conditions.
A separate experiment is needed for natural-language decomposition quality or
contract-information ablation. Log exact presented metadata, retrieval overhead,
context truncation and remaining generator budget: equal ceilings alone do not make
realized computation equal.

## Composition invariants and implementation boundary

- Preserve each row's `snapshot`, `source_sha256` and `as_of`. Do not join evidence
  across versions implicitly. A version comparison must retain two independently
  bound result sets rather than merge them into a single current fact set.
- Carry the originating order and its product/required capability through candidate
  and qualification lookups. A machine identifier alone is not a complete decision
  context; do not accidentally attach one order's qualification result to another.
- A qualification match must use product, capability and date from one record.
  Matching fields across several records is not a valid match.
- Bind directed relation semantics explicitly. In the initial proposal an empty
  `relations` list means no enumerated relation contract, not no returned relations;
  `inspect_entity` needs a directional relation contract before formal composition.
- Results at the row limit are potentially truncated. A chain built from such a
  result cannot certify exhaustive question coverage or source completeness.
- Missing services, incompatible inputs and unresolved identifiers remain explicit
  unresolved obligations. No fabricated fallback query or physical approval.

The existing Factory Lab tool validators still check bounded strings. The new
standalone `experiments/query_contracts/core.py` additionally checks selected-view
entity kinds, input/output binding, order context and snapshot/hash/date. The foundation originally enabled
impacted_orders, replacement_candidates and qualification_records; the subsequent
standalone CompetingTools adapter adds assigned_machines and current/expired
qualification-record queries with corresponding composer bindings. Generic
adjacency and two-version comparison remain outside this composer. Qualification
records remain individual rows; policy matching and final answer checking are not
implemented here. The archived catalog-proposal.json retains its original proposal
status; it is not a claim that no separate index now exists.

The executor reads the selected view's full ID/kind registry. This is additional
access beyond individual query results; share and cost it equally in comparisons.
Multiple required capabilities per order are not yet supported generally: a candidate
batch with a different capability fails conservatively with order_context_mismatch.
Do not reinterpret that failure as unavailable qualifications or source absence.

## Evaluation and limits

Track required-query omissions, semantically inappropriate selections, incompatible
bindings, evidence coverage, unsupported certainty, unnecessary withholding, answer
quality, calls, tokens and latency. Distinguish query execution, evidence sufficiency,
policy agreement and externally judged factual truth.

The current six tools and consumed manufacturing cases are development material.
Build new question compositions and genuinely different competing queries before
freezing reserved evaluation; renamed duplicates do not establish scale or domain
transfer. Retain all failures and unattempted slots. No evaluator contracts or gold
answers enter runtime selection or repair. Keep post-answer review fixed during the
selector comparison; compare self/Python/SHACL separately on identical saved inputs.

No budget for additional paid selector experiments is opened by this design file.


## Implemented offline diagnostic

`CatalogIndex` uses BM25 over all contract metadata, English words and Korean
words/bigrams. It is not dense retrieval. Rankings and execution are separate:
`research/query-contracts-1/authored-request.json` supplies the human-authored plan,
not an LLM plan or gold answer. Rankings do not determine its steps.

The saved `research/query-contracts-1/diagnostic-001.json` uses consumed case-01
selected views, actual RDFLib SPARQL and SQLite queries, nine calls each, no failed
calls, equal output rows/context/lineage. The chain returns two impact rows, six
candidate rows and eight qualification-lookup rows (including null qualifications;
not eight unique qualification records). Delivery remains not_planned. This is
integration evidence, not selector quality, answer improvement or engine performance.

Every obligation keeps retrieval status separate from answer/review coverage, which
remain not_evaluated. Reaching a result limit propagates uncertainty. Failed calls
consume the cap; valid partial outputs may remain but downstream unresolved status
is retained. No automatic retry, cross-product, answer generation or query repair.

Reproduce without paid calls from repository root:

```bash
PYTHONPATH=. uv run --locked --offline python scripts/query_contract_diagnostic.py \
  --request research/query-contracts-1/authored-request.json \
  --views research/factory-complexity-1/development-001/runtime/case-01 \
  --output _workspace/query-contract-diagnostic-new.json
```

The output path must not already exist. Tests cover wrong type/dependency, call
budget, foreign version, response entity binding, limit propagation, deterministic
retrieval and actual backend parity. Independent methods/implementation reviews
accepted this bounded scope, with multi-capability and documentation warnings.

## Next decision experiment

Before more model calls, add meaningful competing queries (direct versus transitive
impact, capability candidates versus current assignments, current versus historical
qualifications) with real executable semantics, not renamed duplicates. Freeze new
compound requests with shared caller interpretations and keep evaluator requirements
outside runtime. Connect the model's selected plans to this executor, while keeping
full-catalog and retrieval-only controls equally informed. Record both erroneous
links prevented and valid links unnecessarily blocked. Do not optimize only for a
checker pass rate. Single-record qualification matching and answer-claim coverage
need their own integration checks before claiming an end-to-end coverage system.

The earlier [post-answer comparison is closed](answer-review-closeout.md); its
components remain available without further similar-case campaigns.


## Competing-query selection diagnostic (2026-11-12)

The development bundle `research/query-contracts-1/selection-development-001/`
adds real assigned-machine and date-filtered qualification templates. Its six-tool
catalog is three existing composable tools plus three new tools; it is not the full
nine-tool union or a catalog-size study. The original proposal artifact is unchanged.
The new queries actually execute through SQLite and RDFLib, and date conditions are
applied before LIMIT. Current means inclusive valid_from/as_of/valid_until dates,
not product-specific suitability. Empty filtered queries have no null placeholder.

Both deterministic selectors receive identical BM25 top-three candidates and the
same authored decomposition, typed IDs and dependency paths. Top1 selects the best
positive score; typed-top3 selects the best positive score with compatible declared
input kind. This combines type checking with a larger selectable candidate set.
No LLM, intent parser or learned ranker participates. Actual type registry access and
12-call slot budget remain shared. Invalid plans execute no graph queries, but all
individual selections remain available for posthoc semantic-intention scoring.

Six compound requests contain 15 authored task intentions. Runtime receives neither
expected tools nor scorer labels. The independent *software module* scorer is run
posthoc; its manual labels are not independent human validation or external truth.
The expected-tool rubric may reject a broader query whose results could support a
later transformation: specifically all qualifications instead of current records.
No downstream date filter or final answer was evaluated here.

| Outcome | Top1 | Typed-top3 |
| --- | ---: | ---: |
| Selected query agrees with authored intention | 11/15 | 12/15 |
| Selected query disagrees | 4/15 | 3/15 |
| Correct nonselection of unsupported requirements | 0 | 0 |
| Unnecessarily unselected supported requirements | 0 | 0 |
| Structurally invalid plans | 1/6 | 0/6 |

The recovered plan is r04: a qualification query with Machine input was originally
selected for an Order input. Typed-top3 chose replacement_candidates. Both methods
still substitute qualification lookup for delivery feasibility and document
authenticity, and choose all qualifications for r06's current-scope request.
Input types cannot establish these semantic requirements. All original errors and
rankings remain retained; no post-result prompt/ranking tuning was performed.

All 24 planned slots were recorded. The invalid top1 plan was not executed on either
backend. The other 11 backend pairs returned equal output/context/lineage; inspection
also found zero failed calls or unresolved execution-step issues. There were 84
actual query calls across both backends, not 84 independent questions. Local checks
passed 16 query-contract tests and 13 existing complexity tests. These results do
not measure final-answer improvement, type-checking-only causal effect or engine
performance. See [the execution record](records/2026-11-12-query-selection-development.json).

An initial independent implementation review blocked setup-before-checkpoint failure
loss. V2 now saves all slots before backend setup, preserves setup_error and
unattempted slots, and includes an injected setup-failure test. The original review
is preserved. Backend output equality alone is never treated as successful execution;
call failures and step issues are inspected separately.

Next, expose evidence-support, temporal scope and nonclaims to a model selector,
retain full-catalog controls, and count both unsupported-service substitutions and
unnecessary nonselection. Test candidate-count and type checking separately if making
an isolated mechanism claim. Do not reopen old paid ledgers or relabel this consumed
bundle as held-out evaluation.
