"""Posthoc-only scoring. Never imported by the paid request runner."""
import argparse
import hashlib
import json
from pathlib import Path

from scripts.sbom_contracts import read_document, contract_errors, shacl_contract_errors, execute
from scripts.sbom_reference import reference, compare


def score(contract, authored, output, expected, valid):
    fields = {key: isinstance(contract, dict) and contract.get(key) == authored[key]
              for key in ('operation', 'target', 'scope')}
    exact = valid and contract == authored
    return {'field_agreement': fields, 'mapping_correct': exact,
            'result_agreement': valid and not compare(output, expected),
            'valid_but_wrong_mapping': valid and not exact,
            'unknown_scope_behavior': output.get('status') == 'unknown_world_scope',
            'clarification_behavior': output.get('status') == 'needs_clarification'}


def evaluate(folder, evaluator, destination):
    config = json.loads((folder/'config.json').read_text())
    gold = {q['id']: q for q in json.loads(evaluator.read_text())}
    rows = []
    for index, slot in enumerate(config['slots']):
        q = gold[slot['question_id']]
        if hashlib.sha256(Path(q['source_path']).read_bytes()).hexdigest() != q['source_sha256']:
            raise ValueError('source_changed')
        expected = reference(q['source_path'], q['authored_contract'])
        if expected != q['reference'] or q['mapping_scoring'] != 'exact_contract':
            raise ValueError('reference_or_scoring_changed')
        path = folder/'responses'/f'{index:03d}.result.json'
        row = {**slot, 'state': 'no_completed_output', 'mapping_correct': False,
               'result_agreement': False, 'valid_but_wrong_mapping': False}
        if path.exists():
            response = json.loads(path.read_text()); row['state'] = response['status']
            contract = response.get('contract')
            if response['status'] == 'completed':
                snapshot = read_document(q['source_path'])
                errors = contract_errors(contract, snapshot)
                output = execute(contract, snapshot)
                row.update(contract=contract, contract_errors=errors, output=output,
                           shacl=shacl_contract_errors(contract, snapshot))
                row.update(score(contract, q['authored_contract'], output, expected, not errors))
        rows.append(row)
    result = {'planned': len(rows), 'completed_outputs': sum(r['state'] == 'completed' for r in rows),
              **{k: sum(r[k] for r in rows) for k in
                 ('mapping_correct', 'result_agreement', 'valid_but_wrong_mapping')}, 'rows': rows,
              'limits': 'Authored development contracts; matching output is not matching interpretation or external truth.'}
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('folder', type=Path); p.add_argument('evaluator', type=Path); p.add_argument('destination', type=Path)
    a = p.parse_args(); evaluate(a.folder, a.evaluator, a.destination)
