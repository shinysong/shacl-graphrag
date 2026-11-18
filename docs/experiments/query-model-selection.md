# Two-model query selection and contract checking

Status: completed on 2026-11-13 after explicit 32-attempt/USD 5/two-hour approval. This is a selector diagnostic, not a
new final-answer/SHACL efficacy campaign. Earlier paid campaigns remain closed.

## Model and structure factors

The public OpenRouter registry checked on 2026-11-13 lists
[Gemini 4 Hydrogen](https://openrouter.ai/api/v1/models/google/gemini-4-hydrogen/endpoints)
and [Gemini 4 Carbon](https://openrouter.ai/api/v1/models/google/gemini-4-carbon/endpoints).
They are selected as same-family efficiency/frontier-positioned models to reduce
vendor confounding, not because superiority has been measured here. Both use the
pinned google-ai-studio provider, no fallback, temperature 0, seed 42, low reasoning
and max_tokens 2048. Aliases and provider behavior are not immutable model weights;
record returned model/provider and all reported usage. Repeat stability is empirical,
not guaranteed by temperature or seed.

| Condition | Model sees | Post-selection processing |
| --- | --- | --- |
| A | Full six-query contract catalog per task | Preserve selections; structural validation before fixed queries |
| B | Same BM25 top-three contract candidates per task | Preserve selections; same structural validation |
| C | Reuses exactly B's model response | Selectively veto incompatible input/output/dependency steps; no new model call or replacement query |

All contracts carry the same fields. Decomposition, typed seed identifiers, dependency
paths, model instructions and unsupported-service notice are supplied identically.
The experiment measures selection on supplied interpretations, not natural-language
question parsing. A/B change catalog visibility and prompt length intentionally;
report exact bytes/tokens and retrieval candidate coverage rather than treating equal
ceilings as equal realized compute. C is paired derived processing of B, not an
independent model condition. It cannot detect all same-type semantic mistakes.
A/B can reject an entire invalid plan while C preserves compatible steps: separate
that compiler-policy difference from model semantic quality.

## New questions and preserved scope

Six new authored requests comprise 16 distinct task obligations. They combine
assignments, capability candidates, all/current/expired qualification records,
delivery feasibility and document authenticity. The first two requests repeat once,
adding six repeated obligations per model/paid condition. All original author labels
are kept in a separate scorer file; runtime and paid gate never read that file.

These are author-seen prospective diagnostics over the same consumed synthetic
case-01 selected graph. They are not representative held-out evaluation or domain
transfer. Do not pool repeated tasks or the old diagnostic cohort as independent
samples. Retain broad-query alternatives for secondary adjudication: all qualification
records may support later filtering, so exact tool-ID disagreement is not necessarily
insufficient evidence or a final wrong answer. No final business answer is generated
by this scope.

## Outcomes and failure accounting

Record every model selection/null and its short public explanation, presented
candidates, required-query omission, unsupported-service substitute, type rejection,
unnecessary rejection, invalid response schema, invalid plan, failed query, selected
rows, truncation and unattempted slot. Preserve the raw choice before any deterministic
veto. No evaluation-label repair or model retry. Same-policy Python/SHACL review is
not a changed factor in this study.

A model-chosen tool outside its presented shortlist is a retained protocol violation;
never silently replace it with an allowed tool. The first paid-call or parse failure
stops the campaign and leaves remaining slots unattempted. Local plan/query failures
are recorded as outcomes rather than repaired. All reservations remain consumed.
A stronger model succeeding without a checker is a valid outcome, not a reason to
manufacture more errors.

## Bounded proposed campaign

- 6 new requests plus 2 repeated requests, 2 models, 2 paid prompt conditions:
  **32 maximum API attempts**, including failures, no retries.
- C derives from B: **48 condition records**, not 48 independent model samples.
- New shared nonrefunded ledger across both models, proposed **USD 5** cap and an
  immutable **two-hour** window starting only after new human authorization.
- Complete prompt/maximum-output reservation preview: **USD 3.5458150**, using twice
  full UTF-8 request bytes plus framing allowances and the output ceiling at frozen
  rates. This is not an actual model tokenizer count or expected invoice. Unknown
  billing stops the shared gateway; actual costs and usage are retained separately.
- No AWS startup, GPU, server restart or publication. Actual graphs are local RDFLib
  selected views, using fixed templates. This is not a Neo4j/Neptune performance study.

No permission is inferred from old unused budgets. At preparation the gate was false and its deadline null. The authorized run is now complete and all execution gates are closed. After explicit scope approval, the coordinator must bind the
approval record, start/deadline, frozen runtime inputs and independent review/check
receipt before opening the one-launch gate. Recheck endpoint prices/availability
before launch if the saved registry information is stale. Failures, interruptions
and expired windows never trigger automatic resume or a new window.

## Implementation artifacts

- `experiments/query_contracts/model_selection.py`: identical control prompts,
  full/retrieved candidate packets, strict response parsing, raw/checked plan pairs.
- `experiments/query_contracts/model_campaign.py`: closed preparation, shared ledger,
  immutable-window checks, per-call gate reuse, checkpointed slots and final closure.
- `research/query-contracts-1/model-selection-001/`: new runtime questions, model
  registry configuration and separate posthoc intention rubric.
- `scripts/query_model_campaign.py`: prepare or execute an already approved scope;
  it has no automatic authorization command.

Existing [lexical selection diagnostic](query-contracts.md) remains separate.

## Preparation verification

Independent methods and implementation reviews completed under job
`20261113T070615Z-query-model-selection-1070b7`. Registered offline checks passed:
query-contract-tests (22 tests, exit 0) and factory-campaign-tests (10 tests, exit 0).
The scripted gateway checks exercise shared reservation accounting and stop-on-malformed
responses; they do not verify real provider behavior or model accuracy.

For stopped episodes, use checkpointed progress and the call ledger together:
the Store run status can remain queued after a call/parse failure. No result should
be inferred from Store status alone. At preparation, provider acceptance and billing were untested. The completed calls now provide recorded parameter acceptance and reported usage, not independent invoice verification.

## Observed model comparison

All 32 calls completed, with no failed or unattempted slots and no unresolved costs.
Provider-reported cost was USD 0.251945925; nonrefunded reservations were USD 3.5458150.
All returned the requested model through Google AI Studio with finish reason stop.
The two-hour window started at 07:16:11 UTC; completion did not authorize further calls.
The first CLI invocation failed before import/API activity because the repository root
was absent from the module path. Setting PYTHONPATH to the repository root launched
the unchanged reviewed code; this was not a retry of a model request.

Primary results exclude the two repeated requests. Each row covers six authored
compound requests and 16 supplied task obligations, including three unsupported tasks.

| Model | Catalog | Intended tool selected | Correct unsupported-task null | Required task left unselected | Wrong tool selected |
| --- | --- | ---: | ---: | ---: | ---: |
| Hydrogen | Full six contracts | 13 | 3 | 0 | 0 |
| Carbon | Full six contracts | 13 | 3 | 0 | 0 |
| Hydrogen | Retrieved top three | 12 | 3 | 1 | 0 |
| Carbon | Retrieved top three | 12 | 3 | 1 | 0 |

Both retrieved-catalog nulls concern the same request m06, all_records: find O18
replacement candidates and inspect their complete qualification histories. The full
catalog contains qualification_records. BM25 top-three excludes that contract for this
task while presenting date-filtered alternatives. Both models decline to substitute a
partial history. Thus the end-to-end missing coverage originates in candidate retrieval;
it is not evidence that either model reasoned incorrectly about the supplied choices.
The evaluator's unnecessary_null category is relative to the full available service
catalog and must be read together with required_tool_missing=true.

All eight original/repeat pairs retained the same selected tool/null sequence. This
checks choices only, not identical explanation text or general reproducibility.
The selective contract checker vetoed zero steps, so it neither improved nor worsened
selection here. It cannot restore a contract omitted before model selection.
Actual fixed RDFLib execution made 102 query calls across raw and derived conditions,
with zero recorded query failures. These include repeated/paired work and are not
102 independent business questions or a database performance benchmark.

The result supports prioritizing candidate coverage and explicit fallback design for
the next diagnostic. It does not establish that a stronger model is generally useless,
that ontology/SHACL is unnecessary, or that answer quality is solved. Decomposition and
bindings were supplied; no final business answers were generated. Do not tune and then
reuse these six questions as fresh evaluation.

Saved public artifacts are under
research/query-contracts-1/model-selection-001/results-001: progress, exact-tool rubric
summary and call metadata. Private raw responses remain private, with their hashes in
call metadata. Original selections, nulls, graph outputs and repeats are preserved.
