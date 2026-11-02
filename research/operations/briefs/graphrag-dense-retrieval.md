# Independent A-only dense retrieval review
Allowed: scripts/graphrag_dense.py, scripts/run_graphrag_dense.py,
scripts/build_graphrag_search.py, scripts/graphrag_expand.py,
tests/test_graphrag_dense.py, research/graphrag-evidence-1/dense-retrieval-v1.md,
dense-retrieval-001/* and frozen/*, _workspace/graphrag-cycle6/* logs/audit/verification,
search-slices-001/manifest.json. No gold/references, other reviewer outputs or secrets.
No source edits, model loading/inference, network or new runs; write only own output.
Methods review is dispatched while corpus encoding may still be running: review
frozen design/code, mark unavailable results unverified; do not wait for results
or infer success. Implementation review will be dispatched after run/audit and
may inspect saved vectors/ranking/hash/budget calculations without model loading.
Declared scope: existing24 consumed questions, A retrieval component only; no
LLM answers or B/C/D/E comparison/relevance scoring. Real pinned CPU E5, shared1483
search slices/814parents. Top20children -> maxchild parent ->top8 ->whole-parent
packing <=4096 E5 accountingtokens and64000bytes; notgenerator tokens. No gold in
runtime. Full index failure emits all24failed envelopes; no partial index/retry.
Long-parent/fragment effects remain limitations. Probe tests shortest child alone
and padded to longest length; single diagnostic not universal invariance.
Registered checks=[]; manual36unit tests exit0. Runtime result and audit may be
pending for methods. Preserve distinction between observed artifacts and your
own execution; no memory/latency/generalization benchmarks.
