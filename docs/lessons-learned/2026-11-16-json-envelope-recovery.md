# 2026-11-16 — Preserve model content during JSON-envelope recovery

## Context

The compound-query campaign stopped after two paid requests because the plan response enclosed otherwise valid JSON in a Markdown JSON fence.

## Incident

A strict JSON decoder rejected the transport envelope. The original stopped progress and billed attempts remained immutable. A reviewed manual continuation decoded one whole-response fence and reused the exact saved decomposition and plan responses. Reconstructed planning messages had to match the original paid request.

## Lesson

Separate transport-envelope parsing from semantic repair. Accepting a single whole-response fence must not modify model fields, choices or bindings, extract arbitrary prose, repeat requests or refund failure reservations. Keep the original denominator, deadline and stopped artifact alongside continuation results. This recovery is a post-failure amendment, not first-try experimental success.

## Verification

The independent recovery review passed 46 query-contract tests and 10 campaign tests. The real-Gateway mocked-HTTP recovery test verifies 24 total requests, reuse of the original two responses, unchanged parent progress and deadline, and shared nonrefunded accounting. Actual completion used two original plus 22 additional calls; no paid call was repeated.
