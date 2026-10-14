"""Independently reconcile saved shared-semantics artifacts; never repairs a run."""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ARMS = ('local_json', 'shared_json_live', 'shared_json_projection', 'rdf_hybrid')
TASKS = ('countries', 'audit', 'recommend')
STATES = ('initial', 'allow_backup', 'rename_country_field', 'add_substitute_role',
          'restrict_country', 'supplier_move', 'remove_country', 'cost_change')
FAULTS = ('clean', 'stale_config_copy', 'stale_projection', 'common_wrong_mapping')
SUBJECTS = tuple(f'p{i}' for i in range(7)) + ('p_missing',)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def semantic_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def reference(source, policy, subject, task):
    """Separate decision derivation from frozen source, with no runner import."""
    exists = subject in {x['id'] for x in source['products']}
    people = {x['id']: x for x in source['suppliers']}
    candidates = []
    for edge in sorted(source['edges'], key=lambda x: x['id']):
        meaning = policy['role_aliases'].get(edge['role'])
        if not exists or edge['product'] != subject or meaning not in policy['allowed_roles']:
            continue
        supplier = people.get(edge['supplier'], {})
        candidates.append(dict(edge=edge['id'], supplier=edge['supplier'], raw_role=edge['role'],
                               role=meaning, country=supplier.get(policy['location_field']),
                               cost=supplier.get('cost')))
    evidence = dict(product_exists=exists, candidates=candidates)
    known = {c['country'] for c in candidates if c['country'] is not None}
    missing = not candidates or any(c['country'] is None for c in candidates)
    prohibited = known.intersection(policy['restricted_countries'])
    if task == 'countries':
        output = dict(decision='unknown' if missing else 'complete', value=sorted(known))
    elif task == 'audit':
        decision = 'blocked' if prohibited else ('unknown' if missing else 'clear')
        output = dict(decision=decision, value=None)
    elif task == 'recommend':
        ranked = sorted((c['cost'], c['supplier']) for c in candidates
                        if c['country'] not in policy['restricted_countries'] and c['cost'] is not None)
        if missing or any(c['cost'] is None for c in candidates):
            output = dict(decision='unknown', value=None)
        elif ranked:
            output = dict(decision='recommended', value=ranked[0][1])
        else:
            output = dict(decision='unavailable', value=None)
    else:
        raise ValueError(task)
    return dict(output=output, evidence=evidence)


def reconcile(manifest, ids, rows):
    if (manifest['sizes'] != [24, 96] or manifest['seeds'] != [17, 29]
            or manifest['protocol'] != 'shared-semantics-1'):
        raise ValueError('Analysis requires the declared full campaign')
    expected = {'/'.join(map(str, (n, seed, state, fault, subject, task, arm)))
                for n in [24, 96] for seed in [17, 29] for state in STATES for fault in FAULTS
                for subject in SUBJECTS for task in TASKS for arm in ARMS}
    if len(expected) != 12288 or len(ids) != len(expected) or set(ids) != expected:
        raise ValueError('Planned matrix missing or duplicated')
    if len(rows) != len(expected) or {r['id'] for r in rows} != expected:
        raise ValueError('Executed matrix missing or duplicated')
    for row in rows:
        bound = '/'.join(str(row[k]) for k in ('size', 'seed', 'snapshot', 'fault', 'subject', 'workflow', 'arm'))
        if bound != row['id'] or row['status'] != 'ok':
            raise ValueError('Row binding or execution failure')
    if manifest['status'] != 'complete' or manifest['completed_rows'] != 12288 or manifest['planned_rows'] != 12288:
        raise ValueError('Manifest incomplete')


def analyze(run, output):
    output.mkdir(parents=True, exist_ok=False)
    result = {'status': 'running', 'run_id': run.name, 'analysis_source_sha256': sha(__file__)}
    def save():
        (output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    save()
    try:
        manifest = read(run / 'manifest.json')
        rows = [json.loads(line) for line in (run / 'rows.jsonl').read_text().splitlines()]
        reconcile(manifest, read(run / 'planned-row-ids.json'), rows)
        for relative, expected_hash in manifest['source_files'].items():
            if sha(run / 'executed-source' / Path(relative).name) != expected_hash:
                raise ValueError('Archived source mismatch')
        groups, by_workflow, per_context, provenance, refs = {}, {}, defaultdict(set), {}, {}
        for size in manifest['sizes']:
            for seed in manifest['seeds']:
                for state in STATES:
                    folder = run / 'snapshots' / f'{size}-{seed}-{state}'
                    source, intended = read(folder / 'source.json'), read(folder / 'intended-config.json')
                    snapshot_meta = read(folder / 'snapshot-manifest.json')
                    if (semantic_digest(source) != snapshot_meta['source_hash']
                            or semantic_digest(intended) != snapshot_meta['intended_config_hash']):
                        raise ValueError('Snapshot source or policy hash mismatch')
                    for subject in SUBJECTS:
                        for task in TASKS:
                            refs[size, seed, state, subject, task] = reference(source, intended, subject, task)
                    for fault in FAULTS:
                        left = read(folder / fault / 'shared_json_projection' / 'projection.json')
                        right = read(folder / fault / 'rdf_hybrid' / 'projection.json')
                        if left != right:
                            raise ValueError('Matched projection inputs differ')
                        for arm in ARMS:
                            configs = read(folder / fault / arm / 'configs.json')
                            prov = read(folder / fault / arm / 'provenance.json')
                            if arm == 'rdf_hybrid' and sha(folder / fault / arm / 'projection.nt') != prov['rdf_sha256']:
                                raise ValueError('RDF file hash mismatch')
                            if prov['current_source_hash'] != semantic_digest(source):
                                raise ValueError('Deployed source provenance mismatch')
                            if {k: semantic_digest(v) for k, v in configs.items()} != prov['installed_config_hashes']:
                                raise ValueError('Deployed config hash mismatch')
                            if arm in ('shared_json_projection', 'rdf_hybrid'):
                                if semantic_digest(left) != prov['selected_view_hash']:
                                    raise ValueError('Projection hash mismatch')
                            for task in TASKS:
                                installed = configs[task if arm == 'local_json' else 'shared']
                                provenance[size, seed, state, fault, arm, task] = dict(
                                    config_differs=installed != intended,
                                    projection_stale=prov.get('source_stale', False) or prov.get('projection_mapping_stale', False))
        for row in rows:
            ref = refs[row['size'], row['seed'], row['snapshot'], row['subject'], row['workflow']]
            if row['reference'] != ref:
                raise ValueError('Independent reference mismatch: ' + row['id'])
            output_ok = row['actual']['output'] == ref['output']
            evidence_ok = row['actual']['evidence'] == ref['evidence']
            if (row['output_match'], row['evidence_match']) != (output_ok, evidence_ok):
                raise ValueError('Saved score mismatch')
            context = (row['size'], row['seed'], row['snapshot'], row['fault'], row['arm'])
            exposure = provenance[*context, row['workflow']]
            if not output_ok:
                per_context[context].add(row['workflow'])
            for container, key in [(groups, row['arm'] + '/' + row['fault']),
                                   (by_workflow, row['arm'] + '/' + row['fault'] + '/' + row['workflow'])]:
                g = container.setdefault(key, dict(rows=0, output_errors=0, evidence_errors=0,
                    config_differs_rows=0, projection_stale_rows=0, unnecessary_unknown=0,
                    missed_restriction=0, unwarranted_audit_block=0, incorrect_recommendation=0))
                g['rows'] += 1
                g['output_errors'] += not output_ok
                g['evidence_errors'] += not evidence_ok
                g['config_differs_rows'] += exposure['config_differs']
                g['projection_stale_rows'] += exposure['projection_stale']
                actual, expected = row['actual']['output'], ref['output']
                g['unnecessary_unknown'] += actual['decision'] == 'unknown' and expected['decision'] != 'unknown'
                g['missed_restriction'] += row['workflow'] == 'audit' and expected['decision'] == 'blocked' and actual['decision'] == 'clear'
                g['unwarranted_audit_block'] += row['workflow'] == 'audit' and actual['decision'] == 'blocked' and expected['decision'] != 'blocked'
                g['incorrect_recommendation'] += row['workflow'] == 'recommend' and actual['decision'] == 'recommended' and not output_ok
        paired = {}
        lookup = {r['id']: r for r in rows}
        for row in rows:
            if row['arm'] == 'rdf_hybrid':
                other = lookup[row['id'].rsplit('/', 1)[0] + '/shared_json_projection']
                key = row['fault']
                p = paired.setdefault(key, dict(rows=0, output_differences=0, evidence_differences=0))
                p['rows'] += 1
                p['output_differences'] += row['actual']['output'] != other['actual']['output']
                p['evidence_differences'] += row['actual']['evidence'] != other['actual']['evidence']
        result.update(status='complete', rows=len(rows), independent_reference_rows=len(rows), groups=groups,
                      by_workflow=by_workflow, matched_projection_parity=paired,
                      affected_contexts=[dict(size=k[0], seed=k[1], snapshot=k[2], fault=k[3], arm=k[4],
                                              workflows=sorted(v)) for k, v in sorted(per_context.items())],
                      configuration_copies=manifest['configuration_copies'], versions=manifest['versions'],
                      caveats=['Deterministic fault injection; not failure probabilities or labor cost.',
                               'Same pinned foreground; sizes/seeds are not independent business populations.',
                               'Shared final decision algorithm; independent artifact scorer checks declared semantics.',
                               'No LLM, OWL, SHACL, graph server or external factual truth measurement.'])
        # Compact full outcomes retain references to immutable snapshot IDs and evidence hashes.
        compact = [{k: r[k] for k in ('id', 'status', 'output_match', 'evidence_match')} |
                   dict(output=r['actual']['output'], expected=r['reference']['output'],
                        actual_evidence_sha256=hashlib.sha256(json.dumps(r['actual']['evidence'], sort_keys=True).encode()).hexdigest())
                   for r in rows]
        (output / 'outcomes.json').write_text(json.dumps(compact, separators=(',', ':')) + '\n')
        # Purposeful examples fixed before observing outcomes, with all four arms.
        selections = [('allow_backup', 'stale_config_copy', 'p0'),
                      ('rename_country_field', 'stale_config_copy', 'p3'),
                      ('supplier_move', 'stale_projection', 'p3'),
                      ('remove_country', 'stale_projection', 'p3'),
                      ('cost_change', 'stale_projection', 'p4'),
                      ('restrict_country', 'common_wrong_mapping', 'p4')]
        samples = [r for r in rows if r['size'] == 24 and r['seed'] == 17
                   and (r['snapshot'], r['fault'], r['subject']) in selections]
        (output / 'samples.json').write_text(json.dumps(samples, indent=2) + '\n')
    except BaseException as exc:
        result.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        save()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.run, args.output)
    print(json.dumps({'status': result['status'], 'rows': result['rows']}))


if __name__ == '__main__':
    main()
