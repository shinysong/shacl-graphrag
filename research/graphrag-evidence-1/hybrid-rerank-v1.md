# Frozen-candidate CPU reranking

The next bounded execution scores the existing453 question-child pairs, unchanged, with the pinned local GTE model and runtime established by the smoke. It reads24 fixed original questions and shared child text, not reference answers. Dense scores are not recomputed in the Torch environment. Existing candidate hashes, source IDs and question text must match before inference.

```text
Frozen24 candidate rows /453 pairs + bound original text
 -> local CPU GTE, one pair per forward pass
 -> raw finite scalar logit per child
 -> per-question score records and failure states
 -> separate original-runtime parent packing (later)
```

Use CPUfloat32/eager/eval/inference_mode,2threads1interop,8GiB address-space cap,1024pair-token cap without truncation. Raw logits are ranking scores, not calibrated probabilities. No threshold or answer correction is introduced. Run once, with850second between-pair stop and external900second timeout/5second kill grace. Parent records exact argv/stdout/stderr/status independently; no automatic retry. A partial result or missing summary cannot count as full success. Every planned question remains in the24-question denominator; failed preparation rows stay failed and unprocessed/partial questions are failures on forced termination. Partial scores must not be used for successful packing.

This stage does not select final evidence or run a generator/checker. Later packing uses max-child parent scores, deterministic IDs and the same final A budgets in the original accounting-tokenizer runtime. B minus A combines lexical retrieval and reranking; it is not an isolated reranker effect. All current inputs are consumed development;453pairs are workload, not independent evaluation cases.
