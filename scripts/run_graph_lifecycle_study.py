"""Bounded synthetic JSON/Neo4j lifecycle study; no server launch or paid APIs.

Enumerates supported country paths, not external truth. Neo4j timings include
HTTP; JSON arms use resident objects and atomic local snapshots. No RDF database,
OWL, natural language, human maintenance cost, or pure-engine comparison.
"""
import argparse
import copy
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import random
import re
import shutil
import statistics
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
ARMS = ('json_scan', 'json_indexed', 'neo4j')
CHECKPOINTS = ('initial', 'add_products', 'change_region', 'delete_supply',
               'restore_supply', 'add_backup', 'allow_backup', 'revert_rule')
KINDS = ('Product', 'Supplier', 'Region', 'Country')
RELATIONS = ('SUPPLIED_BY', 'LOCATED_IN', 'IN_COUNTRY')
INDEX = ('CREATE INDEX graph_lifecycle_run_id_id IF NOT EXISTS '
         'FOR (n:GraphLifecycle) ON (n.run_id, n.id)')
VERSION = 'CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition'
CLEANUP = 'MATCH (n:GraphLifecycle {run_id: $run_id}) DETACH DELETE n'
DELETE = '''MATCH (s:GraphLifecycle {run_id: $run_id})-[e]->
(t:GraphLifecycle {run_id: $run_id}) WHERE e.run_id = $run_id AND e.id IN $delete_ids DELETE e'''
QUERY = '''MATCH (p:GraphLifecycle:Product {run_id: $run_id, id: $subject})
-[a:SUPPLIED_BY]->(s:GraphLifecycle:Supplier {run_id: $run_id})
-[b:LOCATED_IN]->(r:GraphLifecycle:Region {run_id: $run_id})
-[d:IN_COUNTRY]->(c:GraphLifecycle:Country {run_id: $run_id})
WHERE a.run_id = $run_id AND b.run_id = $run_id AND d.run_id = $run_id
AND a.role IN $allowed_roles
RETURN DISTINCT p.id AS product, s.id AS supplier, r.id AS region,
c.id AS country, a.role AS role, a.id AS supply_edge,
b.id AS location_edge, d.id AS country_edge'''
# Only these closed, source-defined identifiers are interpolated into templates.
NODE_QUERIES = {kind: 'UNWIND $nodes AS row CREATE (n:GraphLifecycle:' + kind +
                ' {run_id: $run_id, id: row.id})' for kind in KINDS}
EDGE_QUERIES = {kind: '''UNWIND $edges AS row
MATCH (s:GraphLifecycle {run_id: $run_id, id: row.s}),
(t:GraphLifecycle {run_id: $run_id, id: row.t})
CREATE (s)-[e:''' + kind + ''' {run_id: $run_id, id: row.id}]->(t)
SET e.role = row.role''' for kind in RELATIONS}


def atomic_json(path, value):
    """Atomic replace and file fsync; directory fsync/crash recovery not benchmarked."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.pending-', delete=False) as handle:
            name = handle.name
            json.dump(value, handle, sort_keys=True, separators=(',', ':'))
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def rule(roles):
    if not roles or len(set(roles)) != len(roles) or set(roles) - {'primary', 'backup'}:
        raise ValueError('Only unique primary/backup roles are supported')
    return {'allowed_roles': sorted(roles)}


def edge(identifier, source, target, kind, role_value=None):
    return dict(id=identifier, s=source, t=target, kind=kind, role=role_value)


def generate(size, seed):
    rng = random.Random(seed)
    suppliers = max(10, size // 10)
    nodes = ([dict(id=f'p{i}', kind='Product') for i in range(size)] +
             [dict(id=f's{i}', kind='Supplier') for i in range(suppliers)] +
             [dict(id=f'r{i}', kind='Region') for i in range(8)] +
             [dict(id=f'c{i}', kind='Country') for i in range(4)])
    edges = [edge(f'country{i}', f'r{i}', f'c{i % 4}', 'IN_COUNTRY') for i in range(8)]
    edges += [edge(f'location{i}', f's{i}', f'r{i % 8}', 'LOCATED_IN') for i in range(suppliers)]
    for i in range(size):
        supplier = 0 if i < 4 else (9 if i == 17 else rng.randrange(suppliers))
        edges.append(edge(f'supply{i}', f'p{i}', f's{supplier}', 'SUPPLIED_BY', 'primary'))
    return dict(nodes=nodes, edges=edges, config=rule(['primary']))


def mutation(checkpoint, size):
    result = dict(add_nodes=[], add_edges=[], delete_ids=[], config=None)
    if checkpoint == 'add_products':
        for i in range(max(1, size // 10)):
            result['add_nodes'].append(dict(id=f'new{i}', kind='Product'))
            result['add_edges'].append(edge(f'new_supply{i}', f'new{i}', f's{i % 10}', 'SUPPLIED_BY', 'primary'))
    elif checkpoint == 'change_region':
        result.update(delete_ids=['location0'], add_edges=[edge('location0', 's0', 'r1', 'LOCATED_IN')])
    elif checkpoint == 'delete_supply':
        result['delete_ids'] = ['supply2']
    elif checkpoint == 'restore_supply':
        result['add_edges'] = [edge('supply2', 'p2', 's0', 'SUPPLIED_BY', 'primary')]
    elif checkpoint == 'add_backup':
        result['add_edges'] = [edge('backup3', 'p3', 's2', 'SUPPLIED_BY', 'backup')]
    elif checkpoint in ('allow_backup', 'revert_rule'):
        result['config'] = rule(['primary', 'backup'] if checkpoint == 'allow_backup' else ['primary'])
    elif checkpoint != 'initial':
        raise ValueError(checkpoint)
    return result


def apply(snapshot, change):
    """Apply source operations only; receives no evaluator outputs."""
    if change['delete_ids']:
        snapshot['edges'] = [e for e in snapshot['edges'] if e['id'] not in change['delete_ids']]
    snapshot['nodes'].extend(copy.deepcopy(change['add_nodes']))
    snapshot['edges'].extend(copy.deepcopy(change['add_edges']))
    if change['config'] is not None:
        snapshot['config'] = copy.deepcopy(change['config'])


def path(a, b, c):
    return dict(product=a['s'], supplier=a['t'], region=b['t'], country=c['t'],
                role=a['role'], supply_edge=a['id'], location_edge=b['id'], country_edge=c['id'])


def answer(paths):
    unique = {json.dumps(p, sort_keys=True): p for p in paths}
    return dict(countries=sorted({p['country'] for p in unique.values()}),
                paths=[unique[k] for k in sorted(unique)])


def evaluate(snapshot, subject):
    """Independent reverse relational join; scoring only, never backend repair."""
    typed = {n['id']: n['kind'] for n in snapshot['nodes']}
    paths = []
    supplies = [e for e in snapshot['edges'] if e['kind'] == 'SUPPLIED_BY' and e['s'] == subject]
    locations = [e for e in snapshot['edges'] if e['kind'] == 'LOCATED_IN']
    countries = [e for e in snapshot['edges'] if e['kind'] == 'IN_COUNTRY']
    for c in countries:
        if c['kind'] != 'IN_COUNTRY' or typed[c['t']] != 'Country' or typed[c['s']] != 'Region':
            continue
        for b in locations:
            if b['kind'] != 'LOCATED_IN' or b['t'] != c['s'] or typed[b['s']] != 'Supplier':
                continue
            for a in supplies:
                if (a['kind'] == 'SUPPLIED_BY' and a['t'] == b['s'] and a['s'] == subject
                        and typed[a['s']] == 'Product' and a['role'] in snapshot['config']['allowed_roles']):
                    # Independent field construction, not the runtime path helper.
                    paths.append(dict(product=subject, supplier=b['s'], region=c['s'], country=c['t'],
                                      role=a['role'], supply_edge=a['id'], location_edge=b['id'], country_edge=c['id']))
    return answer(paths)


class JsonBackend:
    def __init__(self, indexed, location):
        self.indexed, self.location = indexed, location
        self.snapshot = None
        self.adjacency, self.types = {}, {}

    def update(self, initial=None, change=None):
        start = time.perf_counter()
        if initial is not None:
            self.snapshot = copy.deepcopy(initial)
        else:
            apply(self.snapshot, change)
        mutation_ms = (time.perf_counter() - start) * 1000
        graph_changed = initial is not None or bool(change['add_nodes'] or change['add_edges'] or change['delete_ids'])
        if not graph_changed:
            return dict(mutation_ms=mutation_ms, serialization_fsync_replace_ms=0.0,
                        rebuild_index_ms=0.0, total_ms=mutation_ms, config_only=True)
        start = time.perf_counter()
        atomic_json(self.location, {k: self.snapshot[k] for k in ('nodes', 'edges')})
        persist_ms = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        self.types = {n['id']: n['kind'] for n in self.snapshot['nodes']}
        self.adjacency = {}
        if self.indexed:
            for e in self.snapshot['edges']:
                self.adjacency.setdefault((e['s'], e['kind']), []).append(e)
        index_ms = (time.perf_counter() - start) * 1000
        return dict(mutation_ms=mutation_ms, serialization_fsync_replace_ms=persist_ms,
                    rebuild_index_ms=index_ms, total_ms=mutation_ms + persist_ms + index_ms)

    def outgoing(self, subject, kind):
        if self.indexed:
            return self.adjacency.get((subject, kind), [])
        return [e for e in self.snapshot['edges'] if e['s'] == subject and e['kind'] == kind]

    def query(self, subject, config):
        paths = []
        if self.types.get(subject) != 'Product':
            return answer(paths)
        for a in self.outgoing(subject, 'SUPPLIED_BY'):
            if a['role'] not in config['allowed_roles'] or self.types.get(a['t']) != 'Supplier':
                continue
            for b in self.outgoing(a['t'], 'LOCATED_IN'):
                if self.types.get(b['t']) != 'Region':
                    continue
                for c in self.outgoing(b['t'], 'IN_COUNTRY'):
                    if self.types.get(c['t']) == 'Country':
                        paths.append(path(a, b, c))
        return answer(paths)


def local_endpoint(value):
    if not re.fullmatch(r'http://127\.0\.0\.1:[0-9]{1,5}', value):
        raise ValueError('Explicit http://127.0.0.1:<port> required')
    if not 1 <= int(value.rsplit(':', 1)[1]) <= 65535:
        raise ValueError('Invalid port')
    return value + '/db/neo4j/tx/commit'


class Neo4jBackend:
    def __init__(self, client, endpoint, namespace):
        self.client, self.endpoint, self.namespace = client, endpoint, namespace

    def transaction(self, statements):
        response = self.client.post(self.endpoint, json={'statements': [
            dict(statement=q, parameters={**p, 'run_id': self.namespace}, resultDataContents=['row'])
            for q, p in statements]})
        response.raise_for_status()
        body = response.json()
        if body.get('errors'):
            raise RuntimeError(json.dumps(body['errors']))
        return [[dict(zip(result['columns'], row['row'], strict=True)) for row in result['data']]
                for result in body['results']]

    def update(self, initial=None, change=None):
        start = time.perf_counter()
        if initial is not None:
            change = dict(add_nodes=initial['nodes'], add_edges=initial['edges'], delete_ids=[], config=initial['config'])
        statements = []
        if change['delete_ids']:
            statements.append((DELETE, dict(delete_ids=change['delete_ids'])))
        for kind, query in NODE_QUERIES.items():
            nodes = [n for n in change['add_nodes'] if n['kind'] == kind]
            if nodes:
                statements.append((query, dict(nodes=nodes)))
        for kind, query in EDGE_QUERIES.items():
            edges = [e for e in change['add_edges'] if e['kind'] == kind]
            if edges:
                statements.append((query, dict(edges=edges)))
        # Remove/add statements share one commit: no intermediate visible graph.
        if statements:
            self.transaction(statements)
        return dict(total_ms=(time.perf_counter() - start) * 1000,
                    includes_http=bool(statements), config_only=not statements)

    def query(self, subject, config):
        rows = self.transaction([(QUERY, dict(subject=subject, **config))])[0]
        # Only normalize database-returned paths; no Python graph traversal.
        return answer(rows)

    def cleanup(self):
        self.transaction([(CLEANUP, {})])


def timed_query(backend, subject, config, samples, progress=None):
    warm = backend.query(subject, config)
    latencies, outputs = [], []
    if progress:
        progress(dict(warmup_answer=warm, samples_ms=[], sample_answers=[]))
    for _ in range(samples):
        start = time.perf_counter()
        value = backend.query(subject, config)
        latencies.append((time.perf_counter() - start) * 1000)
        outputs.append(value)
        if progress:
            progress(dict(samples_ms=latencies, sample_answers=outputs))
    return dict(answer=outputs[-1], warmup_answer=warm, samples_ms=latencies,
                sample_answer_sha256=[digest(v) for v in outputs],
                stable=all(v == warm for v in outputs), median_ms=statistics.median(latencies),
                p95_ms=sorted(latencies)[math.ceil(.95 * len(latencies)) - 1])


def plan_rows(sizes, repeats):
    return [dict(id=f'n{size}-r{repeat}-{checkpoint}-{subject}-{arm}', size=size,
                 repeat=repeat, checkpoint=checkpoint, subject=subject, arm=arm, status='planned')
            for size in sizes for repeat in range(repeats) for checkpoint in CHECKPOINTS
            for subject in [*[f'p{i}' for i in range(18)], 'new0', 'missing'] for arm in ARMS]


def run(args):
    endpoint = local_endpoint(args.endpoint)
    args.output.mkdir(parents=True, exist_ok=False)
    record = dict(protocol='graph-lifecycle-1', status='running', started_utc=datetime.now(UTC).isoformat(),
                  sizes=args.sizes, repeats=args.repeats, samples=args.samples, seed=args.seed,
                  endpoint=args.endpoint, arms=ARMS, checkpoints=CHECKPOINTS,
                  versions=dict(python=platform.python_version(), httpx=importlib.metadata.version('httpx')),
                  source_hashes={}, planned_rows=len(plan_rows(args.sizes, args.repeats)),
                  planned_query_invocations=len(plan_rows(args.sizes, args.repeats)) * (args.samples + 1),
                  namespaces=[], updates=[], snapshots=[], common_config_writes=[], errors=[],
                  limitations=['Synthetic positive path enumeration, not external truth.',
                               'No RDF database or OWL arm; no human maintenance measurement.',
                               'HTTP database versus resident Python; timing boundaries differ.',
                               'Fixed arm order; shared host caches; tiny per-row timing samples.',
                               'Shared GraphLifecycle schema index retained; namespace data cleaned.'],
                  templates=dict(query=QUERY, nodes=NODE_QUERIES, edges=EDGE_QUERIES,
                                 delete=DELETE, cleanup=CLEANUP, index=INDEX))
    def save():
        atomic_json(args.output / 'record.json', record)
    save()
    rows = plan_rows(args.sizes, args.repeats)
    atomic_json(args.output / 'planned-rows.json', rows)
    for rel in ('scripts/run_graph_lifecycle_study.py', 'tests/test_graph_lifecycle_study.py', 'uv.lock'):
        src, dest = ROOT / rel, args.output / 'inputs' / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        record['source_hashes'][rel] = hashlib.sha256(src.read_bytes()).hexdigest()
    save()
    auth = None if args.no_auth else (args.username, os.environ[args.password_env])
    try:
        with httpx.Client(auth=auth, trust_env=False, follow_redirects=False, timeout=10) as client:
            probe = Neo4jBackend(client, endpoint, 'metadata-' + uuid.uuid4().hex)
            record['versions']['neo4j'] = probe.transaction([(VERSION, {})])[0]
            start = time.perf_counter()
            probe.transaction([(INDEX, {})])
            probe.transaction([('CALL db.awaitIndexes(10)', {})])
            record['schema_setup_http_ms'] = (time.perf_counter() - start) * 1000
            save()
            for size in args.sizes:
                for repeat in range(args.repeats):
                    namespace = f'lifecycle-{size}-{repeat}-' + uuid.uuid4().hex
                    lifecycle = dict(namespace=namespace, size=size, repeat=repeat, cleanup='pending')
                    record['namespaces'].append(lifecycle)
                    save()
                    folder = args.output / f'n{size}-r{repeat}'
                    canonical = generate(size, args.seed + repeat)
                    backends = dict(json_scan=JsonBackend(False, folder / 'json_scan.json'),
                                    json_indexed=JsonBackend(True, folder / 'json_indexed.json'),
                                    neo4j=Neo4jBackend(client, endpoint, namespace))
                    try:
                        for checkpoint in CHECKPOINTS:
                            change = mutation(checkpoint, size)
                            if checkpoint != 'initial':
                                apply(canonical, change)
                            if checkpoint == 'initial' or change['config'] is not None:
                                config_path = folder / 'rule.json'
                                start = time.perf_counter()
                                atomic_json(config_path, canonical['config'])
                                config_ms = (time.perf_counter() - start) * 1000
                                record['common_config_writes'].append(dict(size=size, repeat=repeat,
                                    checkpoint=checkpoint, serialization_fsync_replace_ms=config_ms,
                                    bytes=config_path.stat().st_size, config=copy.deepcopy(canonical['config'])))
                            snapshot_path = folder / f'{checkpoint}-canonical.json'
                            atomic_json(snapshot_path, canonical)
                            record['snapshots'].append(dict(size=size, repeat=repeat, checkpoint=checkpoint,
                                path=str(snapshot_path.relative_to(args.output)), sha256=digest(canonical),
                                file_sha256=hashlib.sha256(snapshot_path.read_bytes()).hexdigest(), mutation=change,
                                graph_json_bytes=len(json.dumps({k: canonical[k] for k in ('nodes', 'edges')},
                                    sort_keys=True, separators=(',', ':')).encode()) + 1,
                                config_json_bytes=(folder / 'rule.json').stat().st_size))
                            save()
                            for arm, backend in backends.items():
                                update = dict(size=size, repeat=repeat, checkpoint=checkpoint, arm=arm, status='running',
                                    operation_counts=dict(add_nodes=len(canonical['nodes']) if checkpoint == 'initial' else len(change['add_nodes']),
                                        add_edges=len(canonical['edges']) if checkpoint == 'initial' else len(change['add_edges']),
                                        delete_edges=len(change['delete_ids']),
                                        config_changes=int(checkpoint == 'initial' or change['config'] is not None)))
                                record['updates'].append(update)
                                save()
                                try:
                                    update['timing'] = backend.update(initial=canonical) if checkpoint == 'initial' else backend.update(change=change)
                                    update['status'] = 'ok'
                                except Exception as exc:
                                    update.update(status='error', error=f'{type(exc).__name__}: {exc}')
                                    raise
                                finally:
                                    save()
                            for subject in [*[f'p{i}' for i in range(18)], 'new0', 'missing']:
                                expected = evaluate(canonical, subject)
                                for arm, backend in backends.items():
                                    row_id = f'n{size}-r{repeat}-{checkpoint}-{subject}-{arm}'
                                    row = dict(id=row_id, size=size, repeat=repeat, checkpoint=checkpoint,
                                               subject=subject, arm=arm, namespace=namespace, status='running')
                                    location = args.output / 'rows' / f'{row_id}.json'
                                    atomic_json(location, row)
                                    def progress(partial):
                                        row.update(partial)
                                        atomic_json(location, row)
                                    try:
                                        row.update(timed_query(backend, subject, canonical['config'], args.samples, progress))
                                        row.update(expected=expected, agreement=row['answer'] == expected,
                                                   country_agreement=row['answer']['countries'] == expected['countries'], status='ok')
                                    except Exception as exc:
                                        row.update(status='error', error=f'{type(exc).__name__}: {exc}')
                                        raise
                                    finally:
                                        atomic_json(location, row)
                    finally:
                        try:
                            backends['neo4j'].cleanup()
                            lifecycle['cleanup'] = 'ok'
                        except Exception as exc:
                            lifecycle.update(cleanup='error', error=f'{type(exc).__name__}: {exc}')
                            record['errors'].append(lifecycle['error'])
                        save()
                    if lifecycle['cleanup'] != 'ok':
                        raise RuntimeError('Namespace cleanup failed; stopping')
        record['status'] = 'completed'
    except Exception as exc:
        record['status'] = 'failed'
        record['errors'].append(f'{type(exc).__name__}: {exc}')
    finally:
        actual = [json.loads(p.read_text()) for p in sorted((args.output / 'rows').glob('*.json'))]
        record.update(finished_utc=datetime.now(UTC).isoformat(), executed_rows=len(actual),
                      unexecuted_rows=record['planned_rows'] - len(actual),
                      successful_rows=sum(r['status'] == 'ok' for r in actual),
                      agreement_rows=sum(r.get('agreement', False) for r in actual),
                      unstable_rows=sum(r.get('stable') is False for r in actual))
        save()
        print(args.output / 'record.json')
    return 0 if record['status'] == 'completed' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Fresh directory; refuses overwrite')
    parser.add_argument('--endpoint', required=True)
    parser.add_argument('--no-auth', action='store_true')
    parser.add_argument('--username', default='neo4j')
    parser.add_argument('--password-env', default='NEO4J_PASSWORD')
    parser.add_argument('--sizes', type=int, nargs='+', default=[100, 1000, 5000])
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--samples', type=int, default=3)
    parser.add_argument('--seed', type=int, default=20261014)
    args = parser.parse_args()
    if (not args.sizes or len(set(args.sizes)) != len(args.sizes) or
            any(n < 20 or n > 5000 for n in args.sizes) or len(args.sizes) > 3 or
            not 1 <= args.repeats <= 2 or not 1 <= args.samples <= 10):
        parser.error('Bounds: 1–3 distinct sizes 20–5000, repeats 1–2, samples 1–10')
    if not args.no_auth and not os.environ.get(args.password_env):
        parser.error('Set password environment variable or explicitly supply --no-auth')
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
