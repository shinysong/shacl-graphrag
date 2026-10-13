# 2026-10-13 — Research operations backend and experimental model costs

## Context

The user requested researcher-side orchestration using Codex subagents while
keeping experimental QA on OpenRouter. The initial operations runner also used
OpenRouter for planning and reviews, adding a second API cost path. That was an
implementation choice; it was not required by the experiment architecture.

## Incident

The implementation and explanation initially failed to make that distinction
clear. A daily limit of 100 operations requests did not change the experimental
QA budget or the Codex account's usage allowance. The earlier API verification
made 22 calls at reported cost $0.00515835; all original attempts and costs remain
under ignored `_workspace/research-ops/`.

## Lesson

Choose the backend separately for research operations and experimental inference.
Use the active Codex session and native subagents for planning, code work and
independent review. Keep OpenRouter solely in the existing experimental runners.
Do not replace native collaboration with a paid API worker when it is unavailable.

The migrated helper freezes task packets, records logical role requests and
results, enforces independent reviewer attribution and blocker gates, and runs
only registered local checks. It has no model transport. Agent IDs are recorded
operator annotations, not authenticated identity. Shared workspace access requires
review instructions and audit; it is not a security sandbox.

## Follow-up

- Preserve historical requests, unsuccessful attempts, costs and prior limitations.
- Count at most 100 logical requests per UTC day and 7 per job. Do not describe
  these counts as Codex token/account limits or enforceable monetary budgets.
- Verify actual native reviews and local checks, including a deliberately flawed
  proposal with no real evaluation answers supplied.
- Document measured software behavior separately from scientific reviewer quality.

Native verification completed the registered checks with 44 unit tests and
`e0-local` both successful. Separately dispatched reviewers each found four
blockers in the deliberately obvious proposal. Its execution gate rejected the
job, and no checks ran for that proposal. This is one disclosed known-defect smoke
check, not a blinded reviewer benchmark or proof of general scientific judgment.
No new OpenRouter model calls were made during migration.
