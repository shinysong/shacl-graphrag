# External semantic field and relation adoption gate
Problem: imported actual upstream relations were inert and lacked explicit approval/query provenance. Implement saved current import resolution, reviewed endpoints/meaning, separate relation approval, fixed typed query reuse. Existing physical FK and unique parent checks remain. No raw upstream SQL execution. Rejection is candidate selection only: does not invalidate previous pending or approved artifacts; explicit reproposal remains possible. UI must disclose that limitation. Origin is reconstructed from persisted bytes and bound revision on every use; no producer/input authenticity attestation.

Read the frozen source files listed below, parent workspace_service.py for dispatch/withdrawal, and actual runner. Review independently with no other reviewer outputs or gold. Registered checks workspace-extension-pytest and research-ops-tests; run only after both independent reviews and synthesis ready. Then coordinator executes frozen run_actual_adoption.py with gate record in unique owned directory. No model calls, infrastructure, publication or paid budget change.

Actual runner reuses exact original commerce-small DB and actual semantic native-export hashes, approves five source fields, edits/adopts actual Quantity annotation, reloads revision, reimports same bytes, rejects duplicate physical relation, edits semantic FK pending -> approval -> grouped delivered-order quantities query -> approval -> execution. All mutations replay after service restart, raw outputs precede checks. Scripted approval is software acceptance, not independent human meaning validation. No gold answer scoring. The source snapshot can differ bytewise from original due SQLite backup; retain both. Browser adoption is later separate task and remains unverified on current UI. Full goal remains incomplete: missing-evidence workflow, OO source-bound reuse, full docs/audit still required.

Source-only context: _workspace/extensions-20261119/external-relation/runner-interface.md and _workspace/extensions-20261119/relation-service-frozen.json. Actual inputs paths are in runner, no secrets. Preserve preceding failures; no rerunning model generation.

- `apps/factory_lab/workspace_extension_relations.py` SHA256 `1702e65b3f51f0c34b885b33a3ddd8ba86cd523a6d3b7dfc07b7074279b31cda`
- `apps/factory_lab/workspace_query_service.py` SHA256 `bf649e3577bfffcd2b73d25e15044710c860c7ac10ce63ebb3cd2a151e59ebf9`
- `apps/factory_lab/public_static/workspace.js` SHA256 `d8427541a9b6418a9a7f1378da42c7d322616e0f160289f238e702d15b54d0aa`
- `apps/factory_lab/public_static/workspace.css` SHA256 `c2ab75d7af7813918caa3ab11f90af57c492903880f5780edde47e511655317b`
- `tests/test_workspace_extension_relations.py` SHA256 `77baf210cc950fd642fd6194ecb6c781ace4fd66e7d7c613b4f2572bd629fefa`
- `tests/test_workspace_external_relation_service.py` SHA256 `54f5d551cc1513fe326f619ca4ed455118828536194535e1eb59f400a1b13150`
- `scripts/research_ops.py` SHA256 `59a82eb6f1a67e4666e16b250ebac8e575702cc4efbc1380ee5b3372e4f47046`
- `tests/test_research_ops.py` SHA256 `e1d26a25a64f88d848a75993e8ec34de32912c2917ae379285c33bed4d611915`
- `_workspace/extensions-20261119/external-relation/run_actual_adoption.py` SHA256 `5a921a4ba24be0f7c6dbe8019b7e5971d8cb94a6c8b86da0dc02a563c0e0caa3`

Previous 0c1322 methods/implementation both revise: wrong rejection UI requirement. Correct both warnings and add pending -> rejection -> existing approval regression; previous review evidence preserved. No behavioral invalidation added.

93a061 was initialized prematurely: first string replacement missed 이후 versus 나중에; no reviewers dispatched/checks run. Both actual strings now corrected; retain abandoned request reservations.
