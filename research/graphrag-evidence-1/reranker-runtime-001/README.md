# CPU reranker runtime readiness

## Observed compatibility

The first isolated uv resolution used torch2.5.1+cpu from the CPU index and failed with exit1: that release had no matching ARM64 wheel at the selected index. The original stderr remains saved. After inspecting PyPI release metadata, a separate attempt used torch2.5.1 for ARM64. Its declared cp312 wheel is91,811,673bytes. Isolated uv resolution/import and tokenizer loading returned exit0; torch.version.cuda is null. The experiment repository dependencies were not changed.

Versions: torch2.5.1, transformers4.39.1, tokenizers0.15.2, numpy1.26.4, safetensors0.4.5. Full observed distribution versions are saved. This is an environment inventory, not a hash-locked dependency supply-chain audit or model inference result.

## Pinned implementation inspection

The retained Alibaba new-impl configuration and modeling files define a local PyTorch encoder and classification head. Modeling lines421-596 implement eager/SDPA attention with optional xformers; lines624-700 select attention and residual layers; lines785-797 pool the first token; lines1079-1167 apply dropout and the single-logit classifier. Configuration sets unpadding and memory-efficient attention false. Dropout must be disabled with eval. The token-type embedding code maps types tozero when type_vocab_size is1. The prospective smoke selects eager attention and CPU float32 explicitly.

No custom class or model weights were loaded in this cycle. Static inspection is not a complete security audit of imported dependencies. Use the exact local code files with retained notices, direct imports and local safetensors loading, avoiding remote auto-map resolution. Strict state-dictionary loading must reject missing/unexpected weights.

```text
Verified local code/config/tokenizer/weights
  -> direct local class construction, CPU float32
  -> strict weight loading, eval + inference_mode
  -> four fixed length-based pairs, no truncation
  -> finite logits + repeat checks + resource/failure record
```

The smoke plan is prospective. Model weight acquisition, loader implementation/review and the bounded smoke remain pending. Its length-selected inputs assess execution only, not retrieval relevance, graph benefit or full B performance. No gold, paid model calls, source repair or deployment is involved.

## Tokenizer input parity

Both tokenizer versions encoded all35,592 original question/child pairs. The ordered IDs, type IDs and attention-mask streams have identical SHA256; both maxima are560tokens. This checks the changed tokenizer runtime on this consumed input bundle, not model-output or relevance equivalence.
