# Actionable evidence development diagnostic

`protocol.json` and `implementation-contract.md` are the frozen **pre-run** design,
not a live status flag. Protocol0.1 is retained under `archive/`. The implementation
contract0.2 is authoritative for the actual bounded runtime and scoring semantics.
Its explicit synthetic-authorship statement qualifies the earlier protocol's
"reference evidence acquired independently of gold" wording: both source reference
and external expectation are authored here; only their runtime/scorer channels are
separate. No independent real-world correction truth was acquired.

## Data separation

- `source/`: descriptive extraction of243 actual PENELOPE annotation rows. Original
  codebooks, cell provenance, hashes, formulas, attribution and acquisition limits
  are retained. No confirmed correction truth or physical intervention policy.
- `fixtures/runtime/`:32 new authored development inputs, not sampled source rows.
- `fixtures/scorer.json`: separate authored expectation, never loaded by the
  runtime child process. Missing-source/projection-omission pairs expose identical
  runtime bytes. All cases are consumed development after this run.
- `runs/smoke-001`:12 executions on two of those same cases, not additional trials.
- `runs/run-001`:192paired rows (32cases×3candidate scopes×2postcheck policies).
  Failures, stdout/stderr and complete outputs are retained. `frozen-inputs.zip`
  archives exact hashed source/fixtures/lock/design bytes for reproduction.

The runner hashes files (including scorer bytes) for provenance but does not
interpret scorer contents. The separate evaluator loads labels only after complete
outputs are saved. Source snapshots use authored synthetic locators. Raw real
workbooks/PDFs remain outside this package; source extraction retains CC BY4.0
attribution in its metadata.

## Observed scope

The full run completed192rows without runtime errors. Python/SHACL-AF full candidate
evidence, patches, reports and dispositions match32/32 cases under each postcheck
condition. This is policy/implementation parity, not graph-engine superiority.
Postchecks remove four dependency-violating proposals in each full-relation arm
but retain four formally conforming externally false proposals. These are authored
controls, not estimated natural failure rates. The direct arm intentionally stops
after one edge; it is not a competitive keyword/vector/LLM baseline.

Both postcheck conditions compute before/after validation; one merely records it,
the other uses it to veto proposals. Both Python and SHACL validators run for
diagnostic agreement. Thus neither these arms nor elapsed row times isolate engine
latency. No physical process change, paid API call or source correction occurred.

Canonical Korean explanation and exact aggregate/per-case records:
`docs/experiments/actionable-evidence-study.md` and
`docs/experiments/records/20261029-actionable-evidence.json`.
