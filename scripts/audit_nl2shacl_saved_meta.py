"""Read-only meta-SHACL audit of saved raw outputs; no repair or API calls."""
import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
from pathlib import Path

from rdflib import Graph
from pyshacl.entrypoints import meta_validate
from pyshacl.errors import ValidationFailure


def check(raw):
    try:
        graph = Graph().parse(data=raw, format='turtle')
    except Exception as exc:
        return {'status': 'parse_failure', 'error_type': type(exc).__name__, 'detail': str(exc)}
    try:
        conforms, report_graph, report_text = meta_validate(graph, inference='rdfs', do_owl_imports=False)
        if isinstance(report_graph, ValidationFailure):
            return {'status': 'unknown', 'detail': str(report_graph)}
        if type(conforms) is not bool:
            return {'status': 'unknown', 'detail': 'Non-boolean validation result'}
        return {'status': 'meta_conformant' if conforms else 'invalid_shape',
                'report': report_text, 'report_ttl': report_graph.serialize(format='turtle')}
    except Exception as exc:
        return {'status': 'runtime_exception', 'error_type': type(exc).__name__, 'detail': str(exc)}


def run(root, output):
    root, output = Path(root), Path(output)
    if output.exists():
        raise FileExistsError(output)
    previous_path = root / 'results.json'
    previous = json.loads(previous_path.read_text())
    ledger_path = root / 'campaign-budget.json'
    ledger = json.loads(ledger_path.read_text())
    old = {(r['id'], r['language']): r for r in previous['results']}
    assert len(old) == len(previous['results']) == len(ledger['reservations']) == 24
    assert len({(r['id'], r['language']) for r in ledger['reservations']}) == 24
    prefix = '@prefix ex: <urn:audit:> . @prefix sh: <http://www.w3.org/ns/shacl#> . '
    controls = {
        'valid': prefix + 'ex:S a sh:NodeShape ; sh:property [sh:path ex:p ; sh:minCount 1] .',
        'invalid': prefix + 'ex:S a sh:NodeShape ; sh:property [sh:path ex:p ; sh:minCount "one"] .',
        'parse_failure': 'ex:S a sh:NodeShape .',
    }
    control_results = {k: check(v) for k, v in controls.items()}
    results, hashes = [], {}
    for index, item in enumerate(ledger['reservations']):
        key = (item['id'], item['language'])
        prior = old[key]
        path = root / 'generation' / f'call-{index:04d}' / 'output.ttl'
        row = {'id': key[0], 'language': key[1], 'original_validity': prior['upstream_validity']}
        if not path.exists():
            row['meta'] = {'status': 'unknown', 'detail': 'Missing saved output'}
        else:
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            hashes[str(path)] = digest
            if digest != prior['raw_sha256']:
                raise RuntimeError('Saved output hash mismatch')
            row['raw_sha256'] = digest
            row['meta'] = check(raw.decode('utf-8'))
        results.append(row)
    for path in (previous_path, ledger_path, Path(__file__)):
        hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    record = {'scope': 'Raw saved 24 outputs; meta-SHACL conformance is not requirement correctness.',
              'versions': {p: importlib.metadata.version(p) for p in ('rdflib', 'pyshacl')},
              'operation': 'pyshacl.entrypoints.meta_validate, inference=rdfs, do_owl_imports=False',
              'control_ttl': controls, 'controls': control_results, 'hashes': hashes,
              'summary': {lang: dict(Counter(r['meta']['status'] for r in results if r['language'] == lang)) for lang in ('en', 'ko')},
              'results': results, 'paid_calls': 0}
    with output.open('x') as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
    assert {k: v['status'] for k, v in control_results.items()} == {
        'valid': 'meta_conformant', 'invalid': 'invalid_shape', 'parse_failure': 'parse_failure'}
    print(json.dumps(record['summary']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    run(args.root, args.output)
