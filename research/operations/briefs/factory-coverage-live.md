# Four-case actual LLM coverage follow-up

Latest human explicitly requested actual LLM execution before moving to contract-based
query selection research. Coordinator states conservative new operational ceilings:
36 attempts, USD2 nonrefunded reservation cap, one hour from preparation, no retries.
These numeric ceilings are operator limits, not a verbatim numeric human approval.
Prior 108/USD5 window and ledgers stay closed/untouched. No AWS starts, no push.

New execution module experiments/factory_complexity/coverage_campaign.py uses the
reviewed coverage-enabled Runner and existing bounded Gateway. Exact cases04/05/11/12
are selected because previous checker target count was zero; consumed development,
selection bias explicit, not a fresh benchmark or randomized treatment comparison.
No operator targets supplied at runtime. Model may declare targets using exact user
quotes. Capture missing/wrong declarations, actual selected evidence, draft and three
isolated finals. Same evidence and report policy for Python/SHACL. Compare to old
outputs descriptively only because tool availability and generated traces change.

Read permitted code: coverage_campaign.py, campaign.py, tools.py under
experiments/factory_complexity; agent.py, branching.py, coverage.py, evidence.py,
review.py, llm.py, store.py under apps/factory_lab; tests/test_factory_campaign.py,
tests/test_factory_branching.py. Private live-001 session/model/approval/plan/gate/readiness
JSON under _workspace/factory-coverage-20261112 are permitted; no .env, raw calls,
evaluation files or other review outputs. Gate false until both reviews/checks pass.
Readiness fetched from OpenRouter endpoint registry: unchanged Gemini3.8flash Google
AIStudio prices prompt0.75/output3.75 per million,tools/seed/temp supported. No API key
in packet. Old ledgers inspected for unresolved billing before preparation.

One launch lock and existing-progress/ledger rejection prevent resuming silently.
Gateway checks hashes and reserves before every paid request; failures nonrefunded,
unknown billing stops; output truncation retained without retry. Explicit 120second
cutoff before deadline. Runner max6generation steps plus3 finals =9 requests percase.
On first failed episode stop and preserve remaining slots. Finalizer closes gate.
No running service or scheduler introduced. Tests must verify closed gates and
failure denominators; reviewers must flag concrete unsafe execution boundaries.

Permitted registered checks: factory-campaign-tests, factory-branching-tests,
factory-lab-tests, factory-complexity-tests. After run produce public content/event
metadata only (no raw hidden provider continuation state). Review answers separately
from execution correctness and avoid attributing ordinary language variation to SHACL.
