Final bounded offline integration audit. No implementation changes. Review the listed existing test files for local-only execution and coverage/claim limits. Authorized reads: listed tests, imported rule_workbench modules, scripts/profile_public_domains.py and scripts/industrial_source_snapshot.py, apps/rule_workbench.py. No secrets, gold or other reviewer outputs. Run all listed tests together using uv run --locked --group workbench python -m pytest. No network/paid APIs, new databases, server restart, site publish or push. Preserve any failure; no scientific efficacy claim. Passing tests only show covered software behavior, not production readiness or independent real-world accuracy. Existing browser and 101-page site checks remain historical, not rerun.

tests/test_workbench_core.py
tests/test_workbench_connectors.py
tests/test_workbench_ui.py
tests/test_workbench_linkage.py
tests/test_workbench_linkage_consistency.py
tests/test_workbench_linkage_config.py
tests/test_workbench_linkage_ui.py
tests/test_workbench_provenance_roundtrip.py
tests/test_workbench_reference_scope.py
tests/test_workbench_domain_ui.py
tests/test_workbench_term_ui.py
tests/test_domain_candidates.py
tests/test_term_candidates.py
tests/test_public_domain_profile.py
tests/test_industrial_source_snapshot.py