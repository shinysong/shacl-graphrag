# Refined hybrid candidate preparation

User approved sequential improved hybrid, relation backend and SHACL work. This cycle only freezes candidates from improved A1; no reranker, paid API, database or generation runs. Preserve every old artifact. This is consumed development, not fresh evaluation.

Mechanism: use the same 814 source-field children and E5 vectors as A1, with original 24 query vectors. Add unchanged BM25 positive top10 to dense top10, sorted union, no overlap refill. Existing prepare function verifies dense top20 identity with saved A1. No graph expansion, gold or question rewriting. Candidate pairs are not scored answers.

Implementation: scripts/prepare_refined_hybrid.py wraps existing prepare_graphrag_hybrid.prepare and graphrag_candidates.candidates, adding fixed814/24 count and ID checks, question field guard, hashes of every input and code dependency, pinned numpy2.3.4, immutable output directory, frozen input copies and failure summary. Runtime paths: vector-refinement-1/run-001 children.json, child-vectors.npy,A1.jsonl; original dense-retrieval-001/query-vectors.npy and frozen/development-questions.json. Manifest made before execution. Tests reuse candidate and preparation tests. No historical output edited.

Next cycles separately review refined reranking/packing, matched relation expansion and actual Neo4j parity, external pySHACL plus matchedPython, Neptune adapter. AWS creation waits for region/account/cost bound; paid API stop persists. Common generation budget and fresh question diversity remain unresolved; no QA result claims.
