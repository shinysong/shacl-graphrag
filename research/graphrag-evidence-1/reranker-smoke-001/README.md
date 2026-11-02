# Local CPU reranker smoke

## Observed execution

Pinned GTE multilingual reranker weights were acquired with their expected611,934,706byte size and SHA256. The local loader used unchanged pinned custom code with retained notices, strict safetensors state loading, CPU float32, eager attention, eval and inference_mode. It made no model API calls or source lookups.

The first fixed development question was paired with its shortest and longest child inputs by token count, ties by child ID. Each pair was repeated once: two unique pairs, four forward passes. All logits were finite scalars and both repeat differences were0.0. Selected IDs, token counts and raw logits are saved. Repeated agreement within one process is not evidence of semantic correctness or cross-process determinism.

```text
Hash-checked local artifacts -> strict CPU model load
  -> first question + shortest/longest child
  -> repeat both once
  -> four finite logits, two exact repeat matches
```

The parent captured stdout/stderr/exit independently of the child. Exit0, no timeout. Child elapsed17.750499seconds, parent elapsed18.462483seconds, peak process RSS2,392,056KiB. These are observations from one smoke, not latency/throughput or host-capacity benchmarks. An8GiB address-space ceiling was active; it is distinct from resident-memory usage. External timeout was180seconds with5second kill grace.

## Scope and next execution

This run establishes that these two inputs execute under the pinned local configuration. No complete B retrieval, QA answer, relevance score, SHACL check or graph advantage was measured. No candidate policy or original A result was changed. Full B still requires a runner that enforces shared input/vector bindings, NumPy dtype checks, candidate selection, existing parent packing, per-question failure accounting and its own resource bounds/review.

The original prospective runtime plan remains unchanged as history. Manifest dependencies under _workspace are private local artifacts; the model weights are not included here. The saved command is intended for the documented prepared host with cached packages; the runtime inventory is not a complete hash-locked wheel environment. Independent reviews preceded execution and inspected design/code; saved-output arithmetic and hashes were audited afterward by the coordinator without rerunning inference.
