# Native Codex research operations

This is a procedure for the main Codex agent in an active session with native
collaboration tools. The Python helper records work; it does not dispatch agents
or make model API calls. Do not use OpenRouter, an OpenAI SDK, or a nested Codex
CLI to emulate these roles. If native collaboration is unavailable, report that
review is pending. The experimental QA runners remain on OpenRouter.

## Local job preparation

```bash
JOB_ID=$(uv run --locked python scripts/research_ops.py init research/operations/tasks/local-verification.json)
uv run --locked python scripts/research_ops.py request "$JOB_ID" plan
```

Read the emitted request, follow its role instructions, and write the common JSON
contract to its designated output path. Planning, synthesis and analysis are main
Codex tasks. Submit each with the real main session identity (for this session,
`/root`), not a fabricated model name. Follow command help for argument ordering.

```bash
uv run --locked python scripts/research_ops.py submit "$JOB_ID" plan /absolute/path/to/result.json --agent-id /root
uv run --locked python scripts/research_ops.py request "$JOB_ID" methods
uv run --locked python scripts/research_ops.py request "$JOB_ID" implementation
```

## Independent review dispatch

Use available native collaboration tools (`spawn_agent` in this environment).
Start methods and implementation reviewers as separate agents with
`fork_turns="none"`, inherited model settings, and only the respective request path
and designated result path. These two tasks may run concurrently. The packet
contains the plan but not the other review. Give reviewers a read-only instruction:
read their own request, write only their own result, do not inspect other review
folders, source secrets, held-out gold or historical raw QA answers. Shared
filesystem access is not an enforced isolation boundary.

Record each actual returned agent ID through `submit`. Do not create fixture
reviews to get a completed state. A copied plan is not an independent review.
Agent IDs supplied by the operator are recorded annotations, not cryptographically
authenticated identity. Native tool conversations retain the actual delegation.

```bash
uv run --locked python scripts/research_ops.py submit "$JOB_ID" methods /absolute/path/to/methods-result.json --agent-id /root/methods_actual_id
uv run --locked python scripts/research_ops.py submit "$JOB_ID" implementation /absolute/path/to/implementation-result.json --agent-id /root/implementation_actual_id
uv run --locked python scripts/research_ops.py request "$JOB_ID" synthesis
```

Main Codex preserves both reviews and their objections in synthesis. A blocker
stops local checks even if synthesis approves. A revised plan or changed source
requires a fresh job; do not reuse an approval for changed inputs.

## Registered checks and observed analysis

After submitting synthesis, run only the registered local checks:

```bash
uv run --locked python scripts/research_ops.py check "$JOB_ID"
uv run --locked python scripts/research_ops.py request "$JOB_ID" analysis
```

Main Codex reports every supplied check ID and exact exit code, separates software
verification from benchmark evidence, and submits analysis with decision `observe`.
`status` and `handoff.md` show recorded progress. Main Codex implements follow-up
code changes separately; reviewers do not modify code and JSON tasks never become
shell commands. A scoped implementation subagent may be assigned by main Codex
when the user-authorized work needs it, followed by fresh checks.

## Limits, failed attempts and continuation

Reserve a role request before dispatch. The repository tracks at most 100 logical
role requests per UTC day and 7 per job, including retries. These counts do not
measure internal model turns, tool calls, tokens or account-wide usage. No monetary
Codex cap is enforced or inferred. Up to 2 independent reviewers run concurrently.
Codex credentials and billing stay with the current session; the runner needs no
model API key. Experimental OpenRouter and AWS costs remain separate.

Inspect failed attempts before using `--retry` on request/check. Preserve older
request/result/log files and consumed reservations. Completed steps are reused.
The helper freezes task, roles, config, source/fixture hashes and static checks.
No paid QA run, database install, Terraform apply or Git push is a registered check.
Historical OpenRouter records and their budget ledger stay in
`_workspace/research-ops/`; new native records use `_workspace/research-ops-codex/`.
