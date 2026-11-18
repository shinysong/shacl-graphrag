# Blinded original-question and final-answer audit

Allowed artifact ONLY _workspace/query-composition-20261116/audit-packet.json (source,
originalquestions,manualreference4needs/case,modelrequirements,12anonymousanswers,
modelwrittenplans,actualselectedqueryresults/context/lineage,sourcepolicy). No condition
map,otherrevieweroutputs,secrets,rawAPIresponses,codechanges or modelcalls. Root masked
three arms, reordered within cases. Evaluate evidence, do not guess arm identities.
Write only own assigned agent-output.json. No tests or API calls.

Four new authored compound requests, not heldout; common model decomposition, three
final answers percase. One originalformat failure preserved; source-onlyenveloperecovery
reusedexact2responses,24totalcalls, no extra modelretry. Judge saved semantics, not
preregistration/modelgeneralization. Native reviewers are research assessment, not
experimental multiagent treatment. No forced checker/model advantage.

Independently assess BOTH decomposition and finalanswers against ORIGINAL needs:
1. Four decomposition findings, one percase; evidence JSON string:
{"kind":"decomposition","case":"c01","requirements":[{"index":0,"status":"covered|partial|missing|unclear","quote":"exact substring of model requirement text, or empty if absent","note":"brief reason"}, ...all four...]}
2. Twelve answer findings, one peranonymousanswer; evidence JSON string:
{"kind":"answer","case":"c01","answer_id":"Z01","requirements":[{"index":0,"status":"supported|partial|withheld_correctly|withheld_unnecessarily|unsupported|unclear","quote":"exact substring from saved answer text or coverage explanation; empty if omitted","note":"brief reason"}, ...four...],"issues":{"query_omission":"present|absent|unclear","wrong_binding":"present|absent|unclear","lost_order_context":"present|absent|unclear","unsupported_certainty":"present|absent|unclear","unnecessary_withholding":"present|absent|unclear","unresolved_disclosure_missing":"present|absent|unclear","citation_support_error":"present|absent|unclear"},"issue_evidence":"specific quotes/evidence IDs supporting present/unclear findings"}
Use the required common root contract. Exactly16 findings, severityinfo unlessactual
problem meritswarning; JSON goes inside evidence STRING, not new root fields. Each
finding recommendation may state interpretation/limitation. Decisionready means
assessment complete, not that modelanswers correct. No source edits/repair.

Coverage statuses are modelselfreports, not truth. Queryexecuted/rowsreturned are not
semanticrequirementsatisfaction. Distinguish: missingdecomposition, queryomission,
emptyselectedresults, upstreamempty preventeddescendantquery, unsupportedservice,
sourceabsenceunknown, actual wrongbusinessclaim. Potentiallybroaderqualquerycan suffice
with filtering; exacttoolIDnotgold. Unnecessarywithholding is relative to sufficient
RETRIEVED evidence, not facts hidden frommodel; sourcepacket may diagnose retrieval
omission separately. CitationIDs existence is different from support/applicability.
No schema-conformance/physicaltruth/completeness claims. Unsupportedservices honestly
unresolved are correct. Preserve ambiguity/disagreement, do not forcebinarysummary.
