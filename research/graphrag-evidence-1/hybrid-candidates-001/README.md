# Pre-reranker candidate contract

This cycle specifies and implements candidate selection only. No actual B reranking, final evidence packing or model inference was executed. The implementation receives shared child text, the original question and dense scores; it has no reference-answer or source lookup interface.

```text
Bound A child/query vectors -> recomputed dense top10 ----+
Same child text + question -> positive BM25 top10 -------+-> unique child IDs
                                                           -> <=20 candidates
                                                           -> future reranker
```

The contract resolves dense/lexical cutoff ties, lexical zero-score eligibility, corpus statistics, empty inputs and nonfinite scores. Overlapping slots remain unfilled. Source text includes its original prefix; character slicing and length differences remain potential retrieval biases. Query terms are unique; Korean text uses the stated Unicode regex, not morphological analysis.

Input bindings retain exact A vector/order/source identities and the existing packing implementation. They are a manifest, not a runtime loader: a future runner must verify every hash, array shape/order and unit-vector assumptions before calculating scores. No fixed-source candidate output or relevance outcome was generated in this cycle.

Nine local unit cases passed, including a hand-calculated BM25 value, Unicode tokens, duplicate query terms, tie permutation invariance, disjoint/overlap unions, empty lexical matches and invalid inputs. The first test command failed collection because the scripts import path was missing; after adding the repository's existing test import convention, nine passed. This software check is not a benchmark.

The previous prospective model config remains preserved. This contract supersedes only its candidate-selection fields. The full B gate remains closed pending pinned custom-code/runtime review and a bounded CPU smoke. B minus A combines lexical retrieval and reranking; shared final caps do not establish equal compute cost. Existing A outcomes remain unchanged; consumed development only.
