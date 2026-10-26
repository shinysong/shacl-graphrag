"""Posthoc scorer of saved outputs; no runtime imports, execution, or answer repair."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score(fixture, run):
    manifest, plan = read(fixture / 'manifest.json'), read(run / 'plan.json')
    assert sha(fixture / 'manifest.json') == plan['fixture_manifest_sha256']
    assert plan['arms'] in (['python_rules', 'rdf_owl_shacl'], ['asserted_only'])
    assert plan['scenes'] == [s['scene_id'] for s in manifest['scenes']] and len(plan['scenes']) == 24
    completed = read(run / 'completed.json') if (run / 'completed.json').exists() else None
    verified = {r['file']: r['sha256'] for r in completed['outputs']} if completed else {}
    results = {}
    for arm in plan['arms']:
        pairs = {name: Counter() for name in ('receipt', 'links', 'candidate', 'recheck', 'impact_graph_completeness')}
        strata, errors, depths = {}, Counter(), {}
        for entry in manifest['scenes']:
            sid = entry['scene_id']
            ename, lname = f'scorer/{sid}-expected.json', f'scorer/{sid}-lineage.json'
            assert sha(fixture / ename) == entry['files'][ename] and sha(fixture / lname) == entry['files'][lname]
            expected, lineage = read(fixture / ename), read(fixture / lname)
            filename = f'{sid}-{arm}.json'; path = run / filename
            output = None
            if path.exists():
                if completed:
                    assert filename in verified and sha(path) == verified[filename]
                envelope = read(path)
                assert envelope['scene_id'] == sid and envelope['arm'] == arm
                if envelope['status'] == 'ok':
                    output = envelope['raw_output']
                else:
                    errors[envelope['error']['stage']] += 1
            else:
                errors['missing_attempt'] += 1
            def add(name, ref, predicted):
                pairs[name][ref + ' -> ' + predicted] += 1
            add('receipt', expected['receipt'], output['receipt'] if output else 'error')
            for key, ref in expected['links'].items():
                add('links', ref, output['links'][key] if output else 'error')
            add('impact_graph_completeness', expected['impact_graph_completeness'], output['impact_graph_completeness'] if output else 'error')
            products = {(p['id'], p['revision']): p for p in output['products']} if output else {}
            family = lineage['family']
            depth = str(lineage['depth'])
            depths.setdefault(depth, {'candidate': Counter(), 'recheck': Counter()})
            strata.setdefault(family, Counter())
            for p in expected['products']:
                pred = products.get((p['id'], p['revision']))
                for name in ('candidate', 'recheck'):
                    value = pred[name] if pred else 'error'
                    add(name, p[name], value)
                    depths[depth][name][p[name] + ' -> ' + value] += 1
                    strata[family][name + ':' + value] += 1
        denominators = {name: sum(v.values()) for name, v in pairs.items()}
        assert denominators == {'receipt':24,'links':72,'candidate':96,'recheck':96,'impact_graph_completeness':24}
        matrix = {r: {p: pairs['recheck'][r+' -> '+p] for p in ('required','not_required','unknown','error')}
                  for r in ('required','not_required','unknown')}
        results[arm] = {'denominators': denominators, 'confusions': {k:dict(v) for k,v in pairs.items()},
                        'depth_confusions': {d:{k:dict(v) for k,v in metrics.items()} for d,metrics in depths.items()}, 'recheck_matrix':matrix, 'error_scenes':dict(errors), 'family_prediction_counts':{k:dict(v) for k,v in strata.items()}}
    return {'interpretation':'Authored development policy agreement only; shared adapter/recheck. No business truth or superiority claim.', 'arms':results}


if __name__ == '__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--fixture',type=Path,required=True);ap.add_argument('--run',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();result=score(a.fixture,a.run)
    with a.output.open('x') as stream: json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result))
