# Competing-query selection development diagnostic

This bundle contains six executable query contracts, six authored compound requests
with 15 decomposed tasks, and a separate posthoc expected-selection rubric. It reuses
case-01's consumed synthetic selected graph. It is not a held-out dataset or a
natural-language parsing/LLM benchmark.

`requests.json` supplies text, initial typed identifiers and dependency paths, but no
accepted tool IDs. Both selectors see the same runtime request and catalog. `scoring.json`
is supplied only to the posthoc scorer after execution records have been saved.
Accepted tool IDs represent the author's intended query semantics; their correctness
is not evidence of external factual truth or final-answer quality.

The full original proposal catalog has six old tools. This comparator catalog instead
contains three old composable tools plus three new meaningful competitors. It is
still six tools, not a nine-tool scale evaluation. The union now has nine searchable
query definitions, but the original historical artifact is unchanged.

- `impacted_orders`: selected direct assignments for a machine.
- `replacement_candidates`: machines connected to required capabilities.
- `assigned_machines`: currently assigned machines for an order.
- `qualification_records`: all selected qualification records, including null
  placeholder for an existing machine without linked qualifications.
- `current_qualification_records`: records whose date interval includes as_of.
- `expired_qualification_records`: records whose valid_until precedes as_of.

The date-filtered tools return no null placeholder when no record matches. They do
not establish order-product applicability, authenticity, physical approval or source
absence. This fixture uses valid ISO date strings; malformed/missing dates require
separate investigation and are not an inference about source truth.

Two arms use the same BM25 top-three rankings and per-slot twelve-query cap. Top1
selects the highest positive-score query. Typed-top3 chooses the highest positive-score
query with compatible supplied input/output kind. The latter bundles type checking
and a larger choice set, so differences do not isolate the causal effect of types.
An invalid plan executes no queries; the scorer nevertheless preserves each selected
tool and scores intentions separately from execution failure. Same-type semantic
mistakes and selection of unsupported-service substitutes are expected failure modes.

Run the runtime and scorer separately from the repository root with new output paths:

```bash
PYTHONPATH=. uv run --locked --offline python scripts/query_selection_diagnostic.py \
  --requests research/query-contracts-1/selection-development-001/requests.json \
  --catalog research/query-contracts-1/selection-development-001/catalog.json \
  --views research/factory-complexity-1/development-001/runtime/case-01 \
  --output _workspace/query-selection-new.json
PYTHONPATH=. uv run --locked --offline python scripts/score_query_selection.py \
  --results _workspace/query-selection-new.json \
  --rubric research/query-contracts-1/selection-development-001/scoring.json \
  --output _workspace/query-selection-score-new.json
```

Keep failed/unattempted slots and old results. Do not tune to this bundle and then
report it as fresh evaluation. No paid API, AWS or app restart is needed.
