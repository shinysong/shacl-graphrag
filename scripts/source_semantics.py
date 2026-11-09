"""Declared field semantics and posthoc classification scoring; no LLM client."""
import argparse
import hashlib
import json
from pathlib import Path

VALUES = {'required', 'optional', 'excluded', 'explicit_empty', 'reported_nonempty',
          'unknown', 'established', 'not_established'}


def classify(document, ref, task, schema):
    nodes = [c for c in document['components'] if c['bom-ref'] == ref]
    if len(nodes) != 1:
        raise ValueError('ambiguous_component')
    if task == 'consumer_scope':
        return nodes[0].get('scope', schema['definitions']['component']['properties']['scope'].get('default', 'unknown'))
    if task == 'dependency_knowledge':
        entries = [e for e in document.get('dependencies', []) if e['ref'] == ref]
        if len(entries) > 1:
            raise ValueError('duplicate_dependency_entry')
        if not entries:
            return 'unknown'
        return 'reported_nonempty' if entries[0].get('dependsOn', []) else 'explicit_empty'
    if task == 'external_claim':
        # This task is narrowly scoped to current customer installation from archived example scope alone.
        return 'not_established'
    raise ValueError('unsupported_task')


def valid_response(value):
    return (isinstance(value, dict) and set(value) == {'classification', 'basis'}
            and isinstance(value['classification'], str) and value['classification'] in VALUES
            and isinstance(value['basis'], str) and bool(value['basis'].strip()))


def evaluate(folder, catalog, out):
    config = json.loads((folder/'config.json').read_text())
    questions = {q['id']: q for q in json.loads((catalog/'questions.json').read_text())}
    gold = {q['id']: q for q in json.loads((catalog/'evaluator-only.json').read_text())}
    baselines = {}
    for qid, q in questions.items():
        raw = Path(q['source_path']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != q['source_sha256']:
            raise ValueError('source_changed')
        doc = json.loads(raw)
        schema_path = Path(q['source_path']).parent/('schema14.json' if doc['specVersion']=='1.4' else 'schema12.json')
        node = doc['components'][int(q['source_component_pointer'].split('/')[-1])]
        baseline = classify(doc, node['bom-ref'], q['question_type'], json.loads(schema_path.read_text()))
        if baseline != gold[qid]['expected_classification']:
            raise ValueError('declared_policy_reference_disagreement')
        baselines[qid] = baseline
    rows = []
    for index, slot in enumerate(config['slots']):
        qid, arm = slot['question_id'].split('|')
        row = {**slot, 'case': qid, 'arm': arm, 'state': 'not_completed', 'response_valid': False, 'correct': False}
        path = folder/'responses'/f'{index:03d}.result.json'
        if path.exists():
            result = json.loads(path.read_text()); row['state'] = result['status']
            answer = result.get('contract'); row['answer'] = answer
            row['response_valid'] = result['status'] == 'completed' and valid_response(answer)
            row['correct'] = row['response_valid'] and answer['classification'] == gold[qid]['expected_classification']
        rows.append(row)
    paired = []
    for qid in questions:
        for provider in config['providers']:
            pair = {r['arm']: r for r in rows if r['case']==qid and r['model']==provider['model']}
            paired.append({'case':qid, 'model':provider['model'],
                           'source_only_correct':pair['source_only']['correct'],
                           'source_plus_schema_correct':pair['source_plus_schema']['correct'],
                           'both_valid':all(r['response_valid'] for r in pair.values())})
    out.write_text(json.dumps({'planned':len(rows),'rows':rows,'pairs':paired,'supplied_task_python_baseline':baselines,
                              'arm_counts':{a:{'planned':sum(r['arm']==a for r in rows),
                                               'valid':sum(r['arm']==a and r['response_valid'] for r in rows),
                                               'correct':sum(r['arm']==a and r['correct'] for r in rows)}
                                            for a in ['source_only','source_plus_schema']},
                              'limits':'Authored consumed development; normative metadata access treatment, not SHACL or storage effect. Basis text retained but not scored for correctness; no external expert validation or blind intent extraction.'},ensure_ascii=False,indent=2)+'\n')


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('catalog',type=Path);p.add_argument('out',type=Path)
    a=p.parse_args();evaluate(a.folder,a.catalog,a.out)
