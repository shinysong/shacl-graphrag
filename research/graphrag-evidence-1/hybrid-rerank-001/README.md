# Frozen-candidate reranking result

The local pinned GTE model scored all453 frozen question-child pairs across24 consumed development questions. All24 questions completed with0 failed or unverified questions. The parent exit code was0 with no timeout. The score log matches the saved per-question results exactly; every expected child ID appears in its original candidate order. All scores are finite; the largest encoded pair was558tokens, within the1024cap. Ten input/code hash checks passed after execution, with no inference rerun.

```text
24 frozen candidate rows ->453 local GTE forward passes
 ->24 complete score records,0 incomplete questions
 ->next: max-child parent ranking and original-budget packing
 ->later: independent source-support evaluation
```

CPUfloat32/eager/eval/inference_mode and2threads/1interop were verified in the child. The8GiB address-space limit was active. Child elapsed437.281725seconds, parent elapsed437.964662seconds, peak process RSS2,359,744KiB. These are single-run process observations, not comparative latency, throughput or resource benchmarks. No paid model API calls were made.

Two independent reviews accepted the bounded execution before it ran. They inspected the code/design and did not independently reproduce the inference. The coordinator audited saved IDs, finite values, token caps, row counts, exact progress correspondence and input/code hashes afterward. External timeout and error capture were configured, but forced termination/failure paths were not fault-injected in this successful run.

No final evidence packing, QA answer, validation report or support score has been produced by this stage. Raw logits are uncalibrated ranking scores, not truth probabilities. B minus A combines keyword retrieval and reranking; no isolated effect or graph advantage follows from completion.453pairs are workload, not independent cases. Original A results and candidate inputs remain unchanged.

Next use original-runtime E5 token accounting and the existing max-child parent ranking/top8/4096token/64000byte whole-parent packing. Preserve every failed question if future runs fail; incomplete scores cannot be treated as successful evidence. Workspace-dependent model inputs remain private, with hashes and invocation retained here.
