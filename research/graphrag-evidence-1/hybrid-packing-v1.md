# Original-budget hybrid evidence packing

This stage uses saved GTE scores without new inference or source lookup. It requires exact per-question candidate/score alignment; partial, duplicate, nonfinite and failed score sets cannot produce successful evidence. It invokes the unchanged A rank_pack implementation on only the frozen candidate children. All candidates fit the existing maximum20child budget.

```text
Frozen candidate IDs + complete saved logits
 -> max child score per parent, ties parent ID
 -> first8 parents
 -> whole-parent packing, skip oversized and continue
 -> <=4096 E5 accounting tokens and64000 UTF8 bytes
 -> B evidence envelope and selected-only downstream seeds
```

Use the original pinned E5 tokenizer bytes with tokenizers0.22.1, padding/truncation disabled. Evidence token count for an unselected generator remains null; accounting tokens are not generator tokens. There is no content truncation or gold-guided recovery. Per-question exceptions remain failures; global setup errors mark24planned failures in summary.

B seed_chunk_ids explicitly names selected evidence only. The historical A envelope used prepacking parents for that metadata field; its actual selected evidence remains unchanged. Future C/E must start from identical selected B evidence, not discarded parents. This field clarification does not change A/B evidence packing or introduce a new source.

Same evidence caps do not equalize runtime costs. B minus A combines keyword candidates and reranking; final retrieval envelopes are not generated answers. The24questions remain consumed development. Offline support scoring is a separate later stage and reference answers are unavailable to this runner.
