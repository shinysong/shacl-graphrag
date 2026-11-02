# Vector retrieval refinement

This is a separate consumed-development axis. Historical results under
`research/graphrag-evidence-1` are preserved. No generator or paid API ran.

| Arm | Search projection | Eligible parents | Support /18 |
|---|---|---:|---:|
| Historical A | verbose JSON, midpoint splitting | 814 | 0 |
| A1 | source header/value fields, whole field boundaries | 814 | 5 |
| A2 | identical A1 vectors | 328 nodes | 5 |

A1/A2 recover the same five direct-setting cases (5/6); both score0/6 on each
of nominal-current and defect-label linking questions. Six bundle-absent cases
remain null separately. Historical C and matched E score7/18 on different case
mixes; neither was rerun using A1/A2 seeds, so this is not a controlled measure
of adding graph traversal to the improved baseline.

## Artifacts

- `protocol.md`: fixed interventions and limitations.
- `run-001/`: projections, float32 vectors, original full-evidence outputs,
  frozen source/code, runtime, ranking/packing, source-lineage audit receipts.
- `score-a1-001/`, `score-a2-001/`: unchanged offline scorer results, inputs/hashes.
- `comparison.json`: full denominator, task breakdown, paired changes, hashes.

The local vector index is `run-001/child-vectors.npy`, with row identity in
`run-001/children.json`. Exact NumPy cosine retrieval was retained: no vector DB
server, ANN engine or DB performance comparison. Model is the same pinned E5;
original query vectors were reused. A2 shares A1 embeddings and changes candidate
eligibility. This is post-observation engineering, not held-out validation.

Search representation omits repetitive provenance metadata, but full original
JSON is returned and charged to the unchanged4096E5/64000byte budget. No graph
expansion, target-value joining, query rewriting or reference enrichment occurs.
Original source attribution and license are retained in frozen/source-corpus-v1.json.

## Reproduction

Use a new output directory; never overwrite run-001. Reproduction is not needed
merely to confirm the saved result. Local model/tokenizer files are not bundled.

```bash
uv run --locked --offline --with numpy==2.3.4 --with onnxruntime==1.23.2 --with tokenizers==0.22.1 \
  python scripts/run_graphrag_vector_refinement.py \
  --output research/vector-refinement-1/run-NEW \
  --model _workspace/graphrag-cycle5/model/model.onnx \
  --tokenizer _workspace/graphrag-cycle3/sources/e5-tokenizer.json
```

The launch script configured an external960second timeout for run-001.
The execution receipt records only the command, exit status and elapsed time.
Run took57.76seconds, a single local observation; peak RSS was not recorded.
