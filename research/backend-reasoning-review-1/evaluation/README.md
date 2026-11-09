# Offline replay of saved development evidence

From the repository root:

```bash
uv run --locked python scripts/check_backend_evidence.py --output _workspace/backend-audit-new
```

The output directory must not already exist. This checks the 809 files listed in
`artifact-manifest.json`, full planned/observed slot coverage and saved cleanup
receipts, then reproduces ten archived evaluations in temporary copies. Original
outputs are not overwritten. There is no database connection or model invocation.
The manifest is a local snapshot, not authenticated proof of remote execution.

`score_*.py` are the original posthoc scorers, copied unchanged from the execution
workspace. They use consumed, manually declared evaluator references. They are
not runtime validators and must never be used to repair experiment outputs.
The advisory scorers also use the saved update evaluation, independently replayed
first. Passing means the archived scoring is reproducible; it does not establish
external truth, independent questions, LLM efficacy, or engine performance.

The imported RDF terms that changed, stale-output controls and unsupported Q7
contracts remain in the denominator. Missing or duplicate saved slots fail the
audit. The individual scorers can be run on a disposable copy of a run directory;
they write `evaluation.json` in the supplied directory, so never point them at an
original archive merely to repeat a check.

## Later input-boundary follow-ups

`metadata-boundaries-001` preserves 34 original checker attempts, including four
Python exceptions and one completed LF-suffix disagreement. `advisory-strict-001`
is a separate, post-counterexample version: 370 slots, 362 completed and eight
shared input rejections. Its scorer can be run on a **disposable copy**:

```bash
uv run --locked python -m research.backend-reasoning-review-1.evaluation.score_strict _workspace/strict-run-copy
```

These follow-ups are outside the initial ten-run replay and 809-file manifest.
`artifact-manifest-supplement.json` freezes their files and presentation sources;
it supplies integrity hashes, not an additional independent scoring validation.
The HTML explorer uses v1 saved reports, not substituted v2 results. Its builder
checks paired status/codes; separate saved-data checks verified all displayed
metadata fields for the current 480 pairs. Do not infer that this narrower builder
gate validates arbitrary future inputs.

## Query-conditioned follow-up

`advisory-query-scope-001` contains 640 additional checker slots over the same160
outputs. The declared query dependencies and wrong-query control are supplied
operational metadata, not learned question interpretation or source completeness.
`dependency-finite-001` separately records all12,288 finite software-model states;
this count is unrelated to earlier12,288-output studies. Re-enumerate offline in a
new ignored directory with:

```bash
uv run --locked python -m scripts.check_query_dependency --output _workspace/dependency-finite-new
```

The initial809-file manifest remains valid. The226-file supplemental snapshot was
captured before the query follow-up and report/presentation additions; its exact
files were archived privately under `snapshot-0956` before changes. The final
manifest is the current supplemental integrity snapshot. Neither supplemental
manifest is additional independent validation of scoring. The final presentation
builder checks all displayed paired fields, origin and original output; an
additional check verified unique report/evaluation keys for the current data.
