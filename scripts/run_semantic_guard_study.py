"""Offline veto-only replay of shared-semantics-1; synthetic metadata, not truth validation."""
import argparse
import copy
import hashlib
import json
import os
import signal
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

try:
    from scripts.analyze_shared_semantics_study import reconcile, read, sha, semantic_digest as digest
except ModuleNotFoundError:
    from analyze_shared_semantics_study import reconcile, read, sha, semantic_digest as digest

ROOT = Path(__file__).resolve().parents[1]
TASKS = ('countries', 'audit', 'recommend')
GUARDS = {'none': (), 'cross_only': ('cross',), 'version_only': ('whole',),
          'semantic_only': ('semantic',), 'all_checks': ('cross', 'whole', 'semantic'),
          'selective_checks': ('cross', 'selective', 'semantic')}
CATALOGS = {'documented': {'old_country': 'operating_country', 'new_country': 'operating_country',
                           'tax_country': 'tax_country'}, 'absent': {},
            'mislabeled': {'old_country': 'operating_country', 'new_country': 'operating_country',
                           'tax_country': 'operating_country'}}
EXPECTED = 12288 * len(GUARDS) * len(CATALOGS)


def save(path, value):
    pending = path.with_suffix('.pending')
    with pending.open('w') as handle:
        json.dump(value, handle, sort_keys=True)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
    pending.replace(path)


def dependency(data, mapping, subject, task, projected=False):
    """Raw connected slice, including inactive edges; no answer computation."""
    products = data['products'] if projected else [p['id'] for p in data['products']]
    suppliers = {s['id']: s for s in data['suppliers']}
    edges = sorted((e for e in data['edges'] if e['product'] == subject), key=lambda e: e['id'])
    connected = []
    for edge in edges:
        supplier = suppliers.get(edge['supplier'], {})
        item = dict(edge=edge, supplier_id=edge['supplier'],
                    country=supplier.get('country' if projected else mapping))
        if task == 'recommend':
            item['cost'] = supplier.get('cost')
        connected.append(item)
    return dict(product_exists=subject in products, mapping_field=mapping, connected=connected)


def policy(config, task):
    keys = ['location_field', 'role_aliases', 'allowed_roles']
    if task != 'countries':
        keys.append('restricted_countries')
    return {k: config[k] for k in keys}


def make_packet(actuals, configs, publisher, source, consumed_source, subject,
                projection=None, projection_mapping=None):
    """Explicit runtime inputs only. Build hashes before invoking pure guards."""
    if set(actuals) != set(TASKS):
        raise ValueError('Exactly three runtime workflows required')
    packet = dict(actuals=copy.deepcopy(actuals), publisher=copy.deepcopy(publisher), workflows={})
    for task in TASKS:
        installed = configs[task] if task in configs else configs['shared']
        mapping = projection_mapping if projection is not None else installed['location_field']
        consumed = projection if projection is not None else consumed_source
        packet['workflows'][task] = dict(installed=copy.deepcopy(installed),
            projection_mapping=projection_mapping if projection is not None else None,
            hashes=dict(projected_mapping=digest(projection_mapping), installed_mapping=digest(installed['location_field']),
                current_source=digest(source), consumed_source=digest(consumed_source),
                published_config=digest(publisher), installed_config=digest(installed),
                current_dependency=digest(dependency(source, publisher['location_field'], subject, task)),
                consumed_dependency=digest(dependency(consumed, mapping, subject, task, projection is not None)),
                published_policy=digest(policy(publisher, task)), installed_policy=digest(policy(installed, task))))
    return packet


def cross_guard(packet):
    actual = packet['actuals']
    countries = actual['countries']['output']
    reasons = []
    if countries['decision'] == 'complete':
        known = set(countries['value'])
        restricted = set(packet['publisher']['restricted_countries'])
        expected = 'blocked' if known & restricted else 'clear'
        if actual['audit']['output']['decision'] != expected:
            reasons.append('audit_countries_contradiction')
        recommendation = actual['recommend']['output']
        if recommendation['decision'] == 'recommended':
            selected = [c for c in actual['recommend']['evidence']['candidates']
                        if c['supplier'] == recommendation['value']]
            if not selected or any(c['country'] not in known or c['country'] in restricted for c in selected):
                reasons.append('recommend_countries_contradiction')
    return dict(status='conflict' if reasons else 'valid', reasons=reasons)


def freshness_guard(packet, task, selective=False):
    record = packet['workflows'][task]
    hashes = record['hashes']
    pairs = [('current_dependency', 'consumed_dependency'), ('published_policy', 'installed_policy')] if selective else [
        ('current_source', 'consumed_source'), ('published_config', 'installed_config')]
    reasons = [left + '_mismatch' for left, right in pairs if hashes[left] != hashes[right]]
    # Mapping identity is metadata, represented by a digest just like other freshness inputs.
    if not selective and record['projection_mapping'] is not None:
        if hashes['projected_mapping'] != hashes['installed_mapping']:
            reasons.append('projection_mapping_mismatch')
    return dict(status='conflict' if reasons else 'valid', reasons=reasons)


def semantic_guard(packet, task, catalog):
    record = packet['workflows'][task]
    fields = [record['installed']['location_field']]
    if record['projection_mapping'] is not None:
        fields.append(record['projection_mapping'])
    reasons = [('missing:' if field not in catalog else 'conflict:') + field
               for field in sorted(set(fields)) if catalog.get(field) != 'operating_country']
    status = 'conflict' if any(r.startswith('conflict:') for r in reasons) else 'missing' if reasons else 'valid'
    return dict(status=status, reasons=reasons)


def checks(packet, task, catalog):
    return dict(cross=cross_guard(packet), whole=freshness_guard(packet, task),
                selective=freshness_guard(packet, task, True), semantic=semantic_guard(packet, task, catalog))


def evaluate(actual, reference, allowed):
    """Scoring boundary: saved reference is never supplied to runtime guards."""
    correct = actual['output'] == reference['output']
    known = reference['output']['decision'] != 'unknown'
    outcome = ('correct_retained' if allowed else 'correct_withheld') if correct else (
        'wrong_allowed' if allowed else 'wrong_withheld')
    return dict(outcome=outcome, unnecessary_abstention=correct and known and not allowed,
                correct_unknown_withheld=correct and not known and not allowed,
                reference_known=known)


def validate_rows(manifest, ids, rows):
    reconcile(manifest, ids, rows)
    groups = defaultdict(dict)
    for row in rows:
        key = tuple(row[k] for k in ('size', 'seed', 'snapshot', 'fault', 'subject', 'arm'))
        if row['workflow'] in groups[key] or set(row['actual']) != {'output', 'evidence'}:
            raise ValueError('Duplicate workflow or malformed actual')
        groups[key][row['workflow']] = row
    if any(set(group) != set(TASKS) for group in groups.values()):
        raise ValueError('Incomplete workflow group')
    return groups


def load_packet(run, key, rows):
    """Replay harness reconstructs controlled releases; fault labels stay here."""
    size, seed, snapshot, fault, subject, arm = key
    folder = run / 'snapshots' / f'{size}-{seed}-{snapshot}'
    initial = run / 'snapshots' / f'{size}-{seed}-initial'
    source, publisher = read(folder / 'source.json'), read(folder / 'intended-config.json')
    metadata = read(folder / 'snapshot-manifest.json')
    if digest(source) != metadata['source_hash'] or digest(publisher) != metadata['intended_config_hash']:
        raise ValueError('Snapshot digest mismatch')
    if fault == 'common_wrong_mapping':
        publisher['location_field'] = 'tax_country'
    deployed = folder / fault / arm
    configs, provenance = read(deployed / 'configs.json'), read(deployed / 'provenance.json')
    if (digest(source) != provenance['current_source_hash'] or
            {k: digest(v) for k, v in configs.items()} != provenance['installed_config_hashes']):
        raise ValueError('Runtime provenance mismatch')
    projection, mapping, consumed = None, None, source
    if arm in ('shared_json_projection', 'rdf_hybrid'):
        projection = read(deployed / 'projection.json')
        mapping = provenance['projected_location_field']
        consumed = read(initial / 'source.json') if fault == 'stale_projection' else source
        projection_config = read(initial / 'intended-config.json') if fault == 'stale_projection' else configs['shared']
        if (digest(projection) != provenance['selected_view_hash'] or
                digest(consumed) != provenance['projected_source_hash'] or
                digest(projection_config) != provenance['projected_config_hash'] or
                mapping != projection_config['location_field']):
            raise ValueError('Materialization provenance mismatch')
        reconstructed = dict(products=[p['id'] for p in consumed['products']],
            edges=consumed['edges'], suppliers=[dict(id=s['id'], country=s.get(mapping), cost=s.get('cost'))
                                               for s in consumed['suppliers']])
        if projection != reconstructed:
            raise ValueError('Saved projection differs from consumed inputs')
        if arm == 'rdf_hybrid' and sha(deployed / 'projection.nt') != provenance['rdf_sha256']:
            raise ValueError('RDF digest mismatch')
    return make_packet({task: rows[task]['actual'] for task in TASKS}, configs, publisher,
                       source, consumed, subject, projection, mapping)


def run_replay(run, output):
    output.mkdir(parents=True, exist_ok=False)
    manifest = dict(protocol='semantic-guards-1', original_run_id=run.name, status='running',
                    planned_rows=EXPECTED, completed_rows=0, started=datetime.now(UTC).isoformat(),
                    catalogs=CATALOGS, guards=GUARDS,
                    publisher_channel='Current controlled release; common_wrong_mapping publishes tax_country too.',
                    catalog_scope='Handcrafted synthetic metadata; not independent source-field verification.')
    summary = defaultdict(Counter)
    save(output / 'manifest.json', manifest)
    previous = {}
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f'Signal {signum}')
    for sig in (signal.SIGINT, signal.SIGTERM):
        previous[sig] = signal.signal(sig, interrupted)
    try:
        manifest['input_files'] = {str(p.relative_to(run)): sha(p) for p in sorted(run.rglob('*')) if p.is_file()}
        archive = output / 'executed-source'
        archive.mkdir()
        manifest['source_files'] = {}
        for path in (Path(__file__), ROOT / 'scripts/analyze_shared_semantics_study.py',
                     ROOT / 'scripts/analyze_semantic_guard_study.py', ROOT / 'uv.lock',
                     ROOT / 'tests/test_semantic_guard_study.py'):
            (archive / path.name).write_bytes(path.read_bytes())
            manifest['source_files'][str(path.relative_to(ROOT))] = sha(path)
        base_manifest = read(run / 'manifest.json')
        for relative, expected_hash in base_manifest['source_files'].items():
            if sha(run / 'executed-source' / Path(relative).name) != expected_hash:
                raise ValueError('Base archived source mismatch')
        rows = [json.loads(line) for line in (run / 'rows.jsonl').read_text().splitlines()]
        groups = validate_rows(base_manifest, read(run / 'planned-row-ids.json'), rows)
        manifest['catalog_hashes'] = {name: digest(catalog) for name, catalog in CATALOGS.items()}
        packet_folder = output / 'runtime-packets'
        packet_folder.mkdir()
        save(output / 'manifest.json', manifest)
        with (output / 'rows.jsonl').open('x') as handle:
            for key, group in sorted(groups.items()):
                packet = load_packet(run, key, group)
                packet_id = digest(packet)
                if not (packet_folder / (packet_id + '.json')).exists():
                    save(packet_folder / (packet_id + '.json'), packet)
                for catalog_name, catalog in CATALOGS.items():
                    for task in TASKS:
                        row = group[task]
                        results = checks(packet, task, catalog)
                        for guard, selected in GUARDS.items():
                            reasons = {name: results[name]['reasons'] for name in selected
                                       if results[name]['status'] != 'valid'}
                            allowed = not reasons
                            result = dict(id=row['id'] + '/' + catalog_name + '/' + guard,
                                base_id=row['id'], packet_id=packet_id, guard=guard, catalog=catalog_name,
                                catalog_hash=manifest['catalog_hashes'][catalog_name],
                                arm=row['arm'], fault=row['fault'], workflow=task,
                                allowed=allowed, veto_reasons=reasons, checks=results,
                                output=row['actual']['output'], dependency_status=results['selective']['status'],
                                **evaluate(row['actual'], row['reference'], allowed))
                            handle.write(json.dumps(result, sort_keys=True) + '\n')
                            manifest['completed_rows'] += 1
                            counts = summary['/'.join((guard, catalog_name, row['arm'], row['fault'], task))]
                            counts.update(['rows', result['outcome']])
                            counts['unnecessary_abstention'] += result['unnecessary_abstention']
                            counts['correct_unknown_withheld'] += result['correct_unknown_withheld']
                            if manifest['completed_rows'] % 512 == 0:
                                handle.flush()
                                os.fsync(handle.fileno())
                                save(output / 'manifest.json', manifest)
            handle.flush()
            os.fsync(handle.fileno())
        if manifest['completed_rows'] != EXPECTED:
            raise ValueError('Decision matrix incomplete')
        manifest['status'] = 'complete'
    except BaseException as exc:
        manifest.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed',
                        error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        manifest['finished'] = datetime.now(UTC).isoformat()
        save(output / 'summary.json', dict(rows=manifest['completed_rows'], groups=dict(summary)))
        save(output / 'manifest.json', manifest)
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=ROOT / 'runs/20261014T063154Z-shared-semantics')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_replay(args.run, args.output), sort_keys=True))
