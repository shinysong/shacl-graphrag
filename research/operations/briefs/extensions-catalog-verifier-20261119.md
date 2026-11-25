# Actual catalog driver environment correction

Review only the private `_workspace/extensions-20261119/generic-auto-bridge/run_catalog_acceptance.py`
environment correction. It previously selected upstream/.venv, which lacks dotenv;
actual-20261119T154158Z preserves that bootstrap failure and stopped-container
cleanup. The second case was unexecuted, not a success. The corrected executable
is `_workspace/extensions-20261119/auto-venv/bin/python`, the separate managed
environment used for previous actual native calls. Isolated import of dotenv and
the pinned upstream package succeeds at the expected source path.

Application source and tests are unchanged from completed independent gate
20261119T153915Z-extensions-native-usability-a2bb70: workspace-tests exit_code 0,
167 tests/one opt-in skip, research-ops-tests exit_code 0. Subsequent actual generic
ten browser cases and OO two viewport cases passed. Do not rerun the workspace
suite solely for this private executable-path fix. Registered ops check remains.
The private driver deliberately receives that existing product review-job ID;
root must also complete this new verifier review before execution.

Inspect the driver, original failure's safe summary/cleanup and current bridge
source as needed, not private credentials, other reviewer outputs or posthoc gold.
No API endpoint/gateway is configured, only catalog mode. Require named owned
service initially stopped, loopback-only publication, bounded readiness, two
different registered source IDs and finally cleanup. Actual exported inventories
must be compared with source schemas before acceptance; output success alone is
insufficient. Keep initial failure, failed retries and second-case skips explicit.
Bridge per-file and wall limits do not constitute aggregate memory/disk isolation.
No semantic-model generation, own-data policy interpretation or full-goal completion
claim follows from this catalog check. Reviewers write only their own result.
