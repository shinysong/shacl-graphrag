# Version-qualified model lookup diagnostic

Run from repository root with the locked uv environment. `runtime.py` imports the retained basic-pattern transport at `research/manufacturing-answer-trace-1/manufacturing-v2-20261107-001/runtime.py`, but instantiates only SQLStore and RDFStore. It does not start or contact Neo4j, Neptune or an LLM.

The source projection contains explicit stored references, not completed reverse references or inherited OPC UA semantics. References are serialized values followed by explicit target lookup. This is not native graph traversal benchmarking.

The saved run has 24 planned, emitted and completed rows; 12 adapter pairs agree. The separate `score_xml.py` reads the two original XML files after execution. It verifies selected returned fields and the recorded raw-source hashes, not the entire intermediate projection. No reference values are supplied back to runtime. `denominator-check.json` separately checks the saved matrix; the scorer itself only iterates over existing rows.

Rebuild into a NEW output directory (the runtime rejects an existing directory):

```bash
uv run --locked python research/manufacturing-model-change-1/version-query-offline-001/runtime.py research/manufacturing-model-change-1/projection-001/snapshot-0.json research/manufacturing-model-change-1/projection-001/snapshot-1.json _workspace/model-version-reproduction
```

Software controls, using normal Python without `-O`:

```bash
uv run --locked python research/manufacturing-model-change-1/version-query-offline-001/check.py
uv run --locked python research/manufacturing-model-change-1/version-query-offline-001/check_score.py
```

The controls expect the repository's retained source artifacts and the existing `_workspace/manufacturing-continuation-20261107` parent directory. They are not a standalone package. The namespace control checks an absent namespace, not two defined colliding numeric identifiers. XML/scorer malformed-input support is bounded; filesystem failures can prevent durable output. All results are consumed development diagnostics, not fresh held-out or operational plant measurements.
