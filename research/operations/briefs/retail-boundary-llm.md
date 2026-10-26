# Frozen boundary LLM execution

Review scripts/retail_boundary_llm.py and unchanged nl2shacl_multimodel.py runner.
Current human-authorized144calls/$5campaign already consumed48; execute the28
frozen boundary inputs with same model/settings, preserving original ledger.
No new budget: hash-bound predecessor48 included in campaign count/cost;
all historical campaign ledgers included in UTCdaily500. Stop mode, no retry.

Frozen boundary inputs came from reviewed offline14row diagnostic:2purposive
source cases plus12authored probes with opaque IDs. The preparation checks
source cases against earlier24selected rows to avoid renaming consumed cases.
Runtime inputs contain no reference labels or selection rationale. No heldout.
References stay scorer-only and source/authored metrics must stay separate.
All bad model decisions/schema failures remain outcomes; no repair.

After both independent reviews ready: main runs prepare, manually inspects
frozen prompt/hash/predecessor binding, discovered historical ledger set/count,
reservation upper sum and combined budget. Launch exact unchanged runner with
new boundary config/inputs/output and --limit4. Inspect only model identity,
transport/cost/format; continue --limit24 if operationally resolved, never use
correctness to gate continuation. Then evaluate saved outputs, preserve failures.
No source changes after review, no additional infrastructure, no push.

Reviewers: static review only, no tests/API/secrets/heldout or existing reference
labels/model answers; own review output only. Main reports actual exit codes,
costs and split metrics, no generalized business accuracy.
