# Add one fixed query and its contract

The public demo currently uses six fixed tools. A contract is searchable metadata plus an input/output interface; it does not itself implement a query or establish user intent.

## Runnable example

Run the included extension without credentials:

```bash
uv run --locked python -m examples.factory_lab.extensions.unavailable_candidates
```

`examples/factory_lab/extensions/unavailable_candidates.py` defines `unavailable_candidates`: given an Order ID, return capability candidates whose recorded status is `unavailable`. It adds a fixed status filter to the existing SPARQL template, checks that the expected template fragment occurs exactly once, requires an Order ID present in the selected snapshot, uses the existing argument validation and decoder, and reports only the selected-view result.

The example is **not enabled in the default six-tool catalog**. Running it executes the new query directly and demonstrates catalog indexing; it does not call an LLM. Its result cannot establish schedule availability, qualification applicability or operational approval.

## Registering the example in a local fork

Make these changes together in your fork; metadata alone must not enable execution:

1. Add the example's `CONTRACT` to `examples/factory_lab/catalog.json` under `catalog`. Keep its semantic input, output binding paths, supported facts and unsupported claims consistent with the query.
2. Register `unavailable_candidates` in `experiments/query_contracts/core.py` `BINDINGS` using the example's `BINDING`. This enables declared `Order` input and `order.id`/`machine.id` output checking.
3. Extend the backend dispatch used by `Demo.run` in `apps/factory_lab/public_runtime.py`. Handle the exact tool name with a fixed query implementation. Return the same envelope as `CompetingTools.run`: tool, arguments, snapshot, source_sha256, as_of, rows, query, backend, scope and limit_reached. Use the active `Views` snapshot/hash rather than reading a different dataset. Delegate existing names unchanged. Do not evaluate LLM-supplied query text.
4. Add an execution test proving the status filter, preserved Order ID, argument rejection, empty-result interpretation and declared row bindings. Test wrong-type and missing-dependency plans as well as a successful chain.
5. Update `examples/factory_lab/manifest.json` for intentionally changed fixture bytes after reviewing the diff. Preserve the original study manifest and saved historical examples. A changed catalog is a new demo revision, not a rerun of the old study.
6. Run the public tests, then try a new question with your own explicitly enabled API session if desired. A passing fixed-query test does not prove the model will select it correctly.

The first release deliberately keeps these registration points explicit. A generic plugin system is deferred until a second real use case needs it.

## Contract fields

| Field | Meaning |
| --- | --- |
| tool / id / revision | Stable dispatch identity and metadata revision |
| description | Searchable human explanation of the lookup |
| input | Parameter name and semantic entity type |
| output_bindings | Row paths another step may use |
| evidence_support | Facts the query can supply |
| does_not_establish | Decisions the result alone cannot justify |
| result_limit / empty_semantics | Bound and interpretation of incomplete/empty output |

Input type and connection checks cannot prove that the right query was chosen for the user's meaning. Preserve valid-but-wrong selections as visible results when evaluating an extension.
