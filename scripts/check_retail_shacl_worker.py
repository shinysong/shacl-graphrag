"""Authored adapter checks; neither model generation nor heldout evaluation."""
import json
from pathlib import Path
from scripts.retail_python_runner import execute
from scripts.retail_row_shacl import SHAPES
from scripts.retail_rdf_mapping import map_rows

BASE = Path('_workspace/retail-llm-v1/shacl-adapter-checks-v1')


def main():
    rows = [{'row_id': 'check1', 'data': {'CustomerID': 'x', 'InvoiceNo': 'A1', 'Quantity': '1', 'UnitPrice': '1'}},
            {'row_id': 'check2', 'data': {'CustomerID': None, 'InvoiceNo': None, 'Quantity': 'bad', 'UnitPrice': '-1'}}]
    data, normalized = map_rows(rows)
    original = '\n'.join(SHAPES.values())
    fixtures = {
        'authored': original,
        'supported_wrong': original.replace('sh:minInclusive 0', 'sh:minInclusive 100'),
        'target_rejected': original+'\n<urn:retail:shape:customer_analysis> <http://www.w3.org/ns/shacl#targetNode> <urn:probe> .',
        'parse_error': 'not valid turtle [',
        'service_rejected': original.replace('SELECT $this WHERE {', 'SELECT $this WHERE { SERVICE <http://example.invalid/> { ?s ?p ?o }'),
    }
    source = Path('scripts/retail_shacl_worker.py').read_bytes()
    summary = {}
    for name, shapes in fixtures.items():
        result = execute(source, {'normalized_rows': normalized,
                                  'data_turtle': data.serialize(format='turtle'),
                                  'shape_turtle': shapes}, BASE/name, shacl_dependencies=True)
        if not result['container_absent']:
            raise RuntimeError('Cleanup unresolved')
        assert result['status'] == 'completed', (name, result['status'])
        output = json.loads((BASE/name/'stdout.bin').read_text())
        summary[name] = output
    (BASE/'summary.json').write_text(json.dumps(summary, indent=2))
    def status(name, row, policy):
        return next(d['status'] for d in summary[name]['decisions'] if d['row_id'] == row and d['policy'] == policy)
    assert status('authored', 'check1', 'nonnegative_price') == 'pass'
    assert status('authored', 'check2', 'nonnegative_price') == 'violation'
    assert status('authored', 'check2', 'quantity_sign') == 'unknown'
    assert status('supported_wrong', 'check1', 'nonnegative_price') == 'violation'
    assert summary['target_rejected']['stage'] == 'artifact_unsupported'
    assert summary['service_rejected']['stage'] == 'artifact_unsupported'
    assert summary['parse_error']['stage'] == 'artifact_parse_error'
    print(json.dumps({k: {'stage': v['stage'], 'precheck_unknown_n': len(v['precheck_unknown'])}
                      for k, v in summary.items()}))


if __name__ == '__main__':
    main()
