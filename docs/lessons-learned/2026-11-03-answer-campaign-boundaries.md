# 2026-11-03 — Generator names, artifact bindings and answer denominators

## Context

A bounded final-answer campaign used 24 consumed development questions under B/C/D, with 72 attempts and a $1 ceiling.

## Incident

Independent review caught an OpenRouter-qualified model name being passed to the tokenizer registry before execution. The runner was changed to explicit `o200k_base` while preserving the API model name. A fresh review and offline preflight preceded every paid attempt.

The first aggregation review also found that unique episode IDs alone did not prove a 24-question × three-arm universe, and that equal costs did not establish response identity. The revised aggregator checks the full question/arm product, target uniqueness, frozen inputs, saved request equality, raw answer equality and missing resolved artifacts.

One actual D response returned an array where the answer schema allowed only a scalar. Its original text and cost remain preserved; it was not repaired or retried. A different D response supplied the correct target label with a wrong codebook row. All cited IDs belonged to the selected chunks, which did not prevent incorrect joins or locations.

## Lesson

Keep provider model identifiers separate from tokenizer identifiers. Bind summaries to immutable requests and responses, not just costs or counts. Count format failures separately from withholding, and target-value agreement separately from citation correctness.

## Follow-up

- [x] Preserve failed review jobs, the schema failure and all 72 attempts.
- [x] Obtain fresh independent reviews after runner and aggregation changes.
- [ ] Use fresh questions and independent semantic adjudication for a confirmatory comparison; the present campaign does not supply either.
