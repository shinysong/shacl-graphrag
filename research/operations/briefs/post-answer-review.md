# Post-answer advisory review diagnostic

User requested three hours of offline research following explicit change to final/intermediate-checkpoint SHACL use. No new paid calls, infrastructure or publication. Deadline2026-11-04T04:48:53Z.

Review scripts/post_answer_review.py, tests/test_post_answer_review.py, research/post-answer-review-1/protocol.json. Main owns implementation. Read-only; do not execute source, edit code, inspect secrets, evaluation targets, historical raw model answers or other reviewer outputs. Return own review JSON only.

The typed packet is manually/explicitly supplied and NOT an automatic NLP extraction. Atomic recorded claims bind source_id/field/value/unit; selected source fields have locators. Both engines share input validation/applicability gating; unknown for unavailable evidence/value/unit; derived claims entirely not-applicable. Exact JSON scalar policy preserves type/lexical differences; no conversion, physical rule or external truth. Python checks source admission and scalar equality; actual pySHACL checks admitted membership or hasValue and maps per-check results. Nothing rewrites answers or fetches new source. Raw graph/shapes/report retained in result. Passing does not verify question relevance or completeness. Zero-check raw conformance is not successful answer.

Protocol names no-report/Python/SHACL on same draft and evidence, future report-only versus revision plus self-review equal-budget controls. Current work only offline software diagnostic. Eleven unit test methods passed before review; coordinator reruns after review. Registered checks empty; manual receipt retained. Report blockers precisely. Native distinct methods and implementation reviewers required; omitted external facts unverified.
