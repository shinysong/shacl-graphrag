# Dense-only development retrieval v1

Scope: A retrieval component only on the existing24 consumed questions. No LLM,
B/C/D/E execution, answer score or general benchmark. No reference/scorer file
is a runtime input. Facts remain the same814parents/1483slices for future arms.

## Frozen ranking and packing

Use pinned E5 ONNX/model/tokenizer/runtime from cpu-smoke-v2, masked mean pooling
with float64 accumulation then normalized float32 outputs. CPU2threads, batch2,
fixed source order. Encode passage search_text unchanged, queries as `query: `
plus original question; no query rewriting. Reject >512, never truncate.
Require vectors finite/unit length and padding probe agreement atol1e-5,rtol0:
encode the shortest source child alone and beside the longest, then compare.

Dot product of normalized float32 vectors gives dense similarity. Score all1483
children, sort descending score then child ID. Take20 child hits. Use frozen
max-child parent aggregation, take first8 parents, no relation expansion or
keyword scoring. Pack whole parent chunks in ranked order, skip a parent if
adding it would exceed4096 E5-token accounting units or64000 UTF8bytes for the
canonical JSON selected-chunk array. Continue to later candidates; preserve all
skipped IDs. No partial parent. E5 here is only a fixed accounting tokenizer,
NOT an unspecified generator tokenizer/context budget. `evidence_tokens` stays
null; accounting tokens are named separately. Encode full arrays without the
512limit solely for counting, not model inference. Empty selection is budget_error.

## Execution and provenance

Freeze inputs, protocol, code and hashes before run. Exclusive output directory;
save every batch progress and completed vectors. At most900seconds checked between
batches; this is not a hard per-kernel timeout. On any corpus/query embedding failure,
mark all24 questions retrieval_error and preserve artifacts; do not use a partial
index. Per-question ranking/packing failure produces its own error envelope.
No automatic retry. Save full vector matrices, IDs, top20children, top8parents,
selected full evidence, hash, budgets, timings and process peakRSS.
Question objects must contain only question_id/question; reject unexpected fields.
This software boundary is not an OS sandbox; no gold, answers or expected support
may guide runtime. Source and existing slices stay unchanged.

A successful retrieval means software executed, not correct evidence. Do not
interpret selected irrelevant chunks for bundle-absent questions as hallucinated
answers. Offline support scoring is separate and not part of this run. Same
packing and access rules must be used by future comparison arms, with C/D exact
selected-evidence identity. No claims about full vectorRAG answer performance.
