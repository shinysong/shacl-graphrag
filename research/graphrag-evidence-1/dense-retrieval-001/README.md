# Dense-only retrieval component run

```text
814 preserved source chunks ->1483 pinned search slices
                                   | CPU E5 embeddings
24 consumed development questions -+-> dot products
                                      -> top20 child hits
                                      -> max per parent, top8 parents
                                      -> whole-parent budget packing
                                      ->24 saved evidence envelopes
```

Actual execution:1,483 source-child vectors and24 query vectors,384dimensions.
All24 retrieval envelopes completed;0 execution failures. This is not24correct
answers or24relevant evidence sets. No LLM generation, reranker, relation expansion,
SHACL, B/C/D/E comparisons or reference-answer scoring occurred. This is A's
retrieval component, not a full vector-RAG answer experiment.

Coordinator checks:36 unit tests passed; full run exit0; independent saved-vector
recalculation of top20 child ranks, max-score top8 parents, budget skips, whole
selected payloads, hashes and accounting counts exit0. Methods review covers
frozen design/code while execution was running; implementation review inspects
completed artifacts. Neither review is a second model run.

Budgets are4,096 E5 accounting units and64,000UTF8bytes per canonical selected
array. evidence_tokens=null because no generator tokenizer is specified. Long
parents can create more search opportunities, and character fragments may split
meaning. Existing questions have limited source/answer diversity and are consumed
development. No benchmark, generalization, factual truth or GraphRAG advantage.

One padding probe compared a243token child alone and padded to512; max vector
difference3.72529e-8 met1e-5 tolerance. It is not universal padding invariance.
Runtime395.657639seconds and process peakRSS1,198,664KiB describe this process only,
not representative throughput or host-capacity limits. Paid/generation calls0.

## Reproduction artifacts

manifest.json and frozen/ retain inputs/code/protocol; child-vectors.npy and
query-vectors.npy retain actual normalized embeddings; progress.jsonl preserves
all completed batches. retrieval.jsonl records top hits, parents, budget skips,
selected source text, provenance hashes and accounting costs. Source license and
attribution are preserved in frozen/source-corpus-v1.json. Model weights remain
ignored under _workspace/graphrag-cycle5/model, with original download receipt.
See dense-retrieval-v1.md for the frozen configuration and failure policy.

Next: offline source-bound support scorer, keeping gold away from runtime; then
same-information comparison arms and separately scoped diverse real questions.

## Observed selection composition

Each query selected8 parents, with0 budget skips. All192 selection occurrences
were edge chunks (93 distinct chunk IDs); no node chunk was selected. This
shows selection composition under this fixed representation/model/configuration,
not relevance or answer correctness. Preserve this outcome; do not retune this
run or repair it with gold. Next score source-bound support offline before any
new, separately versioned retrieval intervention.
