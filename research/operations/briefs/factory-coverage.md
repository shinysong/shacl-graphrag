# Explicit selected-evidence review targets

Scope: implement and test a versioned checker projection, not a paid efficacy study.
Current source changes are apps/factory_lab/coverage.py, branching.py, agent.py,
server.py, static/app.js; tests/test_factory_branching.py and
scripts/replay_factory_coverage.py. Reviewers may read these exact files, existing
review.py, evidence.py, graph.py, rdf_graph.py, and public coverage-001/replay.json
as needed. Do not read other reviewers, secrets, evaluation gold, or raw model calls.

Problem: legacy review seeds candidates only from replacement_candidates results;
selected inspect_entity paths may contain enough evidence but produce zero checker
targets. Mechanism: LLM may call declare_review_targets with explicit order/machine
pairs and exact user quotes. This does no graph lookup and is not evidence. Pair
semantics/completeness remain unverified. Tool calls consume the existing 12-call
cap; no new automatic API request or retry. Optional flag preserves historical
programmatic runners; the next web server startup enables it.

New frozen bundles carry factory-review-coverage-v1 and explicit declarations.
Unmarked bundles retain their old exact review path. New projection accepts only
matching version/hash/date evidence; uses explicit pairs or replacement query pairs,
never arbitrary cross-products. Missing positive capability relation is unassessed,
not a false capability claim. Conflicting selected facts/missing fields remain
unassessed. Both Python and SHACL consume the same rows; checker policies unchanged.
UI reports checked/unassessed targets, excluded evidence and outside-checker dimensions.
This is not a full answer fact checker or physical approval.

Offline replay reuses 12 consumed development bundles. Operator-authored pairs from
public question families are explicitly NOT model-generated target declarations or
verified natural-language extraction. No gold, new source queries, paid calls or new
final answers. Legacy zero-target cases 04/05/11/12 project 2/2/4/4 candidate units;
Python/SHACL flags match all12. These are software/projection results, NOT answer
accuracy gains, complete question coverage or SHACL superiority. Original outputs
remain unchanged. Live server has not been restarted; no new paid authorization.

Please check target provenance, compatibility, uncertainty disclosure and runtime
integration. Methods and implementation must independently report blockers or
warnings; no source edits. Planned checks: factory-branching-tests, factory-lab-tests,
factory-planning-tests, factory-complexity-tests. UI syntax and bounded browser
checks separately. No push/deploy requested.
