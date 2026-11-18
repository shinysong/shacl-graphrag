# Nonstandard commerce task coverage

This is an authored synthetic development fixture and an offline **tool-contract diagnostic**, not a model benchmark. It contains no real customer records. The questions, plans, preparation decisions and final response are authored controls. No provider is called and answer quality is not scored.

From the repository root, use a new output directory:

```bash
PYTHONPATH=. uv run --locked python scripts/workspace_task_coverage.py \
  --sources research/workspace-task-coverage-1/sources.json \
  --requests research/workspace-task-coverage-1/requests.json \
  --output _workspace/task-coverage-new-run
```

The runner refuses an existing output directory. It saves the original local draft, a separate reviewed control draft, source/request hashes, model-input packets, every checkpoint and failures. The downstream control explicitly supplies one relationship from the source dictionary. It does **not** demonstrate that the application generated that relationship or that a user created it through the UI.

| Probe | What is exercised | What is not established |
| --- | --- | --- |
| Known purchase | Exact comparison of purchase and parcel records using an approved relationship | Refund eligibility or relationship truth |
| Return ticket | Initial row lookup, then an intentionally unsupported dependent argument | Model selection quality or automatic multi-step traversal |
| Shipping threshold | Retrieval of a document with an unspecified discount basis | Automatic interpretation or a shipping decision |

An episode marked `completed` only means the wrapper reached its scripted final response. Inspect each evidence item's state: the dependent-argument probe retains a failed second tool. Do not count completed wrappers as correctly answered questions.

The current contract accepts literal string values, not an object referring to an earlier result. The authored invalid argument demonstrates this interface boundary; it is not an observed model mistake. The original local generator's missing candidate and the supplied downstream relationship must remain separate findings. These cases are consumed development material after inspection.
