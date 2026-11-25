# Exact product aggregation in reviewed queries

Review the sum_product increment in workspace_query_contracts.py and its tests,
workspace_query_service.py capabilities, workspace_query_catalog tests, and
workspace.js aggregate editor/spec/result display. Preserve previous v1 artifacts
and fingerprints. New product specs need explicit two approved root fields,
integer arithmetic, null policy and reviewed unit annotation. No arbitrary SQL.

Check complete-snapshot operand types, root grain, joined multiplicity, signed64
product/final-sum bounds, null union and diagnostics, empty/all-null groups,
serialization across JavaScript safe-integer limits, dependency invalidation,
time/work/output bounds and separate approval/execution. Product arithmetic is
not policy correctness or external truth. UI must not round exact results.

Also inspect private query-contracts/domain-configs/bind_config.py and modified
commerce-medium.json against the original runtime question, plus the NEW
run_product_case.py. Only commerce-medium-2 is newly executed; prior25 outcomes
remain unchanged. Original configuration is retained in domain-configs/before-product.
No posthoc/expected outputs are allowed in runtime or this review. The runner
uses full immutable registered DB, a byte-bound policy paragraph, scripted reviews
explicitly labeled as such, and durable attempts/failures. No model calls.

Native implementation preliminary tests are not formal gates. After both reviewers
ready, registered workspace-extension-pytest and research-ops-tests run, followed
by the actual narrow source case. Browser sum_product coverage requires a separate
actual test; old sum browser acceptance is not evidence for the new operator.
Scalar binding and directed reachability remain incomplete and in full scope.

Read-only reviewers write only their own result, never other reviews, gold,
secrets or source. Preserve any blocker; no automatic retries or budget resets.

Also inspect NEW _workspace/extensions-20261119/query-contracts/browser_product_acceptance.py: UI-only five field approvals, saved policy/FK, sum_product proposal/separate approval/explicit execution, decimal-string display against independent small-source SQL only AFTER runtime, 1440/375, retained failures. No paid calls. Reuse original harness unchanged. This narrow browser test is required after gate, not evidence until actually run.
