# Offline source-bound support scoring v1

This scorer runs only AFTER retrieval, reading the original references and saved
outputs. It never calls a retriever, model, checker or repair operation, and never
writes original inputs. No runtime module may import it. Existing24 questions
and source are consumed development. The equivalent-support policy was recorded
in offline-interface-v1 before dense retrieval; this implementation is written
after observing edge-only selection and is not a blinded evaluation.

## Support and source scope

Preserve every reference question in the denominator, including missing/failed/
malformed retrieval outputs. Reject duplicate/extra question IDs as scorer-input
errors, not silent exclusions. A missing envelope is recorded as missing_output.
A non-ok envelope is retrieval_failure. For ok envelopes require matching ordered
selected IDs, canonical evidence hash, byte count and exact original source
chunk payloads. Any mismatch is invalid_evidence, never repaired from source.

For source-present questions, complete support requires all nodes in one frozen
admissible_node_set. For a lookup, the selected annotation's dictionary_refs
must bind the required field to the selected target; source workbook/hash/coupon
and code must match. Explicit edges cannot replace missing endpoints; with both
source-exact nodes the embedded link is sufficient, so no extra edge is required.
No extra credit for duplicate link representations. Report node coverage and
complete support separately. Count missing/failed/invalid outputs as incomplete
for source-present denominators, with reasons preserved.

Source-absent review-version questions are a separate6-case group with complete
support=null, not false or vacuously true. No abstention/hallucination/answer
accuracy can be scored because no generator ran. Reference absence is restricted
to the supplied bundle; do not infer absence from lack of retrieval hits.
Validate reference node existence and binding against the source before scoring;
malformed reference definitions are scorer errors, never altered silently.

## Reporting and controls

All24 rows retained; source-present18 subdivide by task (6each), source-absent6
reported separately. Freeze reference/source/output/code/protocol hashes and
copies; retain original dense-retrieval-001 unchanged. Tests use offline fixtures
only and exercise valid nodes without explicitedge, edge-only failure, wrong-scope
target, tampered payload/hash, missing/failing output, source-absent null, duplicate
IDs and bad reference definitions. These tests are not extra research cases.
Software support is under authored evidence contracts, not external factual truth
or general vector-RAG effectiveness. Do not retune or repair this saved run.
