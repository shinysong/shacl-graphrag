"""Run runtime first, then score saved answers; no gold correction."""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from scripts.source_grounded.runtime import graph, python_candidates, python_conforms, rdf_candidates, shacl_conforms, shapes, sql_candidates


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(data_root, output):
    root, out = Path(data_root), Path(output)
    out.mkdir(parents=True, exist_ok=False)
    # Save a frozen manifest BEFORE any runtime answer is computed.
    paths = sorted(root.glob('*/*.json'))
    frozen = paths + [root / 'evaluation.json', Path('research/source-grounded-1/protocol.json')] + sorted(Path('scripts/source_grounded').glob('*.py'))
    (out / 'input-manifest.json').write_text(json.dumps({str(p): digest(p) for p in frozen}, indent=2) + '\n')
    outputs = []
    shapes().serialize(out / 'shapes.ttl', format='turtle')
    for path in paths:
        data = json.loads(path.read_text())
        py = python_conforms(data)
        sh, report, message = shacl_conforms(data)
        answers = dict(python=python_candidates(data), sqlite=sql_candidates(data), rdflib=rdf_candidates(data),
                       unqualified_python=python_candidates(data, unqualified=True))
        result = dict(id=path.stem, answers=answers, python_conforms=py, shacl_conforms=sh,
                      evidence_state='declared_complete' if data['declared_complete'] else 'unknown')
        outputs.append(result)
        if path.stem in ('penelope-00-clean', 'penelope-00-source_absence', 'hinge-00-semantic_decoy', 'bpi-00-false_fact'):
            graph(data).serialize(out / (path.stem + '.ttl'), format='turtle')
            report.serialize(out / (path.stem + '-report.ttl'), format='turtle')
            (out / (path.stem + '-report.txt')).write_text(message)
    (out / 'outputs.json').write_text(json.dumps(outputs, indent=2) + '\n')
    # Evaluation is only loaded after all outputs have been saved.
    gold = {r['id']: r for r in json.loads((root / 'evaluation.json').read_text())}
    counts = Counter()
    by_state = {}
    for result in outputs:
        reference = gold[result['id']]
        key = reference['source'] + '/' + reference['state']
        stats = by_state.setdefault(key, Counter())
        stats['cases'] += 1
        stats['shacl_conforms'] += result['shacl_conforms']
        counts['cases'] += 1
        counts['matched_candidate_parity'] += result['answers']['python'] == result['answers']['sqlite'] == result['answers']['rdflib']
        counts['validation_parity'] += result['python_conforms'] == result['shacl_conforms'] == reference['expected_conforms']
        for arm, answer in result['answers'].items():
            stats[arm + '_contract_match'] += answer == reference['contract_candidates']
            stats[arm + '_external_match'] += answer == reference['external_candidates']
        stats['conforming_external_error_python'] += result['shacl_conforms'] and result['answers']['python'] != reference['external_candidates']
    identical = 0
    for source in ('penelope', 'hinge', 'bpi'):
        for family in range(8):
            a = root / source / f'{source}-{family:02d}-source_absence.json'
            b = root / source / f'{source}-{family:02d}-retrieval_omission.json'
            identical += a.read_bytes() == b.read_bytes()
    summary = dict(protocol='source-grounded-1', counts=dict(counts), indistinguishable_pairs=identical,
                   by_source_state=by_state, api_calls=0,
                   interpretation='Authored development diagnostics only; unqualified baseline deliberately removes semantics; external truth is synthetic author truth.')
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({**counts, 'indistinguishable_pairs': identical}))
    return summary


if __name__ == '__main__':
    run(sys.argv[1], sys.argv[2])
