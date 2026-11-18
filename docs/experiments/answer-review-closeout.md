# Factory Lab post-answer review closeout

Status: bounded comparison closed on 2026-11-12. Historical artifacts, failed
attempts and individual annotations are retained. This is a research-scope decision,
not removal of the review tools from Factory Lab.

## Evidence and claim boundaries

| Evidence | Observed result | Supported interpretation |
| --- | --- | --- |
| [12 compound cases](records/2026-11-11-factory-complexity-llm.json), 12 drafts and 36 final answers | 75 calls; no clear wrong core applicability judgment identified against selected evidence | The supplied bounded questions did not demonstrate a core-decision gain from post-answer reports. This is not external accuracy or an equivalence test. |
| Same 12-case comparison | Some reason-code correction, remaining errors and report-introduced overstatement | A report can clarify reasons without improving the core choice, and can also accompany unsupported claims. |
| [Selected coverage follow-up](records/2026-11-12-coverage-live.json), four consumed cases, four drafts and 12 final answers | 22 calls; 12 expected declared pairs checked; cases 11/12 draft/self reason codes corrected by both report conditions | This completes the explicit-target integration diagnostic. It does not demonstrate complete natural-language interpretation. |
| Same-policy Python and SHACL | Identical final model input messages in all 12 original cases and all four follow-up cases | No SHACL-specific answer advantage is established. Different generated wording is not evidence of a different checking policy. |

The follow-up cases were selected because the earlier projection produced zero
checker targets. They are consumed development data. Do not pool both campaigns
as independent cases, report a general accuracy rate, or tune and relabel them as
held-out evaluation. Unnecessary withholding and source/retrieval absence remain
separate from wrong applicability reasons.

## Closure decision

Do not add more similar cases just to seek a positive SHACL result. Retain the
three post-answer conditions as a downstream diagnostic and reusable system
component. Reopen this comparison only for a materially new failure mechanism or
an independently specified question population. A new paid run needs its own
bounded scope; unused old budgets are not permission to rerun.

Ontology/SHACL maintenance, portability and human audit value remain plausible
architectural uses, not measured maintenance-effort gains. The new phase is
[query contract retrieval and composition](query-contracts.md), where the primary
unit is a question requirement and its retrieval/evidence lineage.
