# 2026-11-24 — Reservation settlement and reported costs

## Context

The shared workspace used the same conservative spending boundary as earlier bounded research campaigns. Each native chat call reserved the full documented model context and output ceilings. The gateway retained that reservation after successful calls, even when the provider reported a much smaller cost.

## Incident

An example SQLite semantic-generation run stopped at the local reservation limit. The native ledger contained 39 completed provider attempts, $9.6341 in cumulative reservations and $0.01367171 in reported costs. Another chat required a $1.20 reservation. This was a local accounting refusal, not evidence of an exhausted provider account. A partial upstream export was retained without being imported or approved.

## Lesson

Use separate concepts for an in-flight hold, a successful response's reported cost, and an unresolved liability. An explicitly selected settlement policy may release the unused portion of a successful, cost-known response. Failed responses and missing, invalid or unconfirmed costs retain their full holds. HTTP 200 alone is insufficient: a provider-error payload must also fail and stop native retries. Reserve atomically before transport so concurrent requests cannot spend the same remaining allowance.

An explicitly authorized reservation reset must preserve the predecessor ledger and its hash, carry historical costs and attempt counts into the new accounting epoch, and keep the campaign's total ceiling and deadline. The reset procedure supports the inspected first-reset case only; it is not a general ledger migration service. A process interruption during the multi-file migration requires operator inspection.

## Follow-up

- [x] Keep fixed, nonrefunded reservation accounting as the default for historical research protocols.
- [x] Add explicit successful-response settlement, conservative unresolved holds and provider-error checks.
- [x] Verify concurrency, inherited-cost accounting, configuration binding and native retry stopping with offline tests.
- [ ] Reconcile each deployment's actual migration and generation receipts before claiming that its connection works. Software tests alone do not establish semantic mapping quality or provider invoice accuracy.
