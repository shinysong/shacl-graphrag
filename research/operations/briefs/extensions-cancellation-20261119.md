# Cooperative execution cancellation
Review actual source changes for local_reasoning/database_reasoning_execute/database_query_execute. Optional callbacks preserve existing signatures; durable cancel request does not optimistically imply stopped. Native subprocess owns its session, kills/reaps on cancellation/timeout/callback exception, preserves partial receipt. SQLite VM and Python traversal check cancellation; preparation/snapshot restoration is not interruptible until it returns. UI polls and retains request keys/server terminal status. No paid/model/AWS or efficacy claim.
Read listed source plus relevant tests/dependencies. Do not read secrets/gold/other reviewer outputs. Independently inspect lifecycle races, replay, partial evidence, process cleanup and original limit preservation. After both ready run workspace-extension-pytest and research-ops-tests. Then bounded actual pinned OO cancellation smoke: 500-class authored RDFS chain (<64KiB), max10s, callback requests stop after0.15s since first callback (prelaunch returns false). Record actual process_started/reaped/exit, raw receipt and elapsed. A completion race is not cancellation success. Private script must be inspected before execution. Browser cancellation remains separate pending verification. Full goal incomplete.
- apps/factory_lab/open_ontologies_runner.py SHA256 68e37378fb16d5ff1ea1938ced347297153beac43945764ab0afef166030b73e
- apps/factory_lab/workspace_reasoning.py SHA256 85e3e7056845ab5555e88f91ea36cd642e278a9d0945ff34fca6e87583d12eb1
- apps/factory_lab/workspace_query_reasoning_service.py SHA256 b426dec5a1f97692b9cf4fd9d42e44ad9422bbfc92b188b2515b8fc756245ac0
- apps/factory_lab/workspace_query_service.py SHA256 67f1fdb10bf6d28a2e994a5fed3bb8ee115d0c842d9239bb45666897c47e7cc1
- apps/factory_lab/workspace_query_contracts.py SHA256 419b7300eec0a8096edb87659a3bec516a8b0f55aeda0c140404800dd739e66d
- apps/factory_lab/workspace_query_reachability.py SHA256 209f0166f123c1683a67d3827eb8ea2ff640c9e907e0d751b51691b259d2fbee
- apps/factory_lab/workspace_store.py SHA256 dd6b38a877905e69134572a8e6da2ff0afa3d3c9119b2a7b5deeb5bf518d1f3c
- apps/factory_lab/public_static/workspace.js SHA256 8e5150a69214077ad2eb1f4959cdd5a875a70d769ce07321e01d55b20fc07d4f
- tests/test_workspace_execution_cancellation.py SHA256 70e4d7c06c7e033235199e55fafaaae8f59ff0fe2d6cc150da7ebdf795ed78ce
- tests/test_workspace_reasoning.py SHA256 369d179ded290a584bad94be45a7ed649d4dbdc16cac1c14911e15323b2e9bce
- scripts/research_ops.py SHA256 2bdaff4fd2c9d04cab28fe315c232a771fbd6426a840e710ceb9e024e7f25afc
- tests/test_research_ops.py SHA256 b8a20003874405a30cb6aad8c1c83e37cc2fc7ebe40a43d4edf99956715fb777
- _workspace/extensions-20261119/actual_native_cancel.py SHA256 b972abc0b89296a98c746c9a6b768cd718d4c31ae730f3c7d1e1990128f2ca5a

Prior a1026d both revise preserved. Removed post-wait cancellation polling. Actual termination cause/signal_sent/signal recorded and native smoke requires SIGKILL exit -9 with cancellation cause. Added deterministic naturally failed child/late callback regression. Trusted binary no-surviving-descendants assumption documented; no cgroup guarantee.
