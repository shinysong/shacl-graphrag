# Catalog-scale preparation review

Read only own request, this brief, docs/experiments/catalog-scale-selection.md,
experiments/query_contracts/{catalog_scale,scale_campaign,scale_scoring,core,model_selection,competing,model_campaign}.py,
scripts/catalog_scale.py, tests/test_query_contracts.py, apps/factory_lab/{llm,store}.py,
research/query-contracts-1/catalog-scale-001/manifest.json, runtime/catalog-{6,24,72}.json,
runtime/development.json, evaluation/development-rubric.json; read-only prepared-003
cost-preview/session/execution-gate if needed. Do not inspect evaluation question texts
or evaluation rubric, other reviews, secrets or private historical responses. Review
code access paths and manifest hashes instead. No source edits or paid/network calls.
Write only own result JSON.

User goal: executable comparison full-catalog vs BM25 candidates as catalog grows,
separate development/prospective questions, candidate inclusion, model errors,
unnecessary withholding, actual usage/cost instrumentation; independent reviews and
offline checks. USD5 cumulative cap but paid gate remains closed for this implementation
objective. No actual study model calls. Prior32-call outputs untouched.

Design: nested6/24/72 catalogs, original6 targets fixed;66 additional executable
record-kind × Machine/Order × all/current/expired SQLite predicates (not aliases).
Generated synthetic distractor density and same template family, not representative
catalog diversity or expanded targets. Originalsix query dispatch RDFLib. All conditions
access both sources identically, separate provenance; not engine/ontology comparison.
Sixdev6prospectiveauthorednew requests×2suppliedtasks, oldschema/entities; not unseen
heldout/domain transfer. Offline CLI devonly, evaluation prepared but notrank/outcomes
inspected; prospective hashes frozen. Runtime labels never read; posthocscore separate.
A full listonce vs B top3/taskunionmetadata; C sameBchoices inputkindveto only. Same
metadata/system/bindings; no decomposition/composition/finalanswer/SHACL efficacy.
Same per-task execution/error policy inA/B/C, so no whole-plan rejection confound.
Inputtypevalidation in ordinarytools already exists; checker may move error earlier
without execution improvement. Broad-query sufficiency separate exacttoolrubric.

Default one savedcandidateHydrogenmodel,36paidattempts/54records if laterapproved;
not currentavailabilityclaim. No retries/fallback/resume. TotalreservedUSD3.0107340,
not expectedbill/tokenizer.2models optional only if whole scopefitsUSD5/context.
One fixedstudyStore/lock across allworkfolders; nonemptyledger blocksnewlaunch,
allfailurescount/no refund, unknownbilling stops, firstcall/parsefailurestops;
checkpoint beforegraphsetup, retainallslots/failedstatus. Exactapprovalhashscope,
2hmax/window120scutoff, frozenruntimehashespercall; allgatesclosefinally.
No automatic approvalCLI. Initialprepared001 exceededcontext, preservedgateclosed;
metadata projection sharedacrossarms fixedcontext;003currentclosedpreparedscope.

Tests cover independentPythonpredicates for66SQLtools, boundarydates/wrongtypes,
sharedledger/noreset, gate/hash/approval, no runtimegold, malformedfirstcall,
backendsetupfailure, usageinstrumentation, scorerdenominators/falseveto. Scripted
Gateway means no providerbehavior/modelaccuracy evidence. Registeredtests not yet
run for final source. Reviewers must not infer observedtestsuccess from source.

## Revision before fresh review

The first review job20261116T003351Z-catalog-scale-selection-43a9e1 is preserved with
both reviewers revising. Its blocker was loss of known failed-call usage/cost in
condition-level aggregation. scale_campaign now reads canonical Store.calls settled
details via settled_calls for success and failure. No shared Gateway source changed.
A network-free test invokes the real Gateway with mocked HTTP truncation responses,
known and unknown cost variants; checks failedcost/tokens, preservedreservation,
unresolvedcount, remaining35slots and closedgate. Fresh reviewers verify the fix
independently; do not read any other review or infer tests passed from this statement.
Prepared003 preceded this change and remainsclosed/stale, not runnable. Prepare a
fresh closed folder after finalsourcefreeze. No paidmodelcall/evaloutcomeinspection.
