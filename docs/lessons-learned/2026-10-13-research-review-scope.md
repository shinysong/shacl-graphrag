# 2026-10-13 — Research review scope and copied outputs

## Context

The researcher-side operations runner was tested against OpenRouter with a total
verification ceiling of $0.10. This tested planning, independent review, execution
gating and local software checks, not a new QA experiment.

## Incident

Four live jobs made 17 calls with reported usage cost $0.0042561 and no missing
cost reports. One job completed the original control flow and local checks, but
its reviewers and analyst repeated the coordinator's plan. The analyst did not
describe the supplied check results. A completed status was therefore insufficient
evidence of meaningful review or analysis.

Other jobs stopped at review gates. The methods reviewer treated acknowledged
historical cohort reuse as a blocker for running unit tests. Another review used
the analysis-only decision `observe`, causing execution to remain blocked. These
were task-scope and output-contract problems, not evidence of a new data defect.
All original attempts were preserved.

## Lesson

Give each worker only the background relevant to the current task. Specify the
current stage explicitly, and validate stage-specific outputs in code. A model's
agreement and a successful API response do not establish review quality.

The runner now rejects a reviewer that copies the plan verbatim, rejects `observe`
before analysis, and requires analysis to use `observe` and mention supplied check
IDs and exit codes. These checks enforce output obligations, not scientific truth.
The local verification task now uses a separate software-only context packet.

## Follow-up

- [x] Retain live attempts, costs and the earlier completed run's limitations.
- [x] Add regression tests for copied reviews and stage-specific decisions.
- [x] Pass the final offline control flow, 45 unit tests and synthetic local check.
- [x] Complete a live run of the final narrowed packet and hardened runner.
- [ ] Evaluate review usefulness on deliberately flawed plans before relying on
  automatic research approval.

The final narrowed live run `20261013T010333Z-local-verification-088b3d`
completed five calls at reported cost $0.00090225. It ran 45 unit tests and
`e0-local`, both with exit code 0, and analysis correctly reported those results.
The reviewer outputs were still generic approvals; their usefulness for detecting
research design defects remains unmeasured. Total verification usage across the
five preserved jobs was 22 calls and $0.00515835, within the approved $0.10 ceiling.

## Accumulated review packet size

The animation source review fit the 28,000-byte request limit, but adding both
reviews exceeded the limit when requesting synthesis. The original job
`20261013T055109Z-animation-review-354b52` remains preserved. A fresh job supplied
the same full JavaScript and visible explanatory prose while omitting HTML markup
and CSS; reviewers explicitly treated omitted rendering facts as unverified.
Separate browser checks covered those facts. Leave room for downstream review
outputs when sizing the initial packet; do not increase limits or silently truncate
evidence to force a completed record.

## Stop dependent shell actions on recorder failure

During the GLEIF development launch, both reviewers returned ready, but the
synthesis request exceeded the accumulated packet limit. A multi-line shell
command lacked fail-fast handling, so the deterministic development runner still
executed. Its run and the failed recorder state are preserved; no model calls
had occurred at that point. A smaller fresh packet, independent reviews and
registered tests completed before the model smoke. Keep dependent launch actions
in separate checked tool calls, or use explicit fail-fast chaining. Do not describe
a later completed gate as having preceded the earlier deterministic execution.
