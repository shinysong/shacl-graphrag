# Actionable evidence offline implementation review

Review actual implementation and measured DEVELOPMENT behavior, not efficacy generalization. User authorized8h offline work, no paidcalls/push. Prior design review20261029T150234Z-meyers-actionable-design-0a068c bothready asked exact denominators, direct/postcheck semantics, dependency scope, limits, freshshadow rebuild; these are now in implementation-contract.md.

Explicitly allowed read-only files (all new synthetic fixtures are consumed development, no heldout):
- research/actionable-evidence-1/{README.md,protocol.json,implementation-contract.md,rules.ttl,shapes.ttl}
- scripts/actionable_evidence/{runtime.py,generate.py,run.py,evaluate.py,__init__.py}
- tests/test_actionable_evidence.py
- research/actionable-evidence-1/fixtures/{manifest.json,scorer.json,runtime/*.json}
- research/actionable-evidence-1/runs/{smoke-001,run-001}/{freeze.json,completion.json,outputs.jsonl,evaluation.json}; source snapshots frozen-inputs.zip ineachrun.
- docs/experiments/actionable-evidence-study.md and records/20261029-actionable-evidence.json
- Source extract/audit research/actionable-evidence-1/source/*.json only if needed. Earlier243 actual annotations remain descriptive; no source correction truth or officialactionpolicy.

32authoreddevelopmentcases=2fieldroles*2pathdepths*8states. Runtime schema strict, IDs opaque, fields setting/code andend_mm/mm. Reference supports entity/field/unit/version; separate scorer read after savedcompleteoutputs. Both reference evidence and externaltruth authored; NOT independentlyobserved source. Runtime neverloadsgold.4missingcausepairs byteidentical, nofetch.8states clean,sourceabsent,projectionomission,stale,wrongentity+fieldbundled,conflict,conformingfalse,dependencyviolation. Targetsinitiallynull; no sourcephysicalmutation.

3candidatearms: directoneedge only; Python1/2edges; actualpySHACL-AFSPARQLRule1/2edges. Allmatching/unique-referencepolicies same. Directincompleteness purposelydesigned, notBM25/vector/LLMbaseline. Postfactor uses samebefore/afterdiagnostics but onlyshadowarm vetoes nonconformingpatch, so NOTlatencycomparison. Rulesadvanced=True,inference=none,iterate_rules=False,inplaceprivategraph. Onepass, norecursivegeneration. Shadowdeepcopyasserted+patch andnewgraph, rerunderive; no staleinferredtriples. Pythonindependentvalidator also matches SHACL. Outputkeeps precandidateids,citations,patch,diff,before/after,disposition,hashes.

Limits16nodes24edges8dependencies4refs; timeout30seconds/row1attempt; max192rows; sequentialchildrenisolatedruntime receivesinput,arm,postonly. Errors retained in denominator; no retries. Registeredchecks=[]; manual5unittest methods pass,2case12row smoke0errors then32case192row full0errors,sourcehashesunchanged. Smoke overlapsfull, NOT204independentrows. pySHACL0.40.1,RDFLib7.6.0,uv.lockhashfrozen.

Observed per32cases (proposals/unsupported_condition_proposals/unnecessarywithholding_of4correctknowneligible/externalwrong): direct/no6/2/2/2, direct/post4/0/2/2; Python/no12/4/0/4, Python/post8/0/0/4; SHACL-AF identicalPython. Fullcandidateids,citations,patch,diff,disposition,before/afterparity32/32perpost. All192originalunchanged andvalidatorsagree. Contracteligible8 includes4conformingfalse, correctknowneligible4; dependencyviolating4noteligible evenvalueistrue. Externalwrong canpasscontract: do not label32/32contractagreementasfactualaccuracy. Errors separateunnecessarywithholding; eligibilitydenominatorsexplicit evaluator. Unsupported label includesdependencyviolations, notjust absentreference.

Methods: assess experimentalclaimboundaries and metricmeaning, suppliedpolicies andsyntheticauthorship. Implementation: inspectindependentruleexecution, strictschema, patchdiff, freshshadow, nooraclerepair, freeze, output/evaluatorconsistency. All sourcepathslisted above mayberead; do notreadanotherreviewfolder orsecrets. Writeonly designatedresultJSON. Sourcecodechanges requirefreshreviewjob; report blockers vsoptionalexpansions accurately. No paidAPI ornewexperiments requested fromreviewers. Local test reruns permitted but notnecessaryifstaticreviewadequate.
