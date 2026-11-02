# CPU embedding execution diagnostic

```text
Pinned E5 weights + tokenizer +9 fixed inputs
  -> attempt001: model loaded, input-interface check failed
  -> inspected token_type_ids requirement
  -> attempt002:5 CPU batches ->9 x384 vectors
  -> shape / finite / unit-norm / repeat checks passed
```

One failed attempt and one manually corrected successful attempt are retained.
Eight distinct inputs (4 source slices,4 authored queries) plus one repeat were
encoded. All first8 vectors are distinct; repeat difference0.0. This checks local
execution, not meaning, retrieval ranking, A–E comparisons or Korean accuracy.

Attempt002 recorded3.512928seconds from inside the script and Linux process peak
RSS1,190,612KiB; loading0.612384seconds. These include runtime overhead and are
single-process observations, not throughput/latency or whole-host benchmarks.
No paid API, GPU, server, model conversion or quantization. No PyTorch parity test.

Runtime ONNX Runtime1.23.2/NumPy2.3.4/tokenizers0.22.1, explicit CPU provider.
Pinned model/hash and source download receipt are in summary/frozen. Weights stay
ignored under _workspace/graphrag-cycle5/model; tokenizer under cycle3/sources.
Original failure and its frozen script/protocol remain in cpu-smoke-001.
Future full-corpus retrieval and reranking have not run. This smoke does not
replace scorer isolation, equal evidence budgets or diverse source questions.
