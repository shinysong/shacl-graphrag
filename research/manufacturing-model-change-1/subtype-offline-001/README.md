# Published ObjectType hierarchy diagnostic

Two preserved MachineTool XML projections; 62 local ObjectTypes and 150 model objects per version. This is a partial positive ObjectType ancestry/type-membership projection, not a complete OPC UA interpreter or operating-equipment inventory. External model definitions are absent.

248 dependent development questions × 3 arms = 744 completed slots. Python closure and actual OWL-RL 7.6.2 agree on 248 answer sets. Asserted-only lookup differs on 44 ancestry questions and 6 membership questions. Additional answer occurrences: 52 ancestors, 20 memberships (not distinct new entities).

`xml-posthoc.json` independently computes selected answers directly from original XML using BFS: 744 scorable, 744 equal. This does not certify all projection fields, arbitrary XML inputs, external truth, or natural-language interpretation. The scorer never repairs runtime answers. `xml-denominator-check.json` confirms 124 rows per source-arm and 248 query identities. Runtime source-tamper control preserves 744 slots: 372 source failures and 372 completions.

From repository root, using a new output directory:

```sh
uv run --locked python research/manufacturing-model-change-1/subtype-offline-001/runtime.py research/manufacturing-model-change-1/subtype-offline-001/config.json _workspace/new-subtype-run
uv run --locked python research/manufacturing-model-change-1/subtype-offline-001/check.py
uv run --locked python research/manufacturing-model-change-1/subtype-offline-001/xml-audit-code/check.py
```

The last command requires the retained `_workspace/manufacturing-continuation-20261107/subtype-xml/` scratch parent for its temporary test directories; create that directory if reproducing in a clean checkout. Saved runtime outputs are never overwritten. Original XML files retain MIT headers under `../projection-001/sources/` and pinned acquisition provenance there. Hashes record local integrity, not independent authentication.

Native independent reviews: `20261107T165123Z-manufacturing-subtype-projection-abb98b` and `20261107T165649Z-manufacturing-subtype-xml-audit-84ac6b`. Review packets omitted actual sources; observed execution and posthoc source checks are separate evidence. No live DB, paid LLM, performance or SHACL-specific efficacy measurement belongs to this offline run.
