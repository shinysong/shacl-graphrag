# Model-authored compound-query composition

Status: implementation and bounded execution preparation. This study addresses the
unfinished end-to-end comparison, not further catalog-index tuning. Existing selector
and catalog-scale records are preserved as separate consumed development work.

## Research question and shared trace

Can the model identify the requirements in an original compound request, construct
fixed-query dependencies, preserve order/candidate evidence context and disclose what
remains unresolved? Does an explicit connection check and requirement-status report
change the final answer beyond the same retrieved plan and source facts?

Runtime inputs contain only four new authored original questions with IDs. They contain
no task decomposition, bindings, expected tools, expected answer or evaluation labels.
A common model call enumerates information needs from the original text. Both planning
conditions then receive this same model-authored decomposition. This isolates query
planning differences while measuring decomposition omissions separately. The study
therefore does not measure different decomposition policies across arms. A shared
omission can affect every arm; it is never filled from scorer labels.

| Arm | Model planning | Execution and finalization |
| --- | --- | --- |
| A full | Entire six-contract catalog; model writes steps and literal/output bindings | Actual fixed queries; independent final-answer call |
| B retrieved | BM25 top-three per model-declared requirement, union visible contracts | Same per-step execution policy; independent final-answer call |
| C checked | Exactly B's saved model plan, no extra planner call | Sequential input/output/dependency check; reject incompatible steps without replacing; requirement-status report; independent final-answer call |

All visible contract descriptions, input/output schema, source ID registry, policy,
source snapshot, query-attempt limit and final output ceiling are identical. B/C share
planning input and original plan. C adds computed procedural feedback and may suppress
invalid connections; it receives no additional source access or evaluator information.
A/B finalization receives the same original question, model requirements, plan, available
contract fields, raw step status and actual graph evidence. Thus the intervention is
explicit connection checking and aggregation of tracking information, not superior
semantic descriptions. C is paired with B, not an independent plan sample.

```text
Original compound question + common schema/ID registry
                  |
       LLM requirement decomposition (shared)
             /                    \
 full contracts                 BM25 contract candidates
       |                              |
 LLM-written DAG A             LLM-written DAG B (frozen)
       |                          /                \
 fixed query execution       raw execution       connection check
       |                          |             + tracked unresolved needs
       |                          |                  |
       |                          |             fixed query execution
       |                          |                  |
 final answer A              final answer B      final answer C
             \                    |                  /
             independent posthoc original-requirement audit
```

A DAG binding is either a model-selected literal entity ID/kind or an earlier step's
row path (order.id or machine.id). Fan-out executes downstream queries per source row,
preserving order/product/capability context and evidence lineage. Raw queries and
responses are saved; SQL text and duplicate output copies are omitted equally from
final prompts. Query calls retain context and input lineage. No free Text2SPARQL,
query generation, model-based source repair or physical process recommendation occurs.

## Checks, omissions and outcome boundaries

All arms enforce the same minimum runtime safety: presented fixed tools, real entity
kinds, argument/source/row binding, snapshot consistency and per-step call budget.
They retain wrong connections and failed steps without whole-plan rejection or repair.
C additionally applies explicit schema checks before execution and summarizes status
per model-declared requirement. Correct types can still express the wrong semantics.
Ordinary execution can reject some of the same bad bindings; earlier rejection alone
is not answer improvement.

C's tracking report knows only model-declared requirements. It cannot prove the original
question was fully decomposed. Rows returned or executed queries are not semantic
satisfaction or source completeness. Final answers independently classify each declared
need as answered, partial or unresolved, with evidence IDs, and may acknowledge original
needs omitted from the first decomposition. Citation errors and semantically wrong
answers remain outcomes, not runtime repair criteria. No compulsory veto is imposed
on final generation.

## Frozen cases and evaluation

Four new authored compound requests use the consumed factory-v3 selected source:
M02 interruption with per-order alternatives/applicability/delivery; O19 assignment,
alternatives/history/current-expired/authenticity; M03 impact/context/record-fusion/load;
O18 assignment/history/applicability/physical-approval boundary. Evaluation references
list four original requirements per case and eight assessment dimensions separately
under evaluation/. The runner never reads them. These are exploratory author-seen
compositions over a known synthetic domain, not representative or fresh-source held-out
evaluation. No result-dependent cases or manufactured model errors are added.

Independent posthoc reviewers must audit actual saved decomposition, plans, execution
and final answers against original requirements and selected evidence. Report:

- Original requirement omission in model decomposition; do not confuse it with an
  unsupported service correctly identified as unresolved.
- Necessary query omission, wrong dependency bindings and lost order/candidate context.
- Unsupported certainty and correct-known unnecessary withholding together, plus explicit
  unresolved-requirement disclosure. Keep ambiguous judgments and disagreements.
- Citation reference validity separately from whether the evidence supports the claim.
- Model calls and actual source queries separately, provider input/output tokens,
  reported cost, nonrefunded reservations and all failed/unattempted phases.

Exact final-answer correctness is bounded to selected evidence and the declared policy.
No physical truth, source completeness, general model ranking, SHACL efficacy, ontology
superiority, Neo4j/Neptune performance or natural-language-to-schema generation claim.
If every final answer is adequate, that is a valid result; do not force checker benefits.

## Paid scope and termination

The latest human authorized paid research up to cumulative USD 5 and requested this
unfinished comparison. No prior paid campaign is reopened. The catalog-scale budget
remained unused; composition shares that same fixed study ledger/lock, so changing
campaign folders cannot multiply the allowance. Before launch, complete independent
methods/implementation review and registered offline tests, verify source hashes and
current endpoint prices, and bind the latest human instruction to this exact scope.

Scope: four common decomposition calls + eight plan calls + twelve final-answer calls
= maximum 24 attempts including failures, no retries. One model: saved candidate
Gemini 4 Hydrogen via google-ai-studio, rechecked before review; temperature 0, seed42,
low reasoning, max3072 output tokens for every stage/arm, no provider fallback.
Byte caps are 8000 decomposition, 20000 planning and 30000 finalization; the existing
gateway adds conservative framing and doubled price reservations. Worst complete-scope
reservation at frozen rates: USD 3.1305600, not expected invoice or tokenizer count.
Actual reported tokens/costs are retained including known failed-call billing.

One immutable two-hour window begins at activation, with 120-second launch cutoff.
Unknown billing, first call/response-schema failure or cap violation stops the campaign;
failed and unattempted stages remain. Setup is after the initial checkpoint. No automatic
retry/resume or replacement models. Gates close at termination. Actual graph-query
failures stay in the episode and are provided to the final model; no evaluator repairs.

## Implementation and verification

- experiments/query_contracts/composition.py: model messages/parsers, raw/checked DAG
  execution, order lineage, computed requirement report, final answer/citation outcomes.
- experiments/query_contracts/composition_campaign.py: three-arm staged campaign, shared
  cumulative ledger, stage-byte ceilings, all failed billing and one-launch gate.
- scripts/query_composition.py: prepare or execute an already approved scope.
- research/query-contracts-1/composition-001/runtime/questions.json: original text only.
- evaluation/rubric.json: independent posthoc references, excluded from runner inputs.

Existing software tests are extended with model-output omission preservation, actual
three-hop RDFLib lineage, wrong dependencies, same-information controls, unplanned needs,
citation errors as outcomes, and scripted complete/failed three-arm cycles. Such tests
verify implementation, not real LLM quality. Actual outcomes and independent answer
reviews will be appended after execution; completion requires these, not preparation alone.

## Preserved first failure and manual format recovery

The original paid collection stopped after two calls: shared decomposition completed,
then A's plan was valid JSON inside a single Markdown JSON code fence. The strict
JSON decoder rejected the envelope. Original status remains stopped, with one failed
plan stage, three unattempted cases and no final answers; reported USD 0.0138990 and
nonrefunded USD 0.1517130 remain in the shared ledger. Do not report first-try completion.

A source-only recovery adds a generic decoder for a single whole-response JSON fence.
It never repairs JSON fields, syntax, tool choices, bindings or semantic decisions.
Arbitrary prose or invalid JSON still fails. The recovery verifies reconstructed
planning messages equal the saved paid request, freezes original progress and reuses
the exact two saved responses. Original progress is immutable. A separate continuation
marks the formerly failed stage as reused_format_normalized with original_status=failed.
No original call is repeated or refunded.

Manual continuation remains within the original maximum 24 attempts/USD 5 and original
03:24:16 UTC deadline; at most 22 new calls remain. Explicit recovery preparation and
fresh independent review/checks precede activation. This is a post-failure protocol
adjustment, not a clean preregistered first-try trial or automatic retry. Report initial
failure and continuation separately alongside combined conditional end-to-end results.

## Completed actual comparison

All four cases and twelve final answers completed after the separately preserved
format-only recovery. Total paid requests are 24, comprising the original two plus
22 continuation requests; no request was repeated. Reported cost USD 0.2782440,
nonrefunded reservations USD 2.1429330, unresolved costs zero. Provider-reported usage
was 53,706 prompt tokens and 26,358 completion tokens (including provider-accounted
reasoning); these are study totals, not final-answer-only counts or invoice verification.
All execution gates are closed and the shared USD 5 scope is complete.

| Case | Model plan steps per arm | Dependency edges per arm | Actual queries per arm | Retrieved visible contracts |
| --- | ---: | ---: | ---: | ---: |
| c01 M02 impact/alternatives/qualification/delivery | 3 | 2 | 9 | 5/6 |
| c02 O19 assignment/candidates/history/authenticity | 5 | 3 | 5 | 5/6 |
| c03 M03 impact/context/fusion/load | 3 | 2 | 1 | 6/6 |
| c04 O18 assignment/history/applicability/approval | 4 | 3 | 4 | 5/6 |

Actual queries total 57 across A/B/C, with zero query-call failures. C rejected zero
steps. Compact execution payloads were identical across the three arms within each
case (four unique evidence bundles); only plan explanation/unplanned wording and
procedural feedback differed. c03's selected-view impact lookup returned no orders,
so downstream candidate/qualification lookups could not run and remained unresolved.
This is not omitted planning or global source absence. c01 executed the actual
order-to-candidate-to-qualification chain with per-order lineage. c04 executed distinct
all/current/expired qualification lookups after retrieving its assigned machine.

Two independently contextualized native reviewers audited masked conditions against
original questions, four reference needs per case and actual retrieved evidence.
Both found all 16 original needs represented in model decomposition. Each returned
16 findings with 64 requirement ratings; all 128 quoted substrings were verified
against saved decomposition or answer text. References count separately from support;
no final coverage label was treated as proof of correctness.

Neither reviewer established a definite error across the seven issue dimensions.
Preserve four disagreement cells: all three c04 history answers were rated partial
by one reviewer (global complete history unknown), but supported as selected-view
observations by the other. The checked c04 answer's availability wording was unclear
to one reviewer and not an issue to the other: recorded status unavailable is known,
but schedule/capacity remains unknown. Both preserved the distinction between capability
candidates and operational approval when a stopped machine appears in the list.
No majority override or artificial overall accuracy score is reported.

The full annotation job recorded both original reports, but synthesizing their complete
contents exceeded the research-operations prose packet ContextLimit. A separate compact
closeout reused each same reviewer's own completed assessment, without another audit,
model call or loss of full annotations. Jobs and both versions remain preserved.

The end-to-end workflow has now actually run. This is still a bounded exploratory
four-case comparison over known synthetic data. There is no demonstrated incremental
checking benefit, model-equivalence result, complete-source guarantee or SHACL-specific
advantage. The full six-tool catalog already enabled adequate bounded planning in
these cases; adding more index complexity is not justified by these outcomes alone.
The structural tests demonstrate handling of injected invalid bindings, not naturally
observed improvement. Retain this result rather than manufacturing errors.

Independent implementation reviews, 46 query tests and 10 factory campaign tests all
passed after the recorded fixes. The actual output audit is additional evidence, not
a software-test substitute. Public results and both full audits are preserved under
research/query-contracts-1/composition-001/results-001/; raw API responses stay private,
with hashes and reported usage in public metadata. Earlier selector/catalog studies
remain separate and unchanged.
