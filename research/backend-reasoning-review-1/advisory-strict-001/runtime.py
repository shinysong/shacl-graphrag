"""Versioned metadata contract: shared input gate plus exact-length SHACL.

This diagnostic preserves v1 outputs; a rejected input is not SHACL conformance.
"""
import argparse
import json
from pathlib import Path

from rdflib import Graph
from scripts.backend_advisory import python_report, shacl_report
from scripts.backend_parity import canonical

FIELDS = {'used_input_hash', 'current_input_hash'}


def input_error(metadata):
    if not isinstance(metadata, dict):
        return 'metadata_must_be_object'
    if set(metadata) - FIELDS:
        return 'unexpected_metadata_field'
    if any(value is not None and not isinstance(value, str) for value in metadata.values()):
        return 'fingerprint_must_be_string_or_null'
    return None


def run(parents, shapes_path, output):
    output.mkdir(parents=True, exist_ok=False)
    inputs = []
    for parent in parents:
        for item in json.loads((parent / 'inputs.json').read_text()):
            inputs.append({**item, 'id': parent.name + '/' + item['id'], 'parent_run': parent.name, 'parent_id': item['id']})
    plan = [{'id': item['id'], 'checker': checker} for item in inputs for checker in ('python', 'shacl')]
    (output / 'inputs.json').write_text(canonical(inputs) + '\n')
    (output / 'plan.json').write_text(canonical(plan) + '\n')
    (output / 'runtime.py').write_bytes(Path(__file__).read_bytes())
    (output / 'advisory-runtime.py').write_bytes(Path('scripts/backend_advisory.py').read_bytes())
    (output / 'shapes.ttl').write_bytes(shapes_path.read_bytes())
    shapes = Graph().parse(shapes_path, format='turtle')
    with (output / 'results.jsonl').open('a') as handle:
        for index, item in enumerate(inputs):
            error = input_error(item['metadata'])
            for checker in ('python', 'shacl'):
                row = {'id': item['id'], 'checker': checker, 'parent_run': item['parent_run'], 'parent_id': item['parent_id'], 'answer_changed': False}
                if 'original_answer' in item:
                    row['original_answer'] = item['original_answer']
                    row['original_status'] = item['original_status']
                if error:
                    row.update(status='input_rejected', error=error, decision='invalid_input_not_conformance')
                else:
                    try:
                        if checker == 'python':
                            codes = python_report(item['metadata'])
                        else:
                            report = shacl_report(item['metadata'], shapes)
                            codes = report['codes']
                            row['conforms'] = report['conforms']
                            (output / f'{index}-report.ttl').write_text(report['validation_graph'])
                        row.update(status='completed', codes=codes, review_requested=bool(codes), decision='advisory_only_no_veto')
                    except Exception as exc:
                        row.update(status='checker_failure', error=f'{type(exc).__name__}: {exc}')
                handle.write(canonical(row) + '\n')
                handle.flush()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--parent', type=Path, action='append', required=True)
    parser.add_argument('--shapes', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.parent, args.shapes, args.output)
