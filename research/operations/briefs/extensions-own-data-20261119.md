# Own-data registration and compact query screens

Review new apps/factory_lab/document_sources_cli.py,
tests/test_workspace_document_cli.py, and
examples/factory_lab/extensions/registered-commerce/create_example.py.
Also review the latest presentation-only workspace.js/css edits: collapsed
terminal request history after active workspace while recovery remains prominent,
selected relation identity/catalog disclosure, paragraph hash disclosure and
mobile dependency identifiers. Inspect private query-contracts/query-screen-design.md
and implementation notes when available, not other review outputs.

Existing query browser run162508717481 passed two viewports BEFORE these UI edits;
it does not verify the current UI. New actual browser execution is required.
CLI seven preliminary tests and root public example registration smoke passed;
independent reviewers did not run these. Preserve earlier failure records.

Check snapshot bindings, immutable bytes, redacted errors, no implicit approval,
no paid/network calls, own-data usability, recovery visibility, exact saved relation
identity and unchanged selection/execute semantics. Public example is synthetic
180 rows/three tables/two text documents; no real-domain correctness claim.

Reviewers read only their own packet/source, write only own result; no secrets,
posthoc gold, other reviewer outputs or source edits. Registered workspace-tests
and research-ops-tests cover local software; actual browser and example CLI evidence
remain separate. This increment does not finish missing query operators or goal.
