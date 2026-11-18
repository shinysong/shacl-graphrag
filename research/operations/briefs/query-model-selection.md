# Two-model selector preparation, paid gate remains closed

Allowed sources: experiments/query_contracts/{core,competing,model_selection,model_campaign}.py,
scripts/query_model_campaign.py, tests/test_query_contracts.py; dependencies
apps/factory_lab/{llm,store,evidence,graph,rdf_graph}.py and
experiments/factory_complexity/tools.py. Fixtures:
research/query-contracts-1/model-selection-001/{requests,models,scoring}.json,
selection-development-001/catalog.json. Scoring is explicitly authored prospective
intent labels permitted to reviewers but excluded from runtime/gate. No other
reviews/secrets/heldout or raw model calls. Write only your own output.

New six questions/16supplied task obligations use old consumed case01 data. Authors
see these texts: not a representative heldout benchmark/domain transfer. First two
requests repeated once, same temp0/seed42; duplicates measure stability, not independent
samples. Two same-family models google/gemini-4-hydrogen and gemini-4-carbon, Google
AI Studio pinned. Official read-only registry checked2026-11-13 pricing prompt/output
1.5/7.5 and2/10 USD per million, low reasoning/maxoutput2048, no fallback/retries.
Provider labels are positioning, not demonstrated superiority. No actual calls yet.

32 planned paid slots = (6questions+2repeats)*2models*2promptconditions. A fullcatalog,
B top3retrieved per task, C deterministic type/dependency veto of SAME B choices.
48condition records, NOT48independent paid calls or new model answers. Model chooses
one tool ornull per supplied task; no parsing/decomposition gain claimed. Same contract
fields/systemnotice/binding inputs, different catalog visibility intended retrieval
intervention. Unsupported-service info shared. C cannot repair wrong semantics or
replace tool; preserves raw and checked plans. No final business answer/SHACL efficacy.
A/B basic structural validation may prevent whole invalid plan execution; C selectively
vetoes invalid steps, so report compiler handling separately from semantic choice.

One new shared Store across both model folders, max32attempts/USD5nonrefunded, all
failures count. Conservative total reservation preview3.545815 USD from actual
request bytes*prices+framing+maxoutput, doubled; NOT tokenizer or expected bill.
New approval required: exactcampaign/caps/immutabledeadline within2h, hashbound.
Current prepared session has deadline null/statusprepared, gatefalse. No activation
function silently grants authority. preflight refuses closed gate or resume; flock
prevents duplicate launches. Launch cutoff120s before deadline, rawresponsesprivate,
publiccontentonly in progress. Shared unresolvedcost stops gateway. First call/parse
failure stops campaign, remaining slots retained. Local typedplan/execution failures
retained without gold repair. Gate closes in finally, backendsetup aftercheckpoint.
Existing ledgers untouched. Gatefields/code runtime inputs exclude scorer/labels.

Review preparation/runner safety and methods. Registered query-contract-tests,
factory-campaign-tests. Tests include fake gateway simulations (NO API/credentials),
shared32attemptledger and malformed firstreply leaving31unattempted. Existing paused
paid scopes NOT reopened. Afterchecks only docs/budgetquestion; no actualpaidlaunch
until explicit bounded human approval and checked frozen inputs. No AWS/push/restart.
