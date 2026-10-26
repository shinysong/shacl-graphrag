# 2026-10-26 — Separating measured results from illustrative constants

## Context

An offline lifecycle diagnostic was summarized as a complete compilation, real-data transfer, maintenance and LLM workflow. A subsequent independent methods and implementation audit compared the manuscript with the executed functions and saved aggregate.

## Incident

The reported GLEIF transfer values were constants without source loading or engine evaluation. Syntax-success counters were incremented without syntax checks. Provenance implementation line counts were literal values, and an empty cardinality-result value was counted as populated. Historical LLM scores were attributed to new prompts that had never been sent to a model. Illustrative snippet differences were described as actual source modifications.

## Lesson

Trace every metric to its executed measurement and denominator before using it in prose. Preserve unmeasured quantities as null or explicitly unexecuted, and distinguish a proposed interface from an observed model response. A passing software test cannot validate a metric that only asserts a constant.

## Follow-up

- [x] Preserve the original aggregate and initial blocker reviews.
- [x] Separate nonempty report values, snippet differences and physical function spans.
- [x] Withdraw unexecuted transfer, compilation and provenance-cost claims.
- [ ] Evaluate matched structured-report baselines only under a separately authorized study scope.
