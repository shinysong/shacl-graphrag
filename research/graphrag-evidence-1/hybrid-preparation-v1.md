# Frozen hybrid candidate preparation

The candidate stage runs under the original A NumPy2.3.4 runtime. It verifies bound input hashes, float32 shapes, finite unit vectors, unique IDs and original question order, then recomputes the original dense top20. A question with any ranking mismatch is retained as a failure. No score reconstruction from answers or reranker feedback is permitted.

```text
Bound A arrays/order -> float32/norm/hash checks
  -> original dense top20 identity check
  -> dense top10 + positive BM25 top10
  -> deduplicate without refill, <=20 children
  -> saved candidate IDs/scores -> later CPU reranker
```

Freezing candidate IDs before the Torch environment avoids changing dense rank semantics when NumPy differs. The deterministic BM25/union policy is the existing hybrid-candidates-001 contract. This is an implementation staging choice, not an additional source or an efficacy intervention. Original question/child texts remain unchanged.

No reranking, parent packing or QA is executed by this stage. A later B runner must verify the candidate output and exact original child/question hashes before passing pairs to GTE, and then apply the existing parent aggregation/packing budget. It must carry preparation failures forward into the full24-question denominator. Source absence is not classified by this stage.

Per-question rank/candidate failures remain rows; global input failures mark all24 planned questions failed in summary without fabricating successful rows. Preserve every failed output directory. Existing A results remain immutable. Unit checks cover NumPy boolean/float64/integer rejection, shape/finiteness/norm failures, wrong question order and one failed question followed by a successful one. No general retrieval or GraphRAG result follows from these checks.
