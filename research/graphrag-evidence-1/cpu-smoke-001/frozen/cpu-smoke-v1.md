# CPU dense embedding smoke v1

Purpose: verify execution of pinned E5 ONNX weights on this host, not retrieval
or generation quality. CPUExecutionProvider only, two intra-op threads, one
inter-op thread, sequential execution, batches of at most2, no remote inference.

Inputs: four distinct search children chosen deterministically by first, last,
minimum token count and maximum token count (first tie); if collision, append
next source-order children until four. Add four authored queries (two Korean,
two English), without answers or reference labels. Repeat first passage at end.
Input receipt is frozen before inference. Nine encodings total, five batches.
No search scores, candidate judgments or question-answer metrics are computed.

Pinned runtime: onnxruntime1.23.2, tokenizers0.22.1, numpy2.3.4 via uv temporary
environment. Model revision614241f622f53c4eeff9890bdc4f31cfecc418b3,
onnx/model.onnx SHA256ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665.
Tokenizer SHA2560b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39.
No quantization/export or PyTorch parity claim. Model card declares MIT; retain
source metadata and existing notices. No weight redistribution in public artifacts.

Tokenization disables truncation; reject >512tokens. Right-pad each batch with
actual tokenizer pad ID. Mean-pool last_hidden_state over attention_mask,
including unmasked special tokens, then L2-normalize as the model-card example.
Require finite nine-by384 outputs, unit norms atol1e-5, and first/repeated vector
agreement atol1e-5, rtol0. Preserve failures, no automatic retries.

Record model/load and batch elapsed wall time and Linux process ru_maxrss KiB.
These are one process observations (including tokenizer, model and libraries),
not representative latency, throughput or whole-host resource benchmarks.
Record all versions, input/code/protocol/source/model/tokenizer hashes, runtime
input/output metadata, embeddings and check results. Loading a model successfully
does not establish task relevance, Korean manufacturing efficacy or A–E results.
