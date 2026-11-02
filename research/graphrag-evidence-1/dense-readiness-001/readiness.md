# Dense retrieval readiness audit

## Observed boundary

Current locked project environment lacks torch, transformers, sentence-transformers,
ONNX Runtime, fastembed, tokenizers and huggingface_hub. NumPy is present. The
workspace research/ and _workspace/ search found no .onnx or .safetensors files;
this is not a host-wide cache inventory. No weights, embedding or reranking ran.
The temporary uv environment used tokenizers==0.22.1 only for length measurement;
project dependencies and uv.lock were not changed.

## Pinned candidates and source declarations

- intfloat/multilingual-e5-small revision614241f622f53c4eeff9890bdc4f31cfecc418b3:
  model card declares MIT and includes Korean in language metadata. Candidate only.
  Card uses query:/passage: prefixes, masked mean pooling and normalization;
  its example truncates at512 tokens. No inference or retrieval suitability proven.
- cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 revision1427fd652930e4ba29e8149678df786c240d8825:
  card declares Apache-2.0. Korean is not in the explicit language list; general
  multilingual claims are not Korean manufacturing relevance evidence. Not selected.
- License declarations are metadata observations, not a complete redistribution
  clearance or audit of upstream datasets. Retain notices before redistribution.

Sources: https://huggingface.co/intfloat/multilingual-e5-small and
https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 .
Pinned cards/API metadata, tokenizer and SHA256 receipts saved in sources/.

## Measured length diagnostic

Pinned E5 tokenizer JSON SHA256
0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39.
Loaded with tokenizers0.22.1; disabled truncation/padding; encoded each exact
corpus chunk text prefixed with "passage: ", including tokenizer special tokens.
No model weights, questions, scorer references or answer labels were used.
Across814chunks,298 exceed512tokens (298/328nodes,0/486edges).
Minimum223, upper median244, maximum1310. Full lengths in token-length-audit.json.
This diagnoses potential truncation, not measured retrieval error. CPU count2,
MemTotal16042368kB are inventory values, not feasibility or peak-memory results.

## Next bounded implementation

Preserve current source-corpus-v1.json and old parity run. Create a separately
versioned search projection with source chunk IDs and hashes. Either lossless
splitting with parent aggregation or compact field projection needs explicit
policy: equal searchable facts across all arms, retained full source evidence,
no silent truncation, deterministic IDs/order and source provenance. Distinguish
search text from selected full evidence and budget both. First count tokens and
check round-trip coverage; freeze before retrieval. CPU model execution requires
pinned weight/runtime manifests and resource smoke check, not metadata inference.
A/B/C/D/E remain unmeasured; no lexical score may stand in for dense embeddings.
