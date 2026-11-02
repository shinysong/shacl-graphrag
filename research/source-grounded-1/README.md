# Source-grounded structural synthetic diagnostic

Read `protocol.json`, `licenses.json`, `DATA_LICENSES.txt` and per-source attribution files before reuse. These are **authored development fixtures**, not actual source rows, a learned simulator or held-out benchmark. Sources are not merged into one real factory. PENELOPE and BPI originals are observed data; Hinge original is already simulated.

`data/*/*.json` are runtime inputs. `data/evaluation.json` is generator-authored evaluation metadata, read only after runtime outputs are saved. Runtime input has no state label or expected answer. Source-absence/retrieval-omission input pairs are identical. Identifier/family variants do not establish independent statistical samples. Completeness is supplied metadata.

Run from repository root:

```bash
uv run --locked python -m scripts.source_grounded.run research/source-grounded-1/data _workspace/source-grounded-new-run
uv run --locked python -m unittest tests.test_source_grounded -q
```

Runner refuses an existing output directory. Generator `scripts/source_grounded/generate.py` authors fresh fixtures from structural motifs documented in `source-anchors.json`; it is **not** an automated raw-source parser. BPI times are invented ordinals and the query is a researcher policy. Source report personnel data and raw transaction rows are not redistributed. Source metadata snapshots remain in the ignored workspace; license proof fields and hashes are in licenses.json.

The output manifest, saved answers, summary, example RDF, shapes and validation reports support offline software checks. No model calls, OWL, vector retrieval, retrieval latency or external real-world truth measurement. The unqualified arm deliberately omits semantics and is not a retrieval-system baseline. Python and SHACL cover the same declared required fields/datatypes/reference classes only; arbitrary JSON ingestion, duplicate IDs and unknown classes are outside the runtime contract.
