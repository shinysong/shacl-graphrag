# Lossless search splitting v1

Scope: offline preprocessing only. No embeddings, ranking efficacy or LLM run.
Input is the unchanged source-corpus-v1.json and pinned E5 tokenizer JSON.
All arms will receive the same search children; original evidence remains intact.

## Representation and bounds

For each original chunk, preserve its exact Unicode string and SHA256. Count the
complete search string `passage: parent=<chunk_id>\n<slice>` including special
 tokens. If over512, recursively bisect the original string at its Unicode
character midpoint; process left then right. No overlap, deletion, normalization,
byte decoding or token-ID decoding. Store start/end character offsets, parent ID,
parent hash, ordinal, original slice and exact search string with measured count.
Reject non-string/empty/duplicate IDs and non-string/empty text, unsplittable
single-character overflow, tokenizer hash/version mismatch and invalid budget.
No runtime question, gold or ontology enrichment enters preprocessing.

Concatenating slices in ordinal order must reproduce each original text exactly;
all814 parents and their order are retained. A fragment need not be standalone
JSON or a coherent semantic unit. This is a reproducible lossless baseline, not a
claim of optimal segmentation or preserved model comprehension. Prefix context
carries only an existing parent ID. Long parents create more search opportunities.

## Parent aggregation contract

Future retrievers rank children. For each parent score=max(child scores), ties
by parent ID ascending. Reject duplicate/unknown child IDs and nonfinite scores.
Store contributing child IDs ordered by descending score then child ID. No score
means no candidate: do not recover a missing parent using references or gold.
This aggregation applies identically to each relevant retrieval arm; long-parent
opportunity bias must be reported. This helper is not a retrieval experiment.

Selecting a parent permits retrieval of its original full evidence from the
shared corpus before packing; all arms have identical access and must charge
full parent evidence to the same future generator-token budget. No splitting
policy here fixes that future budget or retrieval top-k. D receives C's already
packed evidence only, with no parent/source lookup of its own. Retrieval losses
and absent source facts remain separate. Freeze actual generator tokenizer,
reranker input policy and budget/packing separately before model execution.

## Reproduction

Use `uv run --offline --with tokenizers==0.22.1 python scripts/build_graphrag_search.py`
with --source, --tokenizer and --output. Output directory must not exist.
Tokenizer SHA256 is fixed to
0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39.
Keep original corpus and old runs unchanged. Build writes manifest and children
only after full construction; failed attempts retain error receipts once the
exclusive output directory is created. No model weights/network calls required.
