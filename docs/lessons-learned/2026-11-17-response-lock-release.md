# 2026-11-17 — Response delivery and execution locks

## Context

Factory Lab serializes preparation and workspace mutations with a local execution lock. A client can send its next request as soon as it receives the previous response.

## Incident

A preparation HTTP regression expected session closure to return 200 but received 409. Source inspection showed that the handler sent response bytes while holding the lock and released it only afterward in `finally`. This permits a subsequent request to arrive before cleanup finishes. The failed check remains recorded; the failure alone does not measure how often this interleaving occurs.

## Lesson

Freeze response bytes while shared state is protected, release the lock in `finally`, then perform network I/O. Serializing after release could instead expose a mutable result to another operation. A client delay or automatic retry would hide the ordering problem.

## Follow-up

- The preparation/workspace routes now serialize before release and send afterward, including expected validation errors.
- An HTTP test checks frozen response bytes and an unlocked state at send time for success and validation-error paths. The existing concurrent-request test retains the active-execution rejection check.
- This scoped correction does not establish throughput, resource capacity or correctness of other HTTP routes.
