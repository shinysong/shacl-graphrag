# 2026-11-24 — Chat history and viewport boundaries

## Context

The workspace question screen became a chronological conversation while retaining original execution records and the existing request-recovery controls.

## Incident

Parallel read-only history requests intermittently failed because the local server serializes workspace operations with a nonblocking shared lock. A summary placeholder could therefore appear instead of an older question. Separately, the expanded recovery panel pushed the mobile composer below the viewport during an active request. Full-page screenshots and horizontal-overflow checks did not detect the vertical usability failure.

## Lesson

Read-only requests can still contend for an application lock. Hydrate a bounded number of saved turns sequentially and keep an explicit load action after failure. Validate the composer's actual viewport bounds in idle, pending and completed states. Preserve prominent recovery for unknown requests; only the exact foreground chat request can use compact recovery details when its actual progress and cancellation remain visible in the conversation.

## Follow-up

- [x] Preserve the original question, answer, version, unresolved items and execution details.
- [x] Check desktop and mobile composer bounds, Enter submission, Shift+Enter, pending progress and display-only new conversations using an isolated local service and a fake model.
- [x] Check that polling failures appear in the pending message.
- [x] Verify the public screen with saved records and no paid requests.

These are software and interface checks. They do not establish answer accuracy, successful business-query selection or multi-turn model memory.
