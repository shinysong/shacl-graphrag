"""Bounded offline shared-semantics study; deterministic faults, not failure rates.

All arms share the decision algorithm. local_json has three independently copied
configuration objects, not three independently implemented applications. RDFLib
SPARQL and selected JSON are matched materialized views; neither is an RDF DB.
"""
import argparse
import copy
import hashlib
import importlib.metadata
import json
import os
import platform
import random
import signal
import statistics
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from rdflib import Graph, Literal, Namespace, RDF
from rdflib.plugins.sparql import prepareQuery

ROOT = Path(__file__).resolve().parents[1]
ARMS = ('local_json', 'shared_json_live', 'shared_json_projection', 'rdf_hybrid')
WORKFLOWS = ('countries', 'audit', 'recommend')
SNAPSHOTS = ('initial', 'allow_backup', 'rename_country_field', 'add_substitute_role',
             'restrict_country', 'supplier_move', 'remove_country', 'cost_change')
FAULTS = ('clean', 'stale_config_copy', 'stale_projection', 'common_wrong_mapping')
SUBJECTS = tuple(f'p{i}' for i in range(7)) + ('p_missing',)
SUBJECT_DESIGN = {
    'p0': 'Primary C0 cost30; backup C1 cost10 becomes eligible under allow_backup.',
    'p1': 'Primary C0 and restricted C2; audit must block.',
    'p2': 'Primary C0; replacement C1 cost10 becomes primary under alias addition.',
    'p3': 'Single primary C0; independently move to C2 or remove country.',
    'p4': 'Two primary candidates C0 cost30 and C1 cost25; cost_change lowers C0 to5.',
    'p5': 'Single restricted C2; recommendation unavailable.',
    'p6': 'Existing product without supply edges; unknown.',
    'p_missing': 'Absent product; unknown, with distinct existence evidence.',
}
NS = Namespace('urn:shared-semantics:')
QUERY_TEXT = '''PREFIX s: <urn:shared-semantics:>
SELECT ?product ?edge ?supplier ?role ?country ?cost WHERE {
  BIND(?requested AS ?product)
  ?product a s:Product .
  OPTIONAL {
    ?edge s:product ?product ; s:supplier ?supplier ; s:role ?role .
    OPTIONAL { ?supplier s:country ?country }
    OPTIONAL { ?supplier s:cost ?cost }
  }
}'''


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            pending = handle.name
            handle.write(encoded(value) + b'\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(pending, path)
    finally:
        if pending and os.path.exists(pending):
            os.unlink(pending)


def baseline(size, seed):
    """Pinned subjects cover effects; remaining records change background size."""
    if size not in (24, 96):
        raise ValueError('Only the predeclared sizes 24 and 96 are supported')
    rng = random.Random(seed)
    suppliers = [dict(id=f's{i}', old_country=country, tax_country='C0', cost=cost,
                      description=f'Non-semantic supplier metadata {i}')
                 for i, (country, cost) in enumerate([
                     ('C0', 30), ('C1', 10), ('C2', 20), ('C0', 40),
                     ('C1', 25), ('C2', 5), ('C0', 50), ('C1', 15)])]
    # p0 backup; p1 mixed restricted; p2 substitution; p3 move/remove;
    # p4 cost crossover; p5 restricted only; p6 no candidates.
    pinned = [(0, 0, 'main'), (0, 1, 'reserve'), (1, 0, 'main'), (1, 2, 'main'),
              (2, 0, 'main'), (2, 1, 'replacement'), (3, 3, 'main'),
              (4, 0, 'main'), (4, 4, 'main'), (5, 5, 'main')]
    extra = [(i, rng.randrange(8), rng.choice(('main', 'reserve', 'replacement')))
             for i in range(7, size)]
    source = dict(products=[dict(id=f'p{i}', description='Ignored catalog metadata ' * 8)
                            for i in range(size)], suppliers=suppliers,
                  edges=[dict(id=f'e{i}', product=f'p{p}', supplier=f's{s}', role=role)
                         for i, (p, s, role) in enumerate(pinned + extra)])
    config = dict(location_field='old_country', role_aliases={'main': 'primary',
                  'reserve': 'backup'}, allowed_roles=['primary'], restricted_countries=['C2'])
    return source, config


def snapshot(source, config, name):
    if name not in SNAPSHOTS:
        raise ValueError(name)
    source, config = copy.deepcopy(source), copy.deepcopy(config)
    if name == 'allow_backup':
        config['allowed_roles'].append('backup')
    elif name == 'rename_country_field':
        for supplier in source['suppliers']:
            supplier['new_country'] = supplier.pop('old_country')
        config['location_field'] = 'new_country'
    elif name == 'add_substitute_role':
        config['role_aliases']['replacement'] = 'primary'
    elif name == 'restrict_country':
        config['restricted_countries'].append('C1')
    elif name == 'supplier_move':
        source['suppliers'][3]['old_country'] = 'C2'
    elif name == 'remove_country':
        del source['suppliers'][3]['old_country']
    elif name == 'cost_change':
        source['suppliers'][0]['cost'] = 5
    return source, config


def project(source, config):
    return dict(products=[p['id'] for p in source['products']],
                edges=copy.deepcopy(source['edges']),
                suppliers=[dict(id=s['id'], country=s.get(config['location_field']),
                                cost=s.get('cost')) for s in source['suppliers']])


def graph_from_projection(view):
    graph = Graph()
    for product in view['products']:
        graph.add((NS[product], RDF.type, NS.Product))
    for edge in view['edges']:
        for field in ('product', 'supplier'):
            graph.add((NS[edge['id']], NS[field], NS[edge[field]]))
        graph.add((NS[edge['id']], NS.role, Literal(edge['role'])))
    for supplier in view['suppliers']:
        for field in ('country', 'cost'):
            if supplier[field] is not None:
                graph.add((NS[supplier['id']], NS[field], Literal(supplier[field])))
    return graph


def normalized(exists, candidates):
    return dict(product_exists=exists, candidates=sorted(candidates, key=lambda r: r['edge']))


def candidate(edge, supplier, config, projected=False):
    role = config['role_aliases'].get(edge['role'])
    if role not in config['allowed_roles']:
        return None
    return dict(edge=edge['id'], supplier=edge['supplier'], raw_role=edge['role'], role=role,
                country=supplier.get('country' if projected else config['location_field']),
                cost=supplier.get('cost'))


def retrieve_json(data, config, subject, projected=False):
    products = data['products'] if projected else [p['id'] for p in data['products']]
    suppliers = {s['id']: s for s in data['suppliers']}
    rows = []
    if subject in products:
        for edge in data['edges']:
            if edge['product'] == subject:
                row = candidate(edge, suppliers.get(edge['supplier'], {}), config, projected)
                if row is not None:
                    rows.append(row)
    return normalized(subject in products, rows)


def retrieve_rdf(graph, query, config, subject):
    """Parameter binding is actual SPARQL evidence retrieval, with no JSON fallback."""
    records = list(graph.query(query, initBindings={'requested': NS[subject]}))
    candidates = []
    for record in records:
        if record.edge is None:
            continue
        raw_role = str(record.role)
        role = config['role_aliases'].get(raw_role)
        if role in config['allowed_roles']:
            candidates.append(dict(edge=str(record.edge).removeprefix(str(NS)),
                supplier=str(record.supplier).removeprefix(str(NS)), raw_role=raw_role,
                role=role, country=str(record.country) if record.country is not None else None,
                cost=int(record.cost) if record.cost is not None else None))
    return normalized(bool(records), candidates)


def reference_evidence(source, intended, subject):
    """Separate source evaluator; never an input to any deployed arm."""
    exists = any(product['id'] == subject for product in source['products'])
    output = []
    for relation in source['edges']:
        if not exists or relation['product'] != subject:
            continue
        meaning = intended['role_aliases'].get(relation['role'])
        if meaning not in intended['allowed_roles']:
            continue
        supplier = next((s for s in source['suppliers'] if s['id'] == relation['supplier']), {})
        output.append({'edge': relation['id'], 'supplier': relation['supplier'],
                       'raw_role': relation['role'], 'role': meaning,
                       'country': supplier.get(intended['location_field']),
                       'cost': supplier.get('cost')})
    return normalized(exists, output)


def decide(evidence, config, workflow):
    rows = evidence['candidates']
    countries = sorted({row['country'] for row in rows if row['country'] is not None})
    complete = bool(rows) and all(row['country'] is not None for row in rows)
    restricted = set(config['restricted_countries'])
    if workflow == 'countries':
        return dict(decision='complete' if complete else 'unknown', value=countries)
    if workflow == 'audit':
        return dict(decision='blocked' if restricted.intersection(countries) else
                    'clear' if complete else 'unknown', value=None)
    if workflow != 'recommend':
        raise ValueError(workflow)
    if not complete or any(row['cost'] is None for row in rows):
        return dict(decision='unknown', value=None)
    allowed = [row for row in rows if row['country'] not in restricted]
    if not allowed:
        return dict(decision='unavailable', value=None)
    best = min(allowed, key=lambda row: (row['cost'], row['supplier']))
    return dict(decision='recommended', value=best['supplier'])


def deploy(arm, source, intended, prior_source, prior_config, fault, target):
    if arm not in ARMS or fault not in FAULTS or target not in WORKFLOWS:
        raise ValueError('Unknown deployment setting')
    installed = copy.deepcopy(intended)
    if fault == 'common_wrong_mapping':
        installed['location_field'] = 'tax_country'
    if arm == 'local_json':
        configs = {workflow: copy.deepcopy(installed) for workflow in WORKFLOWS}
        if fault == 'stale_config_copy':
            configs[target] = copy.deepcopy(prior_config)
    else:
        if fault == 'stale_config_copy':
            installed = copy.deepcopy(prior_config)
        configs = {'shared': installed}
    state = dict(configs=configs, data=source, projection=None, graph=None,
                 provenance=dict(current_source_hash=digest(source),
                                 intended_config_hash=digest(intended),
                                 installed_config_matches_intended={k: v == intended for k, v in configs.items()},
                                 installed_config_hashes={k: digest(v) for k, v in configs.items()}))
    if arm in ('shared_json_projection', 'rdf_hybrid'):
        projection_source = prior_source if fault == 'stale_projection' else source
        projection_config = prior_config if fault == 'stale_projection' else installed
        view = project(projection_source, projection_config)
        state['data'] = state['projection'] = view
        state['provenance'].update(projected_source_hash=digest(projection_source),
                                  projected_config_hash=digest(projection_config),
                                  source_stale=digest(projection_source) != digest(source),
                                  config_stale=digest(projection_config) != digest(installed),
                                  projected_location_field=projection_config['location_field'],
                                  installed_location_field=installed['location_field'],
                                  projection_mapping_stale=projection_config['location_field'] != installed['location_field'],
                                  selected_view_hash=digest(view), selected_view_bytes=len(encoded(view)))
        if arm == 'rdf_hybrid':
            state['graph'] = graph_from_projection(view)
    return state


def execute(arm, state, subject, workflow, query):
    config = state['configs'].get(workflow, state['configs'].get('shared'))
    evidence = (retrieve_rdf(state['graph'], query, config, subject) if arm == 'rdf_hybrid'
                else retrieve_json(state['data'], config, subject,
                                   projected=arm == 'shared_json_projection'))
    return dict(output=decide(evidence, config, workflow), evidence=evidence)


def row_id(size, seed, snap, fault, subject, workflow, arm):
    return '/'.join(map(str, (size, seed, snap, fault, subject, workflow, arm)))


def planned_rows(sizes, seeds):
    return [row_id(size, seed, snap, fault, subject, workflow, arm)
            for size in sizes for seed in seeds for snap in SNAPSHOTS for fault in FAULTS
            for subject in SUBJECTS for workflow in WORKFLOWS for arm in ARMS]


def summarize(rows, planned):
    groups = {}
    for row in rows:
        key = '/'.join((row['arm'], row['fault']))
        group = groups.setdefault(key, dict(rows=0, errors=0, output_mismatches=0,
            evidence_mismatches=0, affected_workflows=set(), unnecessary_unknown=0,
            incorrect_positive_output=0, timings=[]))
        group['rows'] += 1
        group['timings'].append(row['elapsed_ms'])
        group['errors'] += row['status'] == 'error'
        if row['status'] == 'ok':
            group['output_mismatches'] += not row['output_match']
            group['evidence_mismatches'] += not row['evidence_match']
            if not row['output_match']:
                group['affected_workflows'].add(row['workflow'])
                decision = row['actual']['output']['decision']
                group['unnecessary_unknown'] += decision == 'unknown' and row['reference']['output']['decision'] != 'unknown'
                group['incorrect_positive_output'] += decision in ('clear', 'recommended')
    for group in groups.values():
        group['affected_workflows'] = sorted(group['affected_workflows'])
        group['median_ms_descriptive'] = statistics.median(group.pop('timings'))
    return dict(planned_rows=planned, completed_rows=len(rows), groups=groups)


def run(output, sizes=(24, 96), seeds=(17, 29)):
    if not sizes or len(set(sizes)) != len(sizes) or set(sizes) - {24, 96}:
        raise ValueError('Sizes must be a unique nonempty subset of 24,96')
    if not seeds or len(set(seeds)) != len(seeds) or set(seeds) - {17, 29}:
        raise ValueError('Seeds must be a unique nonempty subset of 17,29')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    ids = planned_rows(sizes, seeds)
    atomic_json(output / 'planned-row-ids.json', ids)
    manifest = dict(protocol='shared-semantics-1', created=datetime.now(UTC).isoformat(),
                    status='running', sizes=list(sizes), seeds=list(seeds), planned_rows=len(ids),
                    subjects=SUBJECTS, snapshots=SNAPSHOTS, faults=FAULTS, arms=ARMS, workflows=WORKFLOWS,
                    subject_design=SUBJECT_DESIGN,
                    snapshot_design='Each snapshot independently copies baseline; no cumulative updates',
                    stale_target_rule='WORKFLOWS[(seed + SNAPSHOTS.index(snapshot)) % 3]',
                    versions={'python': platform.python_version(),
                              'rdflib': importlib.metadata.version('rdflib')},
                    configuration_copies={'local_json': 3, 'shared_json_live': 1,
                        'shared_json_projection': 1, 'rdf_hybrid': 1},
                    semantics='Shared deterministic algorithm; independently copied local configurations',
                    reference_scope='Independent source candidate enumeration; shared decision algorithm, not external truth',
                    evidence_scope='All eligible candidate fields, including cost for countries/audit; mismatch need not change output',
                    selected_fields=['products.id', 'edges.id', 'edges.product', 'edges.supplier',
                                     'edges.role', 'suppliers.id', 'suppliers.<location_field>', 'suppliers.cost'],
                    timing_scope='resident retrieval plus decision; excludes build, serialization and scoring',
                    query=QUERY_TEXT, source_files={})
    for path in (Path(__file__), ROOT / 'uv.lock', ROOT / 'tests/test_shared_semantics_study.py'):
        blob = path.read_bytes()
        destination = output / 'executed-source' / path.name
        destination.parent.mkdir(exist_ok=True)
        destination.write_bytes(blob)
        manifest['source_files'][str(path.relative_to(ROOT))] = hashlib.sha256(blob).hexdigest()
    atomic_json(output / 'manifest.json', manifest)
    rows = []
    previous_handlers = {}
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f'Signal {signum}')
    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signum] = signal.signal(signum, interrupted)
    try:
        query = prepareQuery(QUERY_TEXT)
        with (output / 'rows.jsonl').open('x', encoding='utf-8') as handle:
            for size in sizes:
                for seed in seeds:
                    prior_source, prior_config = baseline(size, seed)
                    for snap in SNAPSHOTS:
                        source, intended = snapshot(prior_source, prior_config, snap)
                        snapshot_dir = output / 'snapshots' / f'{size}-{seed}-{snap}'
                        atomic_json(snapshot_dir / 'source.json', source)
                        atomic_json(snapshot_dir / 'intended-config.json', intended)
                        atomic_json(snapshot_dir / 'snapshot-manifest.json', dict(
                            source_hash=digest(source), intended_config_hash=digest(intended),
                            baseline_source_hash=digest(prior_source), baseline_config_hash=digest(prior_config)))
                        for fault in FAULTS:
                            states, errors = {}, {}
                            target = WORKFLOWS[(seed + SNAPSHOTS.index(snap)) % len(WORKFLOWS)]
                            for arm in ARMS:
                                arm_dir = snapshot_dir / fault / arm
                                try:
                                    state = deploy(arm, source, intended, prior_source, prior_config, fault, target)
                                    states[arm] = state
                                    atomic_json(arm_dir / 'configs.json', state['configs'])
                                    provenance = state['provenance']
                                    provenance.update(config_copy_count=3 if arm == 'local_json' else 1,
                                        configured_target=target if arm == 'local_json' else 'all_workflows',
                                        deployment_domains=list(state['configs']),
                                        deployment_domain_count=len(state['configs']),
                                        changed_config_slots=[k for k, c in state['configs'].items() if c != prior_config],
                                        required_config_touches_by_design=(3 if arm == 'local_json' else 1)
                                            if intended != prior_config else 0,
                                        installed_config_touches=sum(c != prior_config for c in state['configs'].values()))
                                    if state['projection'] is not None:
                                        atomic_json(arm_dir / 'projection.json', state['projection'])
                                    if state['graph'] is not None:
                                        rdf = state['graph'].serialize(format='nt').encode()
                                        (arm_dir / 'projection.nt').write_bytes(rdf)
                                        provenance.update(rdf_bytes=len(rdf), rdf_sha256=hashlib.sha256(rdf).hexdigest(),
                                                          rdf_triples=len(state['graph']))
                                    atomic_json(arm_dir / 'provenance.json', provenance)
                                except Exception as exc:
                                    errors[arm] = f'{type(exc).__name__}: {exc}'
                                    atomic_json(arm_dir / 'deployment-error.json', {'error': errors[arm]})
                            for subject in SUBJECTS:
                                evidence = reference_evidence(source, intended, subject)
                                for workflow in WORKFLOWS:
                                    reference = dict(output=decide(evidence, intended, workflow), evidence=evidence)
                                    for arm in ARMS:
                                        row = dict(id=row_id(size, seed, snap, fault, subject, workflow, arm),
                                            size=size, seed=seed, snapshot=snap, fault=fault, subject=subject,
                                            workflow=workflow, arm=arm, reference=reference)
                                        start = time.perf_counter()
                                        try:
                                            if arm in errors:
                                                raise RuntimeError(errors[arm])
                                            actual = execute(arm, states[arm], subject, workflow, query)
                                            row.update(status='ok', actual=actual,
                                                output_match=actual['output'] == reference['output'],
                                                evidence_match=actual['evidence'] == evidence)
                                        except Exception as exc:
                                            row.update(status='error', error=f'{type(exc).__name__}: {exc}')
                                        row['elapsed_ms'] = (time.perf_counter() - start) * 1000
                                        handle.write(encoded(row).decode() + '\n')
                                        handle.flush()
                                        os.fsync(handle.fileno())
                                        rows.append(row)
        manifest['status'] = 'complete_with_errors' if any(r['status'] == 'error' for r in rows) else 'complete'
    except BaseException as exc:
        manifest.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed',
                        error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        manifest.update(completed_rows=len(rows), finished=datetime.now(UTC).isoformat())
        atomic_json(output / 'summary.json', summarize(rows, len(ids)))
        atomic_json(output / 'manifest.json', manifest)
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Fresh directory; never overwrite a run')
    parser.add_argument('--sizes', type=int, nargs='+', default=[24, 96], choices=[24, 96])
    parser.add_argument('--seeds', type=int, nargs='+', default=[17, 29], choices=[17, 29])
    args = parser.parse_args()
    result = run(args.output, tuple(args.sizes), tuple(args.seeds))
    print(json.dumps(result, sort_keys=True))
    if result['status'] != 'complete':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
