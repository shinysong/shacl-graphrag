# Registered commerce example

Creates 180 authored synthetic rows in three SQLite tables and two UTF-8 policy
documents. No API calls, private customer data, or automatic approvals.

From the repository root:

```bash
uv run --locked python examples/factory_lab/extensions/registered-commerce/create_example.py --output _workspace/my-commerce
```

The output directory must be new. `manifest.json` records file hashes, source
counts, fixed example questions and limits. Generated records and text are
Apache-2.0, like the repository's own code. They are not a business benchmark.

Follow the [database and document registration guide](../../../../docs/setup/factory-lab-registered-sources.md)
to register the snapshot, bind its documents, and open an isolated workspace.
Use separate registry and server data directories from any existing installation.

The source deliberately lacks delivery dates and item condition. Recorded
delivered status is insufficient to decide return eligibility. Keep these missing
facts distinct from evidence a query failed to retrieve.
