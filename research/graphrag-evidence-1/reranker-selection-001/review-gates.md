# Independent review addendum

Both independent reviewers accepted provisional model selection and tokenizer-size reporting only. This addendum narrows the README statement that deterministic ordering is fixed: the current prospective configuration is **not execution-ready**.

Before any B execution, a new configuration and review must specify:

- Dense and lexical cutoff tie ordering, zero-score eligibility, BM25 corpus statistics, empty/nonfinite handling.
- Hash-bound A vectors, child text/prefixes, parent mapping and packing implementation; whether dense candidates are recomputed from vectors.
- Runtime package versions, loader options, complete pinned custom-code review, verified weight receipt, pair special-token policy and evaluation/inference mode.
- CPU smoke input count, resource/time limits, failure preservation and explicit retry policy.

The recorded tokenizer diagnostic covers 35,592 pairs with maximum 560 tokens and zero above 1,024. Reviewers inspected saved arithmetic/receipts; they did not independently reproduce tokenization. Weights and model inference remain unexecuted. B minus A would combine lexical retrieval and reranking, not isolate their effects. Shared final evidence caps do not imply equal compute cost.

Existing A results remain unchanged. This record does not authorize paid API calls, publication or deployment.
