"""Offline diagnostic of frozen advisory checkers at their input boundaries."""
import argparse
import json
from pathlib import Path

from rdflib import Graph
from scripts.backend_advisory import python_report, shacl_report
from scripts.backend_parity import canonical


def cases():
    same = lambda value: {'used_input_hash': value, 'current_input_hash': value}
    values = {
        'canonical_same': 'a' * 64, 'empty': '', 'short': 'a' * 63,
        'long': 'a' * 65, 'uppercase': 'A' * 64,
        'lf_suffix': 'a' * 64 + '\n', 'crlf_suffix': 'a' * 64 + '\r\n',
        'lf_prefix': '\n' + 'a' * 64, 'space_suffix': 'a' * 64 + ' ',
        'unicode': 'ａ' * 64, 'integer': 123, 'boolean': True,
        'list': ['a' * 64], 'dictionary': {'value': 'a' * 64},
    }
    rows = [{'id': name, 'metadata': same(value), 'cohort': 'authored_boundary'} for name, value in values.items()]
    rows += [
        {'id': 'canonical_different', 'metadata': {'used_input_hash': 'a' * 64, 'current_input_hash': 'b' * 64}, 'cohort': 'authored_boundary'},
        {'id': 'missing_both', 'metadata': {}, 'cohort': 'authored_boundary'},
        {'id': 'missing_current', 'metadata': {'used_input_hash': 'a' * 64}, 'cohort': 'authored_boundary'},
    ]
    return rows


def run(shapes_path, output):
    output.mkdir(parents=True, exist_ok=False)
    inputs = cases()
    plan = [{'id': row['id'], 'checker': checker} for row in inputs for checker in ('python', 'shacl')]
    (output / 'inputs.json').write_text(canonical(inputs) + '\n')
    (output / 'plan.json').write_text(canonical(plan) + '\n')
    (output / 'runtime.py').write_bytes(Path(__file__).read_bytes())
    (output / 'advisory-runtime.py').write_bytes(Path('scripts/backend_advisory.py').read_bytes())
    (output / 'shapes.ttl').write_bytes(shapes_path.read_bytes())
    shapes = Graph().parse(shapes_path, format='turtle')
    with (output / 'results.jsonl').open('a') as handle:
        for item in inputs:
            for checker in ('python', 'shacl'):
                row = {'id': item['id'], 'checker': checker}
                try:
                    if checker == 'python':
                        codes = python_report(item['metadata'])
                    else:
                        result = shacl_report(item['metadata'], shapes)
                        codes = result['codes']
                        (output / (item['id'] + '-report.ttl')).write_text(result['validation_graph'])
                        row['conforms'] = result['conforms']
                    row.update(status='completed', codes=codes, review_requested=bool(codes))
                except Exception as error:
                    row.update(status='checker_failure', error=f'{type(error).__name__}: {error}')
                handle.write(canonical(row) + '\n')
                handle.flush()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--shapes', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.shapes, args.output)
