# Catalog growth and query selection

Status: implemented for offline verification and closed preparation. No paid model
calls or evaluation-question selection have been performed in this study. The prior
32-call model diagnostic remains unchanged and consumed development evidence.

## Problem and intervention

The earlier six-contract comparison could not reveal where presenting the entire
catalog becomes expensive or confusing. Its shortlist omitted the required complete
qualification-history query for one task. Both models correctly declined to substitute
partial evidence. This motivates measuring candidate inclusion before attributing
end-to-end failure to the model.

The new controlled factor is catalog size, at 6, 24 and 72 contracts. The six original
factory queries remain targets at every size. Additional contracts retrieve distinct
synthetic maintenance, calibration, inspection, supplier, material, instruction,
operator, tool, shipment, purchase-order and document-revision records. Eleven record
kinds × Machine/Order subjects × all/current/expired scope yield 66 executable SQL
predicates. They are generated schema combinations, not 66 independently authored
production use cases. Catalog growth therefore measures distractor load around a
fixed target intent set, not expanded target coverage or real catalog diversity.

The original six fixed RDFLib queries remain available. Supplemental queries run on
a separate, shared synthetic SQLite ledger, with three validity periods per subject
and record kind. Their source hashes and dates are returned separately. All conditions
have access to both sources. This is a tool-selection study, not an RDF-versus-SQL or
graph-engine comparison. No benchmark claim follows from the number of executable
queries.

## Conditions and common information

| Condition | Model input | Processing |
| --- | --- | --- |
| A | Entire catalog, once per compound request | LLM chooses one tool or null for each supplied task |
| B | BM25 top three per task, union metadata shown once | Same model, system instructions, task decomposition and bindings |
| C | Exactly B's saved choices | Deterministic input-kind/binding veto, without replacement or extra LLM call |

Every visible contract uses identical fields in A/B: tool, description, semantic
input, output bindings, evidence support, nonclaims and row limit. Internal dispatch
metadata stays outside prompts in both arms. Allowed tool IDs are per task even when
one union catalog is shown. Wrong selections outside that task's shortlist remain
protocol failures. Catalog size intentionally changes actual prompt length; common
output ceilings do not imply equal realized tokens or costs.

```text
Runtime questions + catalog(size)
              |
       full / BM25 top3
              |
         same LLM selector
              |
       preserve raw choices -----> fixed query execution (A/B)
              |
       input-kind/binding check --> fixed query execution (derived C)
              |
    saved responses/usage/provenance
              |
    separate posthoc rubric scorer
```

Execution uses the same per-task error handling in all arms. A wrong input kind can
also fail an ordinary tool call, so a checker cannot be credited with an execution
advantage merely for moving this rejection earlier. The checker does not check user
intent, time-scope semantics, source completeness, factual truth, or final answers.
Same-type wrong tools can pass. No SHACL efficacy or ontology superiority is tested.

## Development and prospective evaluation

Six new development requests and six separately authored prospective evaluation
requests each contain two supplied tasks. The two files have distinct IDs and wording;
evaluation is not a representative held-out sample. The author sees the wording and
labels while constructing the study. Both splits reuse the consumed synthetic factory
schema, entities and six target services. They do not establish domain transfer.

The offline CLI always reads development questions; it has no evaluation flag for
retrieval diagnostics. Evaluation prompts may be prepared and sized without model
selection or rubric-based scoring. Their frozen hashes are recorded before execution.
No evaluation rank/outcome inspection is part of this preparation. Future tuning must
use development results; if evaluation outcomes are inspected, mark that cohort consumed
and create a new evaluation set before further tuning. Hash manifests record this
boundary; they are not an access-control mechanism.

Runtime question files contain text and literal typed bindings, never accepted tool
IDs. Labels live under evaluation/ and are read only by the posthoc scorer. The model
receives decomposition and entity bindings supplied by the experiment. Free-form
question decomposition, multi-hop plan generation and autonomous query composition
remain unmeasured. Each task permits one tool: combining current and expired queries
to reconstruct full history is a separate future comparison.

## Metrics and denominators

Report separately for each model, catalog size and arm:

- Candidate inclusion: supported tasks with at least one intended service presented,
  divided by all supported tasks. Compute even for failed/unattempted model slots.
- Model selection error conditional on an intended service being presented; preserve
  wrong tools and unnecessary nulls separately. A missing candidate is not model error.
- Unsupported requirements: correct nulls versus substituted tool selections.
- Checker audit: wrong tools blocked, wrong tools allowed and correct tools blocked.
  A null cannot be repaired by type checking; C is dependent on B, not another sample.
- Planned, completed, failed and unattempted requests; unscored tasks remain in the
  planned denominator. Retain malformed responses, truncation, failed queries and
  uncertainty rather than silently dropping rows or repairing answers from labels.
- Prompt bytes for planned packets; actual provider prompt/completion tokens and
  reported cost only after a call. Offline token fields are null. Aggregate usage has
  a measured-call count so missing usage cannot masquerade as zero-token execution.

Exact tool-ID agreement is a service-selection rubric. A broader query may provide
sufficient evidence after downstream filtering, so disagreeing IDs are not automatically
wrong final answers. Preserve broader-query alternatives for separate adjudication.
Report per-request results; twelve tasks within six authored requests are dependent.
No final-answer accuracy, generated-answer citation quality or statistical model ranking
is measured. The earlier two-model diagnostic already found no choice difference.

## Execution and budget boundary

The user allowed a cumulative USD 5 ceiling. This objective requests implementation,
review and offline validation; it also explicitly keeps new paid execution gated.
Preparation does not activate calls. Default preparation uses one saved candidate model
configuration (Hydrogen), giving 6 requests × 3 sizes × 2 paid conditions = 36 maximum
attempts. C adds 18 derived execution records with no additional LLM call. Optional two
models are supported by the Python interface only if the complete predeclared scope
fits the same USD 5 reservation and context bounds; do not truncate arms to fit.

The candidate model and rates are saved preparation inputs, not current availability
or a claim of relative model strength. Before a paid launch, revalidate endpoint prices,
parameters and scope, freeze the current configuration, obtain scope-bound approval,
record the two-hour start/deadline and native review/check receipts, and bind approval
bytes to the gate. There is no auto-authorization CLI. Output ceiling 2048, temperature
0, seed 42 and low reasoning are inherited from the existing gateway. No fallback,
automatic retry, resumption or new window is permitted.

All preparation folders share one fixed study ledger and exclusive launch lock under
_workspace/catalog-scale-20261116/. Changing output folders cannot reset the USD 5
allowance. A nonempty study ledger blocks another launch. Failures keep reservations.
Known failed-call usage and costs are read from settled ledger records rather than sparse failure events. Unknown billing or the first paid-call/parse failure stops the campaign; remaining
slots stay unattempted. Common per-task execution failures are retained as outcomes.
The gateway checks source hashes on every call. Deadline cutoff leaves 120 seconds
for response and cleanup. Gates close on termination.

The first prepared scope exceeded the existing 60,000-byte per-request guard at size
72. Its closed folder is retained. Shared semantic metadata projection reduces prompt
size equally in all conditions. Cost previews are conservative byte-based reservation
bounds, not tokenizer measurements or expected invoices. Software tests use a scripted
gateway and cannot establish provider behavior or model quality.

## Commands and artifacts

Run all commands from the repository root with uv:

```bash
uv run --locked python scripts/catalog_scale.py offline --output _workspace/catalog-scale-offline.json
uv run --locked python scripts/catalog_scale.py prepare --work _workspace/catalog-scale-new-preparation
uv run --locked python scripts/catalog_scale.py score --results _workspace/catalog-scale-offline.json --rubric research/query-contracts-1/catalog-scale-001/evaluation/development-rubric.json --output _workspace/catalog-scale-dev-score.json
```

The score command is a separate posthoc mode; it is never imported by the campaign.
The run command requires an already approved, hash-bound scope. Keep generated packets,
raw API responses and study ledger private. Publish bounded measurements, rubric,
source hashes and public choice explanations only after inspecting them for private
content. Existing studies and ledgers are not modified.

Core implementation: experiments/query_contracts/catalog_scale.py,
scale_campaign.py and scale_scoring.py. Inputs and immutable split manifest:
research/query-contracts-1/catalog-scale-001/. Current offline checks, independent
review decisions, dissent resolution and measured development results are recorded
below after verification.

## Verified preparation and observed development results

Fresh independent methods and implementation reviews both approved offline verification
in job 20261116T003628Z-catalog-scale-selection-323aa2. The first job
20261116T003351Z-catalog-scale-selection-43a9e1 remains needs_revision: both reviewers
identified the same blocker, not conflicting conclusions. Known failed-call usage/cost
was lost by event-only aggregation although the ledger retained it. The coordinator
changed extraction to canonical settled call records, added a mocked real-Gateway
truncation test with known/unknown billing, and obtained fresh reviews. No blocker
was overridden. Original reviewer outputs remain preserved.

Registered checks: query-contract-tests 35 tests, exit 0; factory-campaign-tests
10 tests, exit 0. Software tests include scripted calls only. Actual offline development
execution additionally exercised all 66 supplemental SQLite queries and all six original
RDFLib queries. Independent Python predicate checks in tests cover all 66 supplemental
queries plus inclusive dates, future records and wrong subject types.

| Catalog size | Full candidate inclusion | Top-three candidate inclusion | Full request bytes, six development questions | Retrieved request bytes, same questions |
| --- | --- | --- | ---: | ---: |
| 6 | 10/10 | 9/10 | 28,408 | 22,485 |
| 24 | 10/10 | 9/10 | 90,472 | 23,609 |
| 72 | 10/10 | 9/10 | 255,472 | 23,570 |

Two of twelve development tasks require unsupported services and are excluded from
the candidate-inclusion denominator. All twelve remain planned tasks in reporting.
No model choices were made; all 36 offline packet slots are explicitly unattempted.
Unscored task counts are retained. These results show stable inclusion for this
wording and generated catalog, not worsening recall with scale. Input bytes expose a
prompt-size tradeoff; actual tokens, selection quality, latency and cost remain unmeasured.

The current closed preparation is prepared-004 under _workspace/catalog-scale-20261116/:
36 prospective calls, 54 raw/derived condition records if completed, conservative
reservation preview USD 3.0107340 within the shared USD 5 cap and context guard.
All preparation gates are false, no study ledger or paid calls exist, and the old
completed 32-call scope remains untouched. This goal completes preparation only.
Public development measurements and two fresh reviews are under
research/query-contracts-1/catalog-scale-001/results-development-001/.
