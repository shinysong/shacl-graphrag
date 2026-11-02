# Independent CPU smoke review
Read only scripts/run_graphrag_cpu_smoke.py, research/graphrag-evidence-1/cpu-smoke-v1.md,
cpu-smoke-v2.md, cpu-smoke-001/* and frozen/*, cpu-smoke-002/* and frozen/*,
search-slices-001/children.json, _workspace/graphrag-cycle5/{verification.json,
model-receipt.json,model-io-inspection.json,onnx-tree.json,runtime-install.log,
smoke.log,smoke-002.log,smoke-inputs.json}. Do not load model weights or execute
inference/downloads. No other reviews, gold/references, secrets or source edits.
Write only own designated output. Model card from cycle3 may be read for pooling
recipe; license is declaration only. Methods: claims/failure denominator/fairness
limits. Implementation: artifact hashes/vector checks and masking/input mapping,
repeat tolerance. Evidence is two attempts: first failed before inference after
loading, explicit inspected correction passed second (9encodings5batches).
No automatic retries, retrieval efficacy/LLM/SHACL/API claims. Manual smoke001exit1,
smoke002exit0, saved vector/hash audit0. Registered checks=[]; independent reviewer
need not reproduce execution. Single-process ru_maxrss not host capacity benchmark.
