# 2026-10-27 — Teaching schema and slide consistency

## Context

A presentation replaced a sensor example with a small manufacturing example while preserving earlier teaching artifacts.

## Incident

The slide defined `installedIn` with domain `Component`, but the copied runner initially retained `Fastener`. The chosen individual was a `Bolt`, a subclass of `Fastener`, so the displayed query results matched despite the definition mismatch. Independent source reviews caught it. The corrected runner uses `Component`; original outputs remain under the ignored revision workspace.

## Lesson

Matching example outputs do not prove that a diagram and an executable schema declare the same semantics. Compare the declared predicates, domain/range and class hierarchy directly, as well as the result values.

## Follow-up

- [x] Align the runner and teaching definition; regenerate the tiny example.
- [x] Preserve the original attempt and request a fresh review after the source change.
- [x] Keep historical research and the earlier sensor artifacts unchanged.
