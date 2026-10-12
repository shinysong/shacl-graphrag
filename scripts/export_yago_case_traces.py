"""Export selected existing YAGO case traces without rerunning the model."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = '20261012T123009Z-yago-selective-abb7e636'


def main():
    root = ROOT / 'runs' / RUN
    record = json.loads((root / 'record.json').read_text())
    assert record['status'] == 'completed'
    selected = [(person + '-wrong_place', 'S2') for person in
                ('Abu_Nuwas', 'Annette_Salmeen', 'Anne_Hutchinson')]
    selected += [('Abu_Nuwas-' + variant, condition) for variant, conditions in
                 [('clean', ['S2']), ('wrong_datatype', ['G1', 'S2']),
                  ('missing_relation', ['G1', 'S2']), ('wrong_class', ['G0', 'S2']),
                  ('source_missing_relation', ['G0', 'S2'])] for condition in conditions]
    output = {'run_id': RUN, 'record_sha256': hashlib.sha256((root / 'record.json').read_bytes()).hexdigest(),
              'note': 'Selected actual traces. Injected faults; no new model calls. Null request means policy abstained before LLM.',
              'samples': []}
    for case_id, condition in selected:
        case = next(c for c in record['cases'] if c['id'] == case_id)
        row = next(r for r in record['rows'] if r['case_id'] == case_id and r['condition'] == condition)
        directory = root / case_id / condition
        request = json.loads((directory / 'request.json').read_text()) if (directory / 'request.json').exists() else None
        response = json.loads((directory / 'response.json').read_text()) if request else None
        original_content = response['choices'][0]['message']['content'] if response else None
        if original_content:
            assert json.loads(original_content) == row['answer']
        files = {name: (root / case_id / name).read_text() for name in ('source.ttl', 'first.ttl')}
        files['evidence.ttl'] = (directory / 'evidence.ttl').read_text()
        output['samples'].append({'case': case, 'result': row, 'request': request,
                                  'model_response_content': original_content, 'graphs': files})
    target = ROOT / 'docs/experiments/records' / (RUN + '-samples.json')
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    print(f'{len(output["samples"])} actual traces exported: {target.name}')


if __name__ == '__main__':
    main()
