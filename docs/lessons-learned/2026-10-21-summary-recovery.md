# 2026-10-21 — Recovering a report without repeating measurements

## Context

The technology-selection maintenance check evaluated 15 isolated submissions against 96 frozen expected outputs. Each output and its process log was persisted before summary generation.

## Incident

All 96 outputs matched, but the checker then exited with code 1: its hash helper received the string `__file__` and attempted to call `read_bytes()` on it. The original failed invocation and raw results were retained. After changing the helper to use `Path(path)`, a separately reviewed `--summarize-only` path reconstructed the missing summary from saved outputs and checked their correspondence to the recorded rows. Recovery exited with code 0 and launched zero new workers.

The original checker failure remains distinct from the passing implementation outputs. See the [maintenance record](../experiments/records/20261021-technology-selection-maintenance.json) for both review jobs and outcomes.

## Lesson

Before retrying an experiment after a reporting error, check which outputs were already saved. If those records are intact, validate and summarize them without repeating the measured work or changing the original failure status.

## Follow-up

- [x] Preserve the original exit code, logs and saved outputs.
- [x] Review the summary-only recovery separately and record zero new workers.
- [x] Distinguish reporting failure from implementation correctness in the paper.
