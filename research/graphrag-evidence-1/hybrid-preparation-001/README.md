# Frozen hybrid candidates

The original A runtime (NumPy2.3.4) prepared candidates for all24 questions with0 preparation failures. All24 recomputed dense top20 ID sequences matched saved A; a separate saved-output audit also confirmed exact top10 scores/IDs. The dense top10 and positive BM25 top10 union contains453 question-child pairs, with14–20 candidates per question. Overlap slots were not refilled.

```text
Original A vectors + same question/child texts
  -> hash/dtype/norm/order checks
  -> saved A top20 agreement
  -> dense10 + BM25 up to10, union without refill
  -> 24 frozen candidate rows / 453 pairs
  -> reranker execution remains next
```

Fifteen unit cases passed before execution. Both independent reviews accepted this candidate-preparation scope only; the implementation reviewer checked ten manifest hashes. The actual preparation command exited0. A postrun coordinator audit checked all24 statuses, original questions, saved dense top10 scores, union arithmetic and all ten input/code hashes. No reviewer reran the tests or candidate experiment.

No model inference, final evidence packing, answer generation or relevance scoring occurred here. Candidate counts are workload observations, not retrieval quality. The current cohort is consumed development. The later B runner must verify this candidate-file SHA and original text bindings, preserve all24 planned questions, and use unchanged parent packing budgets. Do not interpret453 pairs as independent evaluation cases. The original A files remain unchanged.

Global hash-failure/CLI-finally behavior was inspected but not fault-injected in unit tests. No peak resource measurements or interruption durability were established. Private manifest paths describe the prepared local workspace; these artifacts alone are not a standalone model environment.
