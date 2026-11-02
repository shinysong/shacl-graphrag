# Source-field vector retrieval refinement v1

New user-authorized axis dated 2026-11-02. Preserve historical A/B/C/D/E and all
failures. Existing source and 24 questions are consumed development. This is a
post-observation engineering diagnostic, not held-out confirmation or a vector
DB engine benchmark. No new paid API calls, generator, graph traversal or rerank.

## Intervention and comparators

A1 replaces verbose JSON search strings and midpoint splitting with source field
lines. Each child repeats workbook/sheet/Excel row identity. Original column
headers label values; all header rows for a column are joined in source order.
Cells and formula/cached values are retained as search fields; existing node
reference targets are included. Edge fields retain subject/relation/target/code
and source/target locations. No new Korean glossary, inferred value, question
rewrite, joining target values or gold enters the projection. Archive paths,
hashes and repetitive JSON metadata are excluded from search text but preserved
in the original returned evidence. Search text is intentionally not byte-lossless.

Pack whole field lines greedily to <=512 tokens including passage prefix and
special tokens, repeating identity context, no overlap between field lines.
Fail rather than truncate any oversized atomic line. This combines representation
and segmentation changes; it does not isolate their individual effects.

A2 uses the exact A1 embeddings but restricts eligible candidates to the328 node
parents. The486 explicit edge parents cannot be retrieved; node dictionary_refs
remain searchable. This changes candidate eligibility and duplicated relationship
representation, not just vector formatting. Do not claim identical searchable
bytes/facts or independent model runs for A1/A2. A2 is informed by observed old
edge dominance and the consumed development support contract; label that bias.

## Fixed execution and evidence budget

Same pinned multilingual-E5-small ONNX, tokenizers0.22.1, numpy2.3.4,
onnxruntime1.23.2, CPU2threads, batch2, mean pooling/L2 normalization as A.
Reuse exact original24 query vectors and questions after hash binding.
Persist field projection, parent/source hashes, full384dim vectors and ordered
IDs as a local exact vector index. Use exhaustive NumPy cosine search, not a new
DB service. The requested improvement is tested in representation/selection;
no DB product advantage is being tested.

Same old rank_pack: all eligible children scored, top20child hits, max-child
parent aggregation, first8parents, whole original JSON evidence,4096E5-accounting
tokens and64000bytes, skip oversized parent and continue, no refill beyond8.
E5 accounting is not generator context accounting. No compressed-evidence budget
advantage; return exact historical source chunks. Store all24 rows per arm with
failures. Exclusive output directories,900seconds between batches plus external
hard timeout, preserve partial artifacts and failures, no automatic retry.

## Evaluation and reporting

Before execution independent native methods and implementation reviews; then
projection unit tests and one bounded run. Freeze code/protocol/input hashes.
Only afterward apply unchanged score_graphrag_support.py to saved outputs, same
18source-present denominator and6bundle-absent null cases. Original extraction
hash and derived corpus hash are separate namespaces; bind both. Save selected
node/edge counts, missing support, budget skips and paired changes versus old A,
B,C,E; these historical arms are context, not controlled A1 graph ablations.
No answer accuracy, factual truth, unnecessary-abstention or graph superiority
claim. Negative or mixed results are retained without iterative tuning on gold.
