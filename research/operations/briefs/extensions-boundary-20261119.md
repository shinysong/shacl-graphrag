# Optional extension import and SQLite source boundary

This is an intermediate software review, not completion of the full extension goal.
Scope: neutral native-auto YAML import with raw retention, pending status, unresolved/unsupported reporting and nonauthenticated producer identity; durable WorkspaceService extension_import action preserving existing draft approvals; trusted-operator SQLite source registration, whole-source backup including WAL, bounded inspection and parameterized lookup, drift observation.

Reviewers may read ONLY the following source/test files in addition to this packet; do not read other reviewers, secrets, history or evaluation gold. Files are frozen by SHA256 below. Tests are authored software fixtures, not semantic-quality evidence. Read actual implementation before recommendations.

{
  "apps/factory_lab/workspace_extensions.py": "925592a02ea427ed7298e224f35f6ec690f7f462614164275341e637c1c872ec",
  "apps/factory_lab/workspace_database.py": "54e03ad7fd2307db43bb39fc32ac52f11a1aa3cb8307227444903e7ea0f50535",
  "apps/factory_lab/workspace_service.py": "9375738dac6e9fa261b2b5ab32480aacc123718d8e5257233e36a7bf5100b0d1",
  "tests/test_workspace_extensions.py": "047bfa64da49363b50205124022788229d85011b3f5f7005ace7c83f7b94a2c5",
  "tests/test_workspace_database.py": "64e09b0c195966752a674a67c47eea41cd217de745a77d08ea459a02e54a6e0d"
}

The registered workspace-tests invokes unittest discovery over test_workspace*.py and includes new unittest classes; research-ops-tests checks gates only. Existing tests elsewhere are regression inputs, not new efficacy experiments. Reviewers may inspect WorkspaceStore/preparation/workspace_lookup to resolve the new service path, but treat uncovered behavior as unverified.

Expected invariants: untrusted exports cannot confer approval or execute SQL; raw failed inputs retained; exact request-key idempotency; stale revisions not executable; historic results readable; SQLite paths operator-only, public outputs opaque, identifier catalog allowlisting, no arbitrary SQL, whole table counts and rows beyond200 available, samples bounded, snapshots immutable/read-only, source drift distinguished from saved snapshot.

Observed separately: actual pinned auto-ontology migrations, catalog ingestion of synthetic180rows/3tables/10columns and official YAML export completed without model/embedding calls. Root standalone converter read that actual catalog export:5 catalog concept objects/10 fields/2 physical relations,0 unresolved,4 unsupported,pending. This is NOT semantic compilation, human approval, UI evidence, or domain-general accuracy. Semantic compilation, real OpenOntologies runtime, browser flows, DB integration into workspace and 3small/2medium trial completion remain pending.

open_ontologies_runner.py is an unintegrated prototype and excluded from this review; no execution or approval claimed. Build is live. No paid execution is authorized by this job. Check source hashes before tests and create a fresh job after changes.
