# 2026-11-07 — Resource cleanup and observed terminal states

## Context

A bounded manufacturing hierarchy comparison used an existing Neptune cluster and an owned temporary Neo4j container. Query results, data cleanup, resource deletion, and terminal shutdown were recorded separately.

## Incident

Neptune accepted SPARQL requests while its management API still reported `starting`. The initial stop requests were rejected. A later stop request was accepted at 17:25:54 UTC; terminal `stopped` was confirmed at 17:35:08 UTC. A readiness probe was therefore insufficient evidence that a management operation would immediately succeed.

The temporary container and its anonymous volumes were removed. The cleanup helper nevertheless reported `removal_not_verified`: it expected `No such object`, while this Docker invocation emitted `error: no such object`. The original foreground execution ended with a cleanup error after preserving all 992 result slots. This failure was retained rather than relabeled as successful.

A separately reviewed helper matched the exact owned resource name with case-insensitive error text. Its six controls covered both message cases, post-removal verification, an unrelated error, and a terminal receipt. An independent check confirmed the two owned volumes were absent. Only the owned stop timer and service were disabled after terminal shutdown was confirmed.

## Lesson

Keep query readiness, management-operation acceptance, and terminal resource state separate. A successful query does not establish that a cluster has completed its startup transition. A stop request does not establish completed shutdown.

Check the observed CLI response format in addition to mocked responses. Accept a specific absent-resource condition, not any failed command. Preserve cleanup uncertainty and retry bounded administrative recovery without restarting the experiment.

## Follow-up

- [x] Retained the original cleanup failure and separately recorded recovery.
- [x] Reviewed and checked case-insensitive matching for the exact owned container.
- [x] Confirmed terminal Neptune shutdown and absence of the owned container and volumes.
- [x] Removed only the experiment's owned stop guard.
- [ ] If a future run uses a different Docker client or backend, verify its response format before relying on the same helper.

Evidence: `research/manufacturing-model-change-1/subtype-live-001/` preserves the query denominator and namespace-cleanup results. Administrative receipts and native review records remain in the ignored workspace. This incident is not a DB performance or answer-quality result.
