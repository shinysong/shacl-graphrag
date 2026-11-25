# Five authored domain source packs

These are the original three small and two medium synthetic inputs used for the fixed 25-question demonstration. Each pack retains five questions verbatim in `runtime-questions.json`, the original schema and documents, and a source mapping in `domain-config.json`. `query-config.json` contains the current investigator-authored typed plans, including later operator follow-ups. It is not natural-language interpretation by a model or an independent answer key. Original result statuses belong to the separate results report; a plan marked `supported` does not establish that an original run succeeded.

## Local generation

From the repository root, with the repository's uv environment installed:

```bash
uv sync --locked
uv run --locked python examples/factory_lab/extensions/domain-packs/generate.py \
  --output _workspace/public-domain-packs
```

The output directory must not already exist. Each generated pack contains `source.sqlite`, `schema.sql`, `documents/`, `domain-config.json`, `query-config.json` and `runtime-questions.json`. The root output `manifest.json` records row counts, SQLite version, integrity and foreign-key checks, file hashes and comparisons with original input hashes. No model, database server, external service, approval or business query is invoked. A failed generation leaves its partial directory for inspection; use a new output directory for another attempt.

Four databases are generated from the original deterministic row construction functions. `commerce-small/source.seed.sqlite` is the original SQLite input, copied unchanged because its originating byte layout is part of provenance. Original source documents are packaged verbatim, including their original formatting. This bundle contains no runtime answers, posthoc reference queries or expected-output fixtures.

The generator supports Python 3.11 or newer. An actual managed Python 3.11.17 run with SQLite 3.53.1 passed all five schema, integrity and foreign-key checks. The four generated DB file hashes differed from the historical bytes; a separate source-to-source comparison found identical ordered rows in every table. The copied commerce seed remained byte-identical. Keep the new hashes when registering these files; do not substitute historical snapshot IDs.

On SQLite 3.45.1, the generated database, schema, documents, source mapping and question hashes matched every corresponding original input hash. `source-hashes.json` records those original hashes. SQLite byte layout can vary by library version; a future mismatch must remain visible in the generated manifest and must not be described as byte identity. This check does not verify the authenticity or semantic quality of upstream outputs. No paid semantic export is distributed or automatically attached.

## Source size

| Pack | Tables | Rows | Documents | Unicode characters | Estimated tokens | Estimated pages |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| commerce-small | 3 | 180 | 2 | 398 | 100 | 1 |
| manufacturing-small | 6 | 280 | 4 | 3,694 | 924 | 2 |
| organization-small | 6 | 280 | 4 | 3,566 | 892 | 2 |
| commerce-medium | 12 | 15,680 | 24 | 23,512 | 5,878 | 8 |
| organization-medium | 12 | 17,250 | 24 | 24,713 | 6,179 | 9 |

Characters include whitespace. Tokens are `ceil(characters/4)` and pages are `ceil(characters/3000)`, both heuristics rather than tokenizer or rendered-page measurements. Per-table counts and check details are in `source-metrics.json`; generation timing and human authoring effort are not measured here. Full SQLite row counts are separate from display limits. The upstream bridge accepts at most 12 tables, 40 columns per table and 16 MiB of source bytes by default. Catalog mode passes the complete registered snapshot for schema/physical-relationship metadata ingestion without applying the semantic row/cell limits. Semantic mode retains the 1,000-row-per-table and cell-size limits; complete medium catalog coverage does not establish medium LLM semantic generation.

## Three small-domain workflows

Follow [Three small-domain reviewed workflows](WORKFLOWS.md) for concrete commerce, manufacturing and organization field/paragraph review, relation approval, question 2 query entry, saved-output RDF projection, RDFS execution and advisory reuse. The recipes use existing public configs and actual UI controls; no binder call approves or executes a query. The [operator recipe](../operator/README.md) covers upstream installation and optional native integration, while the [recorded results](../../../../docs/experiments/records/factory-lab-extensions-20261119.md) distinguish authored paths from the actual commerce generated-semantic adoption. Writing this recipe is not an additional end-to-end execution.

## Mapping and proposal preparation

Register a generated SQLite file and its documents using the registered-source workspace route in [the setup guide](../../../../docs/setup/factory-lab-registered-sources.md). Review field meanings and source paragraphs in the workspace before preparing a proposal. `domain-config.json` lists actual columns and declared foreign keys. Each `query-config.json` uses `table.column` references, a root grain, explicit parameters, joins, filters, projection and any aggregate or reachability settings. These are supplied interpretations that require review, not inferred business truth.

The adjacent `bind_config.py` exposes a pure `bind(config, runtime_questions, draft, policy_review_operation_id=...)` function for operators integrating those configs with an actual saved draft. `draft['entries']` must contain the real reviewed workspace entries with source `file` equal to the table name and `column` equal to the column name. Every referenced field must already have `status: approved`. A policy-dependent plan requires the actual saved paragraph-review operation ID. Do not invent IDs or mark entries approved to bypass that process.

The binder returns proposal dictionaries, relation specifications, parameters and source-question IDs. It performs no service calls, saves no approval, executes no query and does not verify that the supplied review ID exists. Submit its proposed relations and queries through the normal service/UI review lifecycle; current source binding and valid durable review operations are checked there. Inspect and explicitly approve each relation/query before execution. The binder is an optional operator helper, not an automatic runner or a standalone CLI.

For example, `commerce-small-2` starts at `order_items.line_id`, follows `order_items.order_id → orders.order_id`, filters `orders.status = delivered`, groups by `orders.order_id`, and sums `order_items.quantity`. This is a quantity summary, not return eligibility. `commerce-small-3` uses the reviewed return-policy paragraph and states only the delivered-status prerequisite; condition and delivery-date evidence remain absent.

For another domain, map the following items before proposing a query:

| Item | Required decision |
| --- | --- |
| Root | Table, key and one-row meaning; preserve that grain through joins |
| Fields | Real source columns, types, units and reviewed meanings |
| Relationships | Child and parent endpoints, declared FK, direction and cardinality |
| Policy | Actual paragraph review and the bounded interpretation it supports |
| Query | Parameters, filters, projection, grouping and aggregate or traversal bounds |
| Evidence limits | Missing inputs, result truncation, unknown scope and candidate-only claims |

The supplied examples use bounded typed operators, many-to-one joins, integer sum-products, exact scalar bindings and explicit directed reachability where configured. They are not arbitrary SQL, arbitrary recursive queries or automatic policy extraction. Missing-evidence entries stay diagnostics; the binder does not manufacture a query or prove global absence. Source registration, field/relation/query approval and execution remain separate actions.

## License and provenance

Generator and binding code follow the repository's [Apache-2.0 license](../../../../LICENSE). The four newly authored packs' data and documents retain the original `CC0-1.0` dedication recorded in `protocol.json`. This is synthetic data, not downloaded business data or a claim about real organizations.

The pre-existing commerce-small fixture retains its inherited local-authored provenance; its original record did not establish a separate data-license grant. This bundle does **not** silently assign CC0 or Apache-2.0 to that data. Users needing an explicit redistribution grant for that fixture should resolve that provenance gap. Code licensing does not resolve it.

These packs demonstrate reproducible source preparation and authored query setup. They do not establish expert semantic correctness, automatic question interpretation, independent business accuracy, real-world domain transfer, engine superiority or production-scale behavior.
