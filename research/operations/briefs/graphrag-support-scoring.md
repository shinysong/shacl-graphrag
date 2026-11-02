# Independent offline support-scoring review
Allowed: scripts/score_graphrag_support.py, tests/test_graphrag_support.py,
research/graphrag-evidence-1/support-scoring-v1.md, offline-interface-v1.md,
support-score-001/* and frozen/*, _workspace/graphrag-cycle7/tests.log,
scoring.log,verification.json. Frozen references are the already-consumed24-case
offline scorer definitions, explicitly allowed for THIS scorer review only;
do not expose them to runtime tools, retrievers or any generator. No heldout gold,
secrets, other reviewer outputs, model calls, edits or network. Ownoutput only.
Methods: support versus answers/truth, original policy vs post-observation scorer,
full18present/6absent denominator, link equivalence and scope claims.
Implementation: selected evidence/source identity/hash, per-case support/binding,
missing/failing/invalid results and reference errors, actual24saved outputs and
hashes. Manual44tests/scorer/audit exit0; registered checks=[]. No new model run.
Original A result preserved;0/18complete support,6absent null. No general vectorRAG
or graph-superiority inference. Both reviewers must state what not verified.
