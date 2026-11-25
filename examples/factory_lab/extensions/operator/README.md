# Local extension operator walkthrough

This walkthrough registers the authored commerce SQLite example, runs NVIDIA Auto Ontology's catalog-only path, and enables a locally built OpenOntologies reasoner in Factory Lab. Catalog mode does not generate semantic descriptions or call a model. Imported YAML remains a proposal requiring review.

**Verification status:** commands were checked against the pinned local upstream source and Factory Lab interfaces. Earlier managed-Python installation, PostgreSQL migrations, catalog export and ARM64 Rust build logs exist privately. This exact fresh-directory walkthrough has **not** been executed end to end. It is an operator recipe, not a claim of fresh-host validation.

## Prerequisites and private directories

Use Ubuntu 22.04/24.04, Bash, Git, uv, Docker access, and free loopback ports 55437 and 9273. Native builds need a C/C++ toolchain; the Rust build additionally needs Rust/Cargo 1.89 or newer, pkg-config, OpenSSL development headers, clang/libclang and cmake. Upstream's Dockerfile also installs libpq-dev for its broader SQL build. Install prerequisites through your host's approved provisioning process. Python must be >=3.12,<3.14; managed Python avoids the missing `Python.h` failure seen with the host interpreter.

Confirm both example ports are unused before proceeding; do not stop an existing service to free them. If either is occupied, choose a new port consistently in the template, Docker publication and server command. Run from the Factory Lab repository root in one shell. Use a new private directory; do not substitute an existing shared catalog. These commands download dependencies and later start local services when **you** execute them.

```bash
set -euo pipefail
umask 077
export FACTORY_REPO="$PWD"
export FACTORY_EXT="$FACTORY_REPO/_workspace/my-extension-operator"
test ! -e "$FACTORY_EXT"
mkdir -p "$FACTORY_EXT"
uv sync --locked
```

## Pinned Auto Ontology installation

```bash
git clone https://github.com/NVIDIA/auto-ontology.git "$FACTORY_EXT/auto-ontology"
git -C "$FACTORY_EXT/auto-ontology" checkout --detach ee42eff638ebd136c1c4fe4ab290785f912bb4bc
UV_PROJECT_ENVIRONMENT="$FACTORY_EXT/auto-python" uv sync \
  --project "$FACTORY_EXT/auto-ontology" --locked --no-dev \
  --python 3.12 --managed-python
git -C "$FACTORY_EXT/auto-ontology" diff --exit-code HEAD --
```

Keep the checkout: the bridge requires this exact clean tracked commit and an installed package importing from that directory. Do not install a non-editable wheel elsewhere or use Factory Lab's Python for the worker. The upstream lock also pins its Apache Ossie converter dependency. These pins do not pin OS packages or Python patch releases.

## Isolated PostgreSQL catalog

The example JSON contains a placeholder, not a usable password. Generate a private replacement and a Docker environment file without printing the password. `postgres.port` must be an integer and the host must be an explicit loopback address. No gateway, API key or model settings belong in catalog mode.

```bash
uv run --locked python - <<'PY'
import json, os, secrets
from pathlib import Path
root = Path(os.environ['FACTORY_EXT'])
config = json.loads(Path('examples/factory_lab/extensions/operator/catalog-operator.example.json').read_text())
config['postgres']['password'] = secrets.token_hex(24)
(root / 'catalog-operator.json').write_text(json.dumps(config, indent=2) + '\n')
p = config['postgres']
(root / 'postgres.env').write_text(f"POSTGRES_USER={p['user']}\nPOSTGRES_PASSWORD={p['password']}\nPOSTGRES_DB={p['database']}\n")
PY

docker run -d --name factory-extension-operator-pg \
  --publish 127.0.0.1:55437:5432 \
  --env-file "$FACTORY_EXT/postgres.env" \
  pgvector/pgvector@sha256:b513c48566e4777cd3370451400000c78eda6a08131d68f4c31d4a76f27bd8fd
```

The image digest is the recorded `pgvector:pg17` pull. The container's database lives in its Docker-managed volume; retain the container while investigating failures. No restart policy is installed. Check readiness; if it fails, inspect this container's logs and retry the readiness check, not the entire creation command.

```bash
docker exec factory-extension-operator-pg pg_isready -U factory_catalog -d factory_catalog
docker exec factory-extension-operator-pg psql -U factory_catalog -d factory_catalog \
  -v ON_ERROR_STOP=1 -c 'CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm;'
```

Run migrations with explicit connection variables and dotenv disabled. Upstream uses `POSTGRES_DATABASE`; Docker initialization uses `POSTGRES_DB`. The script keeps credentials out of the command line and terminal output.

```bash
uv run --locked python - <<'PY'
import json, os, subprocess
from pathlib import Path
root = Path(os.environ['FACTORY_EXT'])
p = json.loads((root / 'catalog-operator.json').read_text())['postgres']
env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PYTHON_DOTENV_DISABLED': '1'}
env.update({'POSTGRES_' + k.upper(): str(v) for k, v in p.items()})
with (root / 'migration.log').open('wb') as log:
    subprocess.run([str(root / 'auto-python/bin/python'), '-m', 'alembic', 'upgrade', 'head'],
                   cwd=root / 'auto-ontology', env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
PY
```

Alembic owns the catalog's `public` schema; the upstream vector store owns `vdb`. Do not point this procedure at production or another user's database. Do not save source connection settings in this catalog: the bridge requires an exclusively owned catalog without saved connections and binds each invocation's own SQLite snapshot.

## Registration and complete catalog invocation

```bash
uv run --locked python examples/factory_lab/extensions/registered-commerce/create_example.py \
  --output "$FACTORY_EXT/commerce"
uv run --locked python -m apps.factory_lab.database_sources_cli \
  --registry "$FACTORY_EXT/databases" register "$FACTORY_EXT/commerce/commerce.sqlite" \
  --label 'Authored commerce example' > "$FACTORY_EXT/registration.json"
FACTORY_SOURCE_ID=$(uv run --locked python -c \
  'import json,os; from pathlib import Path; print(json.loads((Path(os.environ["FACTORY_EXT"])/"registration.json").read_text())["source_id"])')
uv run --locked python -m apps.factory_lab.auto_ontology_cli \
  --registry "$FACTORY_EXT/databases" --source-id "$FACTORY_SOURCE_ID" \
  --output-root "$FACTORY_EXT/invocations" \
  --upstream-root "$FACTORY_EXT/auto-ontology" \
  --upstream-python "$FACTORY_EXT/auto-python/bin/python" \
  --operator-config "$FACTORY_EXT/catalog-operator.json" --mode catalog \
  > "$FACTORY_EXT/catalog-receipt.json"
```

Expected success is `status: returned_requires_review` with returned stages `official_catalog_ingest_without_embeddings` and `official_scoped_native_export`. Keep the invocation directory's `receipt.json`, `schema.json`, SQLite copy, logs and `native-export.yaml`. The receipt records hashes. A successful native return does not establish truth, semantic completeness or human approval. Default limits are 12 tables, 40 columns/table, 16 MiB input, 600 seconds per native invocation and 8 MiB per output file. Catalog mode inspects complete schema metadata without the semantic row/cell limit. Semantic mode retains the 1,000-row/table ceiling. Preflight metadata/count work has a cooperative deadline of at most 10 seconds with the default registry. Oversized semantic inputs are rejected without silent truncation. Documents are unsupported.

In the workspace UI, create a workspace from the registered source, import that invocation's `native-export.yaml`, then inspect field bindings and relation direction. Save and approve reviewed mappings and queries separately before executing a query. Import does not execute embedded SQL or approve proposals. The [registered source guide](../../../../docs/setup/factory-lab-registered-sources.md) covers optional text document registration.

## OpenOntologies build and Factory Lab server

This default-feature build is sufficient for the integration's fixed local load/reason/save commands. It does not enable embeddings, SQL connectors or plugins. Prior ARM64 compilation used Rust 1.89; a source pin and a locally recorded binary hash serve different purposes. The recipe below uses an already installed host toolchain and has not been rerun on a second host.

```bash
git clone https://github.com/fabio-rovai/open-ontologies.git "$FACTORY_EXT/open-ontologies"
git -C "$FACTORY_EXT/open-ontologies" checkout --detach 1ed99ac1e20450faf5ad52c824232b054778e5e0
unset CARGO_TARGET_DIR
cargo build --release --locked \
  --manifest-path "$FACTORY_EXT/open-ontologies/Cargo.toml" --bin open-ontologies
sha256sum "$FACTORY_EXT/open-ontologies/target/release/open-ontologies" \
  > "$FACTORY_EXT/open-ontologies.sha256"
uv run --locked python -m apps.factory_lab.public_server \
  --port 9273 --data-dir "$FACTORY_EXT/workspace" \
  --workspace-database-registry "$FACTORY_EXT/databases" \
  --workspace-reasoner-binary "$FACTORY_EXT/open-ontologies/target/release/open-ontologies"
```

Before the build, unset `CARGO_TARGET_DIR` if your shell defines it so the stated executable location is correct. Native ARM64 and x86-64 builds must match the host; cross-compilation is not covered. Do not use `--version` as verification: that flag was unsupported in the recorded binary. Open the local URL printed by Factory Lab. The browser obtains the local CSRF token from the configuration endpoint; the printed URL does not contain it. Remote access should use the existing authenticated access arrangement, not a public bind.

For saved query reasoning, review the output-column RDF mapping and RDFS ontology, approve the plan, then explicitly execute it. Supported derived row classifications can be saved as separate references; the original query answer is preserved. The [RDFS example](../rdfs-change/) supplies authored inputs. This walkthrough does not validate reasoning certificates or external factual truth.

## Failure retention, stopping and semantic mode

If any step fails, stop and inspect its private log/receipt. Fix prerequisites before an explicit retry. Reinvoking the bridge makes a new invocation and catalog namespace; preserve earlier attempts. Do not delete previous receipts or reset budget ledgers. To stop the foreground Factory Lab server, press Ctrl-C. To stop only this example's catalog while retaining its database:

```bash
docker stop factory-extension-operator-pg
```

Resume that same catalog with `docker start factory-extension-operator-pg`, then check readiness. When the example is intentionally retired and its artifacts have been retained, `docker rm -v factory-extension-operator-pg` removes the stopped owned container and its anonymous database volume. Keep private invocation artifacts separately; they can contain source data. Do not remove a similarly named pre-existing container to make setup succeed.

Semantic mode additionally requires `gateway` with `endpoint`, `token`, `chat_model`, `embedding_model`, plus `request_id` and `reservation_id`. The endpoint must be an explicit HTTP loopback reservation gateway. The gateway must enforce a separately authorized budget; the bridge does not enforce monetary limits or grant permission. The catalog example makes no paid call; the separately authorized semantic launcher is described below. Existing native YAML may be imported and reviewed without rerunning upstream. A saved result is replay evidence, not a new measurement.

## Bounded semantic generation with explicit paid authorization

The Linux operator launcher manages the local reservation gateway and one upstream semantic invocation. It does not start PostgreSQL or approve its output. Keep your exclusively owned catalog running using the earlier procedure. Catalog metadata remains free of model calls; semantic generation sends the bounded registered SQLite schema and rows to the selected providers. Documents and prepared sample artifacts are not supported by this semantic command.

Copy `examples/factory_lab/extensions/operator/semantic-budget.example.json` to a private path and fill every placeholder. The template deliberately cannot execute. Supply actual chat and 2048-dimensional embedding models, provider routing, pricing/context evidence, full billing token ceilings, per-request reservation, total reservation, attempt caps and an absolute deadline. One US dollar is 1,000,000,000 nanodollars; a price of USD P per million tokens is P × 1,000 nanodollars per token. Reserve against the configured full ceilings, including billable reasoning/output tokens. Price annotations are operator-supplied evidence, not automatic price verification or an invoice guarantee. The gateway enforces at most USD 10 in reservations; lower limits are recommended for a first run.

The actual upstream role routing is one shared chat alias for REASONING, NON_REASONING and RERANK, plus one embedding alias. This command does not provide independent model selection for each chat role. Source limits remain 12 tables, 40 columns/table, 1,000 rows/table and 16 MiB; oversized semantic inputs fail without silent sampling.

Prepare offline, using your registered source ID and a new campaign directory:

```bash
uv run --locked python -m apps.factory_lab.auto_ontology_semantic_cli prepare \
  --registry "$FACTORY_EXT/databases" --source-id YOUR_REGISTERED_SOURCE_ID \
  --upstream-root "$FACTORY_EXT/auto-ontology" \
  --upstream-python "$FACTORY_EXT/auto-python/bin/python" \
  --postgres-config "$FACTORY_EXT/catalog-operator.json" \
  --budget "$FACTORY_EXT/semantic-budget.json" \
  --output "$FACTORY_EXT/new-semantic-campaign" \
  --request-id YOUR_NEW_REQUEST_ID \
  --authorization-reference 'YOUR_EXPLICIT_NEW_CAMPAIGN_APPROVAL_REFERENCE'
```

Inspect the private `manifest.json` and printed SHA256 before executing. Prepare reads schema and bounded source rows for preflight, but reads no provider credential and starts no gateway, upstream service or network call. It binds source, budget, private catalog-config hash, installed upstream and launcher code. A changed binding or expired deadline requires inspection and a new prepared campaign. The manifest stores the catalog file path/hash, not its password.

Only after obtaining a separate finite paid authorization, set OPENROUTER_API_KEY in the parent shell using your secret manager, then run:

```bash
uv run --locked python -m apps.factory_lab.auto_ontology_semantic_cli execute \
  --manifest "$FACTORY_EXT/new-semantic-campaign/manifest.json" \
  --manifest-sha256 SHA256_PRINTED_BY_PREPARE \
  --authorize-paid-execution
```

The flag records operator intent; it does not grant a research budget. Existing expired campaigns remain closed. This launcher supports new campaigns only and refuses an existing execution claim or ledger; it cannot resume or reset a previous campaign. Preserve all earlier reservations and missing billing reports when requesting a new scope.

The key reaches the supervised worker through stdin, not process arguments, inherited worker environment or a generated config. The upstream receives a generated dummy loopback bearer. Run the launcher as a standalone Linux process, rather than calling its process supervisor from a shared application: it temporarily uses Linux subreaper behavior to collect its worker descendants, including detached sessions. Ctrl+C requests interruption. Wall timeout and the absolute deadline terminate owned work and record cleanup status; this is process supervision, not an OS network sandbox. Do not delete a failed run to retry it.

Keep `execution.json`, `process.json`, `campaign.sqlite`, worker logs and the invocation directory, including its raw receipt and YAML. Reservations are never refunded for failures. Unfinished attempts and missing provider-reported charges remain unknown, separate from reserved ceilings. A returned export still requires the existing import, source-linked receipt association, human review/approval and query-reuse steps; no automatic approval occurs.

**Verification boundary:** the earlier commerce semantic execution used the research launcher. It does not prove this new public launcher has made a paid call. The public launcher's offline checks and any later actual invocation must be reported separately. The current registered software check passed 430 tests and 68 subtests, with one skipped; it includes fake-transport accounting and actual local detached-session timeout/interruption cleanup, not a new provider invocation.

## Local invocation linkage and complete workspace recovery

After a real UI import, use the current workspace ID, revision and import operation ID from its saved request details. The trusted operator may link the private invocation directory without changing that pending proposal:

```bash
uv run --locked python -m apps.factory_lab.workspace_extension_receipt_cli \
  --store /private/workspace.sqlite --registry /private/databases \
  --workspace-id WORKSPACE_ID --revision REVISION \
  --import-operation-id IMPORT_OPERATION_ID --invocation-dir /private/invocations/INVOCATION_ID \
  --operator-id OPERATOR_NAME --request-key UNIQUE_REQUEST_KEY
```

Keep the original directory private and operator-owned. The association verifies local source/export/receipt hashes; it authenticates neither upstream identity nor semantic accuracy and grants no approval. In Data preparation, open the external proposal panel to inspect it and navigate to the original import. Repeating the same request key reads the saved result even when invocation files are unavailable.

Stop application writers before a complete backup. Draft export/import is a different feature and does not preserve all operation history. Use absent destination paths, preserve the printed manifest hash, and restore only a trusted local bundle:

```bash
uv run --locked python -m apps.factory_lab.workspace_backup_cli backup \
  --workspace /private/workspace.sqlite --database-registry /private/databases \
  --document-registry /private/documents --destination /private/new-backup
uv run --locked python -m apps.factory_lab.workspace_backup_cli restore \
  --bundle /private/new-backup --destination /private/new-restored \
  --manifest-sha256 RECORDED_MANIFEST_SHA256 --trusted-local-backup
```

The restored directory contains workspace.sqlite, databases/ and documents/. The public server opens workspaces.sqlite (plural) under --data-dir. After a successful restore, rename the restored store before starting this fresh directory; refuse a conflicting destination:

```bash
uv run --locked python - <<'RESTORE_PY'
from pathlib import Path
root = Path('/private/new-restored')
target = root / 'workspaces.sqlite'
if target.exists() or target.is_symlink():
    raise SystemExit('Refusing an existing server store')
(root / 'workspace.sqlite').rename(target)
RESTORE_PY
uv run --locked python -m apps.factory_lab.public_server \
  --port 9273 --data-dir /private/new-restored \
  --workspace-database-registry /private/new-restored/databases \
  --workspace-document-registry /private/new-restored/documents
```

Use an unused port and add --workspace-reasoner-binary with your installed binary only when new native execution is needed. Saved history can be read without enabling it. Credentials, model configuration, native binaries and mutable original databases are excluded. Wait for successful command completion before using a restored directory. Existing paths are never overwritten. Recovery was checked on saved manufacturing and organization workflows, including 16 replayed reasoning requests with providers disabled; the original queries were not rerun. The documented singular-to-plural rename and public-server startup were also exercised in new directories: each restored workspace exposed all 23 saved operations through actual HTTP history/detail requests with exact operation-ID and persistent-row equality. Both owned servers exited normally; original bundles remained unchanged.

## Optional offline bounded profiling artifact

This command prepares a deterministic primary-key prefix for later inspection. It does not invoke auto-ontology, create semantic suggestions, or change the registered source. The semantic bridge does not yet accept these sample artifacts or associate them with native exports.

```bash
uv run --locked python -m apps.factory_lab.auto_ontology_profile_cli \
  --registry /private/databases --source-id SOURCE_ID \
  --destination /private/new-profile --limit 1000
```

A successful new private directory contains sample.sqlite and manifest.json. Check status=complete, original source ID/hash, sample hash, preserved schema hash, selection policy, per-table counts and the separate source/sample FK checks. The source retains its identity; do not register the sample and describe it as the full source. Selection is biased, not representative. Tables without supported non-null primary keys, triggers/views/generated columns and unsupported indexes or collations are rejected. A failed manifest and partial files are retained and must not be supplied to another tool.

Actual offline checks prepared 6,080 rows from commerce's 15,680 rows and 8,250 from organization's 17,250, at most 1,000 per table. Commerce had zero original FK violations and 141 in the sample because referenced rows were omitted; organization had zero in both. No FK closure repair was performed. This demonstrates source/sample separation, not LLM semantic accuracy or upstream sample integration.
