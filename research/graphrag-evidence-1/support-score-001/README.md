# Offline source-bound support diagnostic

```text
Saved A retrieval outputs (unchanged) + original offline references
       | exact-source and evidence-hash checks
       v
24 valid saved evidence envelopes
       | frozen support policy: annotation node [+ bound dictionary node]
       +--18 source-present questions ->0 complete support
       +--6 bundle-absent version questions ->not scored as support/accuracy
```

| Source-present task | Questions | Complete support |
|---|---:|---:|
| Recorded setting |6|0|
| Nominal current |6|0|
| Defect label |6|0|

All selected chunks were edges; no required source node was selected. Edge-only
evidence does not satisfy the predeclared endpoint/source-record contract. For
example, dev-002 requires PP3:2 and PP3:welding_settings_code:1 with the matching
embedded reference. The standalone edge is optional when both nodes are present;
the edge alone is insufficient. This is not proof that all useful relation
information was absent or that a generator would give18 wrong answers.

The separate6 version questions have no answer in the supplied bundle according
to the original references. Their support and answer-accuracy fields remain null.
No generator ran, so hallucinations, abstentions or unnecessary withholding were
not measured. Scorer validates source binding, not external factual truth.

This implementation follows the equivalent-support policy fixed before retrieval,
but was written after observing edge-only selection. It is not a blinded or held-
out benchmark. The24 consumed questions have limited diversity. Do not generalize
0/18 to vectorRAG broadly. Source records, references and retrieval outputs are
unchanged; no gold-guided retrieval retry, data repair or answer repair occurred.

Manual checks:44 unit tests passed, scorer exit0, independent arithmetic and
input/frozen-hash audit exit0. Missing/failed/malformed output handling is covered
by separate software fixtures, not additional experimental cases. Frozen source,
references, retrieved evidence, scorer and policy are retained for offline audit.
No model calls, B/C/D/E comparisons, SHACL or publication in this cycle.
