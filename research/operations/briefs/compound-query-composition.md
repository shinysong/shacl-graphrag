# Compound query composition: actual end-to-end comparison

Allowed reads: docs/experiments/compound-query-composition.md;
experiments/query_contracts/{composition,composition_campaign,core,competing,model_campaign,scale_campaign,catalog_scale}.py;
scripts/query_composition.py; tests/test_query_contracts.py;
apps/factory_lab/{llm,store,graph,rdf_graph}.py; experiments/factory_complexity/tools.py;
research/query-contracts-1/selection-development-001/catalog.json;
research/query-contracts-1/composition-001/runtime/questions.json and manifest.json;
_workspace/query-composition-20261116/model-candidate.json and endpoint-before-review.json.
No evaluation/rubric.json, other reviewers, historical raw modeloutputs, .env/secrets.
Runtime questions are author-seen exploratory diagnostic, not heldout. No gold repair.
Read-only source, write only own agent-output.json. No API calls.

Latest human approved cumulativeUSD5 research and requested unfinishedoriginal three-arm
comparison. Earlier cataloggrowthpreparation used0paidcalls; it is stopped asmainfocus.
Originalquestion -> sameLLM modelrequirements (sharedonce) -> fullvsretrieved independent
LLMplans (stepsANDbindings modelwritten) -> rawandcheckedactualfixedqueryexecution ->
3separateLLMfinalanswers withcoverage andadditionalunresolved. 4newcompoundrequests.
Runtimefiles question/id ONLY; evaluatorrequirements never read byrunner. C sameBplan,
checks types/dependency/visibletools andcomputedrequirementstatuses, noadditionalfacts,
no modelplannerretry/replacement. Allarms sameinformation fields andminimumperstep
execution safety. C can onlytrackmodeldeclaredrequirements; nooraclecompletenessclaim.
A/Brawfailures retainedperstep, not wholeplanrejection. Typedwrongsemanticspass.
Allqueries existingfixedRDFLib againstsameconsumedcase01; ordercontext/provenance
preservedperrow. Finalprompt excludes SQL/duplicatedoutputcopies equally, retains
calls/resultrows/context/inputlineage. No sourceaccessafterfinalizationstarts.

Budget max24attempts=4decompose+8plan+12final; USD5cumulative fixedstudyStore/lock
sharedwithcatalogscalepreparation (ledgercurrentlyabsent), no retries/resume/fallback;
max2h window; launchcutoff120s. Beforelaunch reviews+registeredtests andcurrentprices.
Onecandidate google/gemini-4-hydrogen pinnedgoogle-ai-studio, temperature0 seed42 low
reasoning maxoutput3072, bytecaps8000/20000/30000 => conservative reservation3.1305600USD
notinvoice/tokenizer. Rootgatefalse untilboundhumanapproval. Perstage providerusage
fromcanonicalStorecalls includesknownfailedbilling. Unknowncoststops.

Softwaretests includingreal3hopRDFLibchain/context, omissionpreserved, wrongbindings,
computedreportnotsemantictruth, finalcitationerrorsoutcomes, no-runtimegold and scripted
24callthree-arm pipeline/failure. No tests claimedasrealmodelbehavior. Actual paidrun
and independentposthoc originalrequirement/answersaudit requiredbeforegoalcomplete.
Check possibility of parser/cap/plan/execution mismatches andfairness. No implementation
worker may change code. Check hashes in own packet. Finalanswersmayallgood: accept.

Revision: firstjob011945-00b9dd preserved withimplementationblocker. Non-scalar resolvedbindings now become per-step issues beforeentitydictionarylookup; modelbindingunchanged, independentstepscontinue. Newregression parsesdict-valuedpath andchecksrawretention/laterexecution/Cveto. Freshreviewbeforepaid.


Manual recovery scope: actual originalrun stopped after2paidcalls, reportedUSD0.0138990,
reserve0.1517130,unresolved0. Commondecompositioncompleted; firstfullplan wasvalidJSON
insideoneMarkdownJSONfence. Originalfailureprogressimmutable at
_workspace/query-composition-20261116/prepared-002/progress.json (allowedexplicitread).
Only recovery additions: genericwhole-responsefence decoder (noJSONcontentrepair),
manualrecover-prepare requiringexactinspectedtwo-stagefailure; compare reconstructed
planner messages byte-for-byte to originalpaidrequest, freezeparentprogress/recovery,
reuse2savedresponses, sharedledgerstillmax24/USD5, SAMEoriginal03:24:16UTCdeadline.
Rawfirstfailedrecord retained; recoveredstage marked reused_format_normalized and
original_status failed. No oldpaidcall repeated, only22remaining calls. No generic
resumeorautomaticretry. Test usesrealGatewaywithmockHTTP andoldparserfailure, verifies
24totalhttpcalls,sharednonrefundledger,oldprogresshashunchanged,samedeadline. No fresh
modelcalls sincefirstfailure. Reviewmanualrecoverybeforeactivate; ifblockeddo notlaunch.
