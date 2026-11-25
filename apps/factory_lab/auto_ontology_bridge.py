"""Operator-only bridge to a pinned, separately installed NVIDIA Auto Ontology.

No import of upstream code occurs in the application process. Credentials and
model endpoints are never inherited. This bridge does not grant API budget or
human approval; a separately authorized reservation gateway must enforce costs.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.parse import quote, urlsplit
import uuid

UPSTREAM_COMMIT = 'ee42eff638ebd136c1c4fe4ab290785f912bb4bc'


class AutoOntologyError(ValueError):
    """Operator configuration or invocation error; no secret values in messages."""


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    temporary.replace(path)


@dataclass(frozen=True)
class BridgeLimits:
    max_tables: int = 12
    max_columns_per_table: int = 40
    max_rows_per_table: int = 1000  # Semantic profiling only; catalog is metadata-only.
    max_source_bytes: int = 16 * 1024 * 1024
    max_cell_bytes: int = 8192  # Semantic profiling only; no catalog cell extraction.
    timeout_seconds: int = 600
    max_output_bytes: int = 8 * 1024 * 1024

    def validate(self):
        ceilings = (100, 200, 1000, 256 * 1024 * 1024, 65536, 1800, 32 * 1024 * 1024)
        if any(type(v) is not int or not 1 <= v <= cap
               for v, cap in zip(asdict(self).values(), ceilings)):
            raise AutoOntologyError('Invocation limits exceed supported bounds')


def _endpoint(value):
    parsed = urlsplit(value)
    if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', '::1')
            or not parsed.port or parsed.username or parsed.password
            or parsed.query or parsed.fragment):
        raise AutoOntologyError('Use an explicit loopback reservation gateway endpoint')
    return parsed.hostname, parsed.port


def child_environment(config, mode):
    """Construct from scratch; even HOME, proxies, PYTHONPATH and .env are excluded."""
    if mode not in ('catalog', 'semantic'):
        raise AutoOntologyError('Choose catalog or semantic mode')
    if not isinstance(config, dict):
        raise AutoOntologyError('Operator configuration must be an object')
    allowed = {'postgres', 'gateway', 'request_id', 'reservation_id'}
    if set(config) - allowed:
        raise AutoOntologyError('Unsupported operator configuration key')
    pg = config.get('postgres', {})
    if not isinstance(pg, dict) or set(pg) != {'host', 'port', 'user', 'password', 'database'}:
        raise AutoOntologyError('Explicit catalog connection configuration required')
    if pg['host'] not in ('127.0.0.1', '::1') or type(pg['port']) is not int or not 1 <= pg['port'] <= 65535:
        raise AutoOntologyError('Catalog must use an explicit loopback port')
    if any(not isinstance(pg[k], str) or not pg[k] for k in ('user', 'password', 'database')):
        raise AutoOntologyError('Invalid catalog configuration')
    env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PYTHONNOUSERSITE': '1',
           'PYTHON_DOTENV_DISABLED': '1', 'SEMANTIC_LLM_MAX_INFLIGHT': '1',
           'LLM_MAX_INFLIGHT': '1', 'LLM_INVOKE_TIMEOUT_S': '60',
           'PREVENT_SEMANTIC_FK_DB_QUERIES': '1'}
    env.update({'POSTGRES_' + k.upper(): str(v) for k, v in pg.items()})
    gateway = config.get('gateway')
    if mode == 'semantic':
        if not isinstance(gateway, dict) or set(gateway) != {'endpoint', 'token', 'chat_model', 'embedding_model'}:
            raise AutoOntologyError('Semantic mode requires explicit trusted gateway configuration')
        if any(not isinstance(v, str) or not v for v in gateway.values()):
            raise AutoOntologyError('Incomplete gateway configuration')
        _endpoint(gateway['endpoint'])
        if any(not isinstance(config.get(k), str) or not config[k] for k in ('request_id', 'reservation_id')):
            raise AutoOntologyError('Semantic request and reservation bindings required')
    elif gateway is not None:
        raise AutoOntologyError('Catalog-only mode must not configure a model gateway')
    for prefix in ('REASONING', 'NON_REASONING', 'EMBED', 'RERANK'):
        env[prefix + '_ENDPOINT'] = gateway['endpoint'] if gateway else 'http://127.0.0.1:1/v1'
        env[prefix + '_API_KEY'] = gateway['token'] if gateway else 'disabled-catalog-only'
        env[prefix + '_MODEL'] = (gateway['embedding_model'] if prefix == 'EMBED' else gateway['chat_model']) if gateway else 'disabled'
    return env


def _verify_upstream(root):
    result = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True)
    if result.stdout.strip() != UPSTREAM_COMMIT:
        raise AutoOntologyError('Installed upstream commit differs from bridge pin')
    if subprocess.run(['git', '-C', str(root), 'diff', '--quiet', 'HEAD', '--'], capture_output=True).returncode:
        raise AutoOntologyError('Upstream tracked files differ from pinned commit')


def _invoke(registry, source_id, *, output_root, upstream_root, python_executable,
           operator_config, mode='catalog', limits=None):
    """Invoke native APIs using a fresh owned snapshot and retain private artifacts.

    Source rows are never silently sampled/truncated. Catalog mode passes the
    complete snapshot for native metadata ingestion, without profiling cells.
    Semantic mode still rejects tables above 1,000 rows. Documents are unsupported.
    """
    limits = limits or BridgeLimits()
    limits.validate()
    env = child_environment(operator_config, mode)
    upstream_root = Path(upstream_root).resolve()
    _verify_upstream(upstream_root)
    executable = Path(python_executable).absolute()
    if not executable.is_file():
        raise AutoOntologyError('Installed upstream Python executable unavailable')
    # Cooperative preflight deadline: cannot interrupt a filesystem read, but
    # checks immediately afterwards and caps SQLite work via its progress hook.
    preflight_seconds = min(30, limits.timeout_seconds, registry.timeout)
    deadline = time.monotonic() + preflight_seconds
    def check_deadline():
        if time.monotonic() >= deadline:
            raise AutoOntologyError('Registered source preflight exceeded time limit')
    # Registry is trusted local code. Re-read verified bytes, never original paths.
    record = registry._record(source_id)
    data = registry._data(record)
    check_deadline()
    if len(data) > limits.max_source_bytes:
        raise AutoOntologyError('Registered source exceeds bridge byte limit')
    timed_out = False
    def progress():
        nonlocal timed_out
        timed_out = time.monotonic() >= deadline
        return int(timed_out)
    try:
        with registry._connection(data) as connection:
            connection.set_progress_handler(progress, 1000)
            check_deadline()
            tables = registry._catalog(connection)
            if len(tables) > limits.max_tables:
                raise AutoOntologyError('Registered source exceeds table limit')
            # Upstream exposes views too; reject rather than silently changing scope.
            if connection.execute("SELECT count(*) FROM sqlite_master WHERE type='view'").fetchone()[0]:
                raise AutoOntologyError('Views are unsupported by this bounded bridge')
            schema = []
            for name, columns in tables.items():
                check_deadline()
                if len(columns) > limits.max_columns_per_table or '"' in name:
                    raise AutoOntologyError('Unsupported upstream identifier or column count')
                quoted = '"' + name + '"'
                count = connection.execute('SELECT count(*) FROM ' + quoted).fetchone()[0]
                if mode == 'semantic':
                    if count > limits.max_rows_per_table:
                        raise AutoOntologyError('Registered source exceeds per-table row bound')
                    for row in connection.execute('SELECT * FROM ' + quoted):
                        check_deadline()
                        if any(isinstance(v, (str, bytes)) and len(v.encode() if isinstance(v, str) else v) > limits.max_cell_bytes for v in row):
                            raise AutoOntologyError('Registered source exceeds cell byte bound')
                schema.append({'name': name, 'columns': columns, 'rows': count,
                               'foreign_keys': [dict(r) for r in connection.execute('PRAGMA foreign_key_list(' + quoted + ')')]})
            check_deadline()
    except ValueError:
        # SQLiteSources translates a progress interruption to DatabaseSourceError.
        if timed_out:
            raise AutoOntologyError('Registered source preflight exceeded time limit') from None
        raise
    invocation_id = uuid.uuid4().hex
    folder = Path(output_root).resolve() / invocation_id
    folder.mkdir(parents=True, mode=0o700, exist_ok=False)
    folder.chmod(0o700)
    receipt = {'format': 'auto-ontology-invocation-1', 'invocation_id': invocation_id,
               'source_id': source_id, 'source_sha256': _hash(data),
               'schema_sha256': _hash(json.dumps(schema, sort_keys=True).encode()),
               'documents': [], 'document_bytes': 0, 'document_status': 'not_supported',
               'upstream_commit': UPSTREAM_COMMIT, 'mode': mode, 'limits': asdict(limits),
               'input_scope': 'complete_source_metadata_only' if mode == 'catalog' else 'complete_small_source_semantic',
               'upstream_input': {'kind': 'complete_registered_snapshot',
                                  'sha256': _hash(data), 'bytes': len(data), 'sampled': False},
               'local_preflight': {'status': 'completed', 'timeout_seconds': preflight_seconds,
                                   'row_count_basis': 'local_sqlite_count_not_upstream_observation',
                                   'table_count': len(schema), 'total_rows': sum(s['rows'] for s in schema),
                                   'per_table_rows': {s['name']: s['rows'] for s in schema},
                                   'cell_values_materialized': mode == 'semantic',
                                   'row_and_cell_limits_apply': mode == 'semantic'},
               'upstream_profiling': {'status': 'not_requested' if mode == 'catalog' else 'not_verified',
                                      'actual_rows_observed': None},
               'request_id': operator_config.get('request_id'),
               'reservation_id': operator_config.get('reservation_id'),
               'cost_status': 'not_applicable' if mode == 'catalog' else 'unreconciled_gateway_ledger_required',
               'semantic_status': 'not_requested' if mode == 'catalog' else 'not_verified',
               'fallback_status': 'not_applicable' if mode == 'catalog' else 'unknown_inspect_native_logs_and_gateway',
               'status': 'prepared', 'stages': [], 'outputs': [],
               'limitations': ['Native return does not verify semantic completeness, factual truth or interpretation.',
                              'No human approval granted; original export must enter pending review.',
                              'Socket audit limits Python network calls, not OS-level egress isolation.',
                              'No address-space or aggregate disk quota; output bound is per file only.',
                              'Catalog must be exclusively operator-owned with no saved source connections.',
                              'No document ingestion; all registered ordinary tables selected without row truncation.',
                              'Local row counts do not establish upstream row observations or semantic coverage.',
                              'Catalog mode ingests metadata only; row/cell profiling limits apply to semantic mode.',
                              'Preflight deadline is cooperative; filesystem reads are checked after return.']}
    path = folder / 'receipt.json'
    _save(path, receipt)
    snapshot = folder / (invocation_id + '.sqlite')
    snapshot.write_bytes(data)
    snapshot.chmod(0o400)
    _save(folder / 'schema.json', schema)
    request = {'folder': str(folder), 'upstream_root': str(upstream_root),
               'snapshot': str(snapshot), 'mode': mode, 'limits': asdict(limits)}
    command = [str(executable), '-I', str(Path(__file__).resolve()), '--worker']
    process = None
    terminal = 'failed'
    try:
        with (folder / 'stdout.log').open('wb') as stdout, (folder / 'stderr.log').open('wb') as stderr:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
                                       cwd=folder, env=env, start_new_session=True)
            try:
                process.communicate(json.dumps(request).encode(), timeout=limits.timeout_seconds)
                terminal = 'returned_requires_review' if process.returncode == 0 else 'failed'
            except subprocess.TimeoutExpired:
                terminal = 'timed_out'
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
    except BaseException:
        terminal = 'interrupted_or_launch_failed'
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        raise
    finally:
        receipt = json.loads(path.read_text())
        receipt['status'] = terminal
        receipt['returncode'] = process.returncode if process else None
        receipt['outputs'] = [{'name': p.name, 'bytes': p.stat().st_size,
                               'sha256': _hash(p.read_bytes())} for p in sorted(folder.iterdir())
                              if p.is_file() and p.name not in ('receipt.json', 'receipt.tmp')]
        if _hash(snapshot.read_bytes()) != receipt['source_sha256']:
            receipt['status'] = 'source_copy_changed'
        _save(path, receipt)
    return receipt


def invoke(registry, source_id, **kwargs):
    """Retain preflight rejections too; no child is started on rejected bounds."""
    try:
        return _invoke(registry, source_id, **kwargs)
    except (AutoOntologyError, ValueError, TypeError, OSError, subprocess.SubprocessError) as exc:
        # Preflight rejection gets its own record. A process-launch exception may
        # also have the more detailed original invocation receipt; never replace it.
        folder = Path(kwargs['output_root']).resolve() / uuid.uuid4().hex
        folder.mkdir(parents=True, mode=0o700, exist_ok=False)
        folder.chmod(0o700)
        receipt = {'format': 'auto-ontology-invocation-1', 'invocation_id': folder.name,
                   'source_id': source_id if isinstance(source_id, str) and len(source_id) == 32 else None,
                   'mode': kwargs.get('mode', 'catalog'), 'status': 'rejected_or_launch_failed',
                   'input_scope': {'catalog': 'complete_source_metadata_only',
                                   'semantic': 'complete_small_source_semantic'}.get(kwargs.get('mode', 'catalog')),
                   'reason': str(exc) if isinstance(exc, AutoOntologyError) else 'Invalid or unavailable operator inputs',
                   'error_class': type(exc).__name__, 'stages': [], 'outputs': [],
                   'upstream_commit': UPSTREAM_COMMIT, 'model_success': False}
        _save(folder / 'receipt.json', receipt)
        return receipt


def _bound_connector(snapshot, list_connections, get_connectors, *, expected=None):
    """Bind official global resolution, shared by profiling and native export.

    A dedicated operator-owned catalog without saved connection settings is
    required. Never delete foreign settings or replace upstream private caches.
    """
    if list_connections():
        raise AutoOntologyError('Catalog has saved connections; dedicated unconfigured catalog required')
    path = Path(snapshot).resolve()
    uri = 'sqlite:///' + quote(str(path), safe='/')
    os.environ['CONNECTION_STRINGS'] = uri
    connectors = get_connectors()
    if len(connectors) != 1:
        raise AutoOntologyError('Native resolver must return exactly one invocation connector')
    connector = connectors[0]
    if connector.database_name != path.stem or connector.dialect != 'sqlite':
        raise AutoOntologyError('Native resolver returned a different database')
    if expected is not None and connector is not expected:
        raise AutoOntologyError('Native resolver connector changed during invocation')
    databases = connector.execute('PRAGMA database_list').to_dict(orient='records')
    main = [row for row in databases if row['name'] == 'main']
    if len(databases) != 1 or len(main) != 1 or Path(main[0]['file']).resolve() != path:
        raise AutoOntologyError('Native resolver is not bound to the owned snapshot')
    return connector


def _worker(request):
    """Native installed APIs only. Runs in a disposable child, never the server."""
    import resource
    folder = Path(request['folder'])
    receipt_path = folder / 'receipt.json'
    receipt = json.loads(receipt_path.read_text())
    resource.setrlimit(resource.RLIMIT_FSIZE, (request['limits']['max_output_bytes'],) * 2)
    allowed = {(os.environ['POSTGRES_HOST'], int(os.environ['POSTGRES_PORT']))}
    if request['mode'] == 'semantic':
        allowed.add(_endpoint(os.environ['REASONING_ENDPOINT']))
    def audit(event, args):
        if event == 'socket.connect':
            address = args[1]
            if not isinstance(address, tuple) or tuple(address[:2]) not in allowed:
                raise PermissionError('Network destination outside explicit bridge configuration')
    sys.addaudithook(audit)
    # Disable dotenv even if an upstream dependency explicitly tries to call it.
    import dotenv
    dotenv.load_dotenv = lambda *args, **kwargs: False
    import auto_ontology
    if Path(auto_ontology.__file__).resolve().parent != Path(request['upstream_root']) / 'auto_ontology':
        raise AutoOntologyError('Imported upstream does not match pinned source directory')
    import logging
    logging.basicConfig(level=logging.INFO)
    def stage(name, function):
        row = {'stage': name, 'status': 'running', 'started_epoch': time.time()}
        receipt['stages'].append(row)
        _save(receipt_path, receipt)
        try:
            value = function()
            row.update(status='returned', result=value)
            return True
        except Exception as exc:
            row.update(status='failed', error_class=type(exc).__name__)
            logging.exception('Native stage failed: %s', name)
            return False
        finally:
            row['elapsed_seconds'] = time.time() - row['started_epoch']
            _save(receipt_path, receipt)
    from auto_ontology.connectors.registry import get_connectors
    from auto_ontology.dal.connections import list_connections
    connector = _bound_connector(request['snapshot'], list_connections, get_connectors)
    receipt['connector_binding'] = {'database_name': connector.database_name,
                                    'resolver': 'official_get_connectors',
                                    'snapshot_sha256': receipt['source_sha256']}
    _save(receipt_path, receipt)
    try:
        if request['mode'] == 'catalog':
            from auto_ontology.catalog import ingest_catalog
            def catalog():
                tables, columns = ingest_catalog(connector)
                return {'tables': len(tables), 'columns': len(columns)}
            stage('official_catalog_ingest_without_embeddings', catalog)
        else:
            from auto_ontology.ingestion_service.ingest import run_ingest
            from auto_ontology.semantic.compile import run_semantic_compilation
            if stage('official_catalog_and_embedding_ingest', lambda: run_ingest(connector)):
                def compile_semantics():
                    _bound_connector(request['snapshot'], list_connections, get_connectors, expected=connector)
                    return run_semantic_compilation(connector.database_name)
                stage('official_semantic_compile', compile_semantics)
        def export():
            _bound_connector(request['snapshot'], list_connections, get_connectors, expected=connector)
            from sqlalchemy import select
            from auto_ontology.dal import model_interchange as dal
            from auto_ontology.server.model_interchange.schemas import ExportRequest
            from auto_ontology.server.model_interchange.service import export_model
            db = dal.s.catalog_database
            matches = dal.store().query_read(select(db.c.id).where(db.c.name == connector.database_name))
            ids = [str(row['id']) for row in matches]
            if len(ids) != 1:
                raise AutoOntologyError('Expected exactly one invocation-scoped catalog database')
            raw = export_model(ExportRequest(databases=ids))
            if not isinstance(raw, str):
                raise AutoOntologyError('Native export did not return YAML text')
            encoded = raw.encode()
            # Write original bytes even when oversize; OS file limit retains prefix
            # on failure and stage records failure. Never advertise prefix as export.
            (folder / 'native-export.yaml').write_bytes(encoded)
            return {'sha256': _hash(encoded), 'bytes': len(encoded), 'catalog_ids': ids}
        stage('official_scoped_native_export', export)
    finally:
        connector.close()
    return 1 if any(s['status'] != 'returned' for s in receipt['stages']) else 0


if __name__ == '__main__':
    if sys.argv[1:] != ['--worker']:
        raise SystemExit('Use apps.factory_lab.auto_ontology_cli')
    request = json.load(sys.stdin)
    try:
        code = _worker(request)
    except BaseException as exc:
        path = Path(request['folder']) / 'receipt.json'
        receipt = json.loads(path.read_text())
        receipt['stages'].append({'stage': 'worker_bootstrap_or_cleanup',
                                  'status': 'failed', 'error_class': type(exc).__name__})
        _save(path, receipt)
        raise
    raise SystemExit(code)
