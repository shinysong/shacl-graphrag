# Query dependency followup
Same160savedbackendoutputs, same8completecontrolledsnapshots, same4typedqueries. Priorfamilyflags20/160 include8mismatch12matching; global32include8+24. Thisfollowupcomputes advertised fingerprints fromquery-specific facts+schema dependency slices. Backwards reachability fromquerytarget, selecttypefacts oranchoredrelationfacts, forwards paths fromselectedfacttypes/properties restrictedtobackwardsreachable. No runtimeanswers/gold used tochoose slices. Emptyselectedsourcefacts means emptydependency on thissuppliedcomplete boundedgraph, NOTglobalabsence frommissing/incomplete sources. Canonicalhashesonly givenPython/SHACL; preprocessor getsfullsavedsource,notSHACLreadingextrasource. Thisiscomputedoperationalmetadata notSHACL-specificbenefit; anyfuturegeneratorcomparison mustprovideequalmetadataaccess/budget. SupportsONLY subtype/subproperty query membership, nofullRDFSdomain/range, negation, equality,OWL. Samev1canonicalstringchecks unchanged. Two policies declared_query/swappedquerynegativecontrol(I1superclass↔unrelated,I2forward↔reverse).160x2x2=640slots320pairs, notindependenttrials; reportsnoanswerrepair/veto/LLM/newDB. Preserve2remainingpossiblematchingwarningsfromalternateproofchanges; donotoptimizebygold. Existingglobal/familyresults remainpreviousoriginalruns; comparedependentproxies, notlabor. Main3targetedunit tests passed. Fullplan savedbeforepreprocess; CLIerrors retainedinexecutionlog. Posthocscorer reads oldconsumedreference only. Source imports omitted bodies exceptnewfunctions; earlierreviewedcanonical/digest/inputdigest andadvisorycheckers areunverified inthispacket. Registeredchecksempty. Independentreviews beforeexplicitrun. Endwindow10:31:23UTC unchanged; noNeptunerestart.

FILE scripts/backend_query_scope.py
"""Query-conditioned dependency fingerprints on complete controlled snapshots.

Only explicit subtype/subproperty queries are supported. This is a supplied
operational preprocessor, not NL interpretation, source discovery or SHACL logic.
"""
import argparse
import json
from pathlib import Path
from rdflib import Graph
from scripts.backend_advisory import python_report, shacl_report
from scripts.backend_parity import canonical, digest
from scripts.backend_inference import TYPE, SC, SP
from scripts.backend_updates import input_digest

SWAPPED = {'I1_superclass': 'I1_unrelated', 'I1_unrelated': 'I1_superclass',
           'I2_forward': 'I2_reverse', 'I2_reverse': 'I2_forward'}


def dependency(state, query):
    kind = query['kind']
    if kind not in ('type', 'relation'):
        raise ValueError('unsupported query kind')
    predicate = SC if kind == 'type' else SP
    edges = {(s, o) for s, p, o in state['schema'] if p == predicate}
    backwards = {query['target']}
    while True:
        expanded = backwards | {s for s, o in edges if o in backwards}
        if expanded == backwards:
            break
        backwards = expanded
    if kind == 'type':
        facts = {(s, p, o) for s, p, o in state['facts'] if p == TYPE and o in backwards}
        starts = {o for s, p, o in facts}
    else:
        facts = {(s, p, o) for s, p, o in state['facts'] if s == query['start'] and p in backwards}
        starts = {p for s, p, o in facts}
    forward = starts
    while True:
        expanded = forward | {o for s, o in edges if s in forward and o in backwards}
        if expanded == forward:
            break
        forward = expanded
    schema = {(s, predicate, o) for s, o in edges if s in forward and o in backwards}
    return {'query': query, 'facts': sorted(facts), 'schema': sorted(schema)}


def run(parent, shapes_path, output):
    output.mkdir(parents=True, exist_ok=False)
    saved = [json.loads(x) for x in (parent / 'results.jsonl').read_text().splitlines()]
    states = json.loads((parent / 'states.json').read_text())
    queries = {q['id']: q for q in json.loads((parent / 'queries.json').read_text())}
    snapshots = {input_digest(s): s for s in states}
    policies = ('declared_query', 'swapped_query_control')
    plan = [{'row_index': i, 'policy': p, 'checker': c} for i in range(len(saved)) for p in policies for c in ('python', 'shacl')]
    (output / 'plan.json').write_text(canonical(plan) + '\n')
    (output / 'runtime.py').write_bytes(Path(__file__).read_bytes())
    (output / 'shapes.ttl').write_bytes(shapes_path.read_bytes())
    inputs = []
    for i, row in enumerate(saved):
        for policy in policies:
            query = queries[row['query_id'] if policy == 'declared_query' else SWAPPED[row['query_id']]]
            current = dependency(snapshots[row['current_input_hash']], query)
            used = dependency(snapshots[row['used_input_hash']], query)
            inputs.append({'row_index': i, 'policy': policy, 'family': 'query_dependency', 'declared_query': query,
                           'origin': {k: row[k] for k in ('event', 'arm', 'query_id')},
                           'original_answer': row['answer'], 'original_status': row['status'],
                           'metadata': {'used_input_hash': digest(used), 'current_input_hash': digest(current)},
                           'used_dependency': used, 'current_dependency': current})
    (output / 'inputs.json').write_text(canonical(inputs) + '\n')
    shapes = Graph().parse(shapes_path, format='turtle')
    with (output / 'results.jsonl').open('a') as handle:
        for i, item in enumerate(inputs):
            for checker in ('python', 'shacl'):
                row = {k: v for k, v in item.items() if k not in ('used_dependency', 'current_dependency')}
                row.update(checker=checker, answer_changed=False, decision='advisory_only_no_veto')
                try:
                    if checker == 'python':
                        codes = python_report(item['metadata'])
                    else:
                        result = shacl_report(item['metadata'], shapes)
                        codes = result['codes']
                        row['conforms'] = result['conforms']
                        (output / f'{i}-report.ttl').write_text(result['validation_graph'])
                    row.update(status='completed', codes=codes, review_requested=bool(codes))
                except Exception as error:
                    row.update(status='checker_failure', error=f'{type(error).__name__}: {error}')
                handle.write(canonical(row) + '\n')
                handle.flush()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--parent', type=Path, required=True)
    p.add_argument('--shapes', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    run(a.parent, a.shapes, a.output)

FILE tests/test_backend_query_scope.py
import unittest
from scripts.backend_query_scope import dependency
from scripts.backend_inference import TYPE, SC, SP


class QueryDependencyTests(unittest.TestCase):
    def test_alternate_path_change_remains_visible(self):
        state = {'facts': [('x', TYPE, 'A')], 'schema': [('A', SC, 'B'), ('B', SC, 'R'), ('A', SC, 'R')]}
        query = {'kind': 'type', 'target': 'R'}
        before = dependency(state, query)
        after = dependency({**state, 'schema': state['schema'][:-1]}, query)
        self.assertEqual(before['facts'], after['facts'])
        self.assertNotEqual(before['schema'], after['schema'])

    def test_empty_query_and_new_matching_fact(self):
        state = {'facts': [], 'schema': [('A', SC, 'R')]}
        q = {'kind': 'type', 'target': 'R'}
        self.assertEqual(dependency(state, q)['schema'], [])
        self.assertNotEqual(dependency(state, q), dependency({**state, 'facts': [('x', TYPE, 'A')]}, q))

    def test_relation_anchor_and_cycles(self):
        state = {'facts': [('x', 'p', 'y'), ('other', 'p', 'z')], 'schema': [('p', SP, 'r'), ('r', SP, 'p')]}
        d = dependency(state, {'kind': 'relation', 'target': 'r', 'start': 'x'})
        self.assertEqual(d['facts'], [('x', 'p', 'y')])
        self.assertEqual(len(d['schema']), 2)
        with self.assertRaises(ValueError):
            dependency(state, {'kind': 'unsupported', 'target': 'r'})

FILE research/backend-reasoning-review-1/evaluation/score_query_scope.py
import json,sys
from pathlib import Path
out=Path(sys.argv[1]);plan=json.loads((out/'plan.json').read_text());rows=[json.loads(x) for x in (out/'results.jsonl').read_text().splitlines()];inputs=json.loads((out/'inputs.json').read_text());expected={(x['row_index'],x['policy']):x for x in inputs}
key=lambda r:(r['row_index'],r['policy'],r['checker']);assert len({key(r) for r in rows})==len(rows);assert {key(r) for r in rows}<={key(r) for r in plan}
parent=Path('research/backend-reasoning-review-1/updates-live-001');ev=json.loads((parent/'evaluation.json').read_text());ref={(x['event'],x['arm'],x['query_id']):x['matches_current_reference'] for x in ev['checks']}
lookup={key(r):r for r in rows};summary={};pairs=[]
for p in plan:
    row=lookup.get(key(p));s=summary.setdefault(p['policy']+'/'+p['checker'],{'planned':0,'completed':0,'review_flags':0,'mismatch_with_review':0,'matching_with_review':0,'mismatch_without_review':0});s['planned']+=1
    if row and row['status']=='completed':
        x=expected[(p['row_index'],p['policy'])];assert row['original_answer']==x['original_answer'] and not row['answer_changed']
        matches=ref[tuple(row['origin'][k] for k in ('event','arm','query_id'))];flag=row['review_requested']
        s['completed']+=1;s['review_flags']+=flag;s['mismatch_with_review']+=not matches and flag;s['matching_with_review']+=matches and flag;s['mismatch_without_review']+=not matches and not flag
for i,p in expected:
    a,b=[lookup.get((i,p,c)) for c in ('python','shacl')];pairs.append(bool(a and b and a['status']==b['status']=='completed' and a['codes']==b['codes']))
result={'planned_checker_slots':len(plan),'observed':len(rows),'pairs':len(pairs),'agreeing_pairs':sum(pairs),'summary':summary,'interpretation':'Derived replay on same160controlledbackendoutputs. Typed query dependency on complete controlled snapshots supplied, not learnedNLunderstanding or sourcecompleteness discovery. Metadataonly/noLLM/veto/repair. Correctflags quantify proxyreviewburden, not actual labor orabstention.'}
(out/'evaluation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));assert len(rows)==len(plan) and all(pairs)
