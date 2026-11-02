# Source-grounded-1 final offline diagnostic review

User authorizes license check of PENELOPE/Hinge/BPI2019 and synthetic research if allowed. No new paid scope, no new push. Existing broad research scope remains.
Official Zenodo metadata: PENELOPE CC BY4.0 DOI10.5281/zenodo.15083865; Hinge CC BY-SA4.0 DOI10.5281/zenodo.13638681. Original BPI DataCite DOI10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1 rightsList explicitly CC BY4.0. Full per-source authors/version/license URL/change notices at research/source-grounded-1/licenses.json and data/*/ATTRIBUTION.txt. Combined evaluation and summaries conservatively CC BY-SA4.0. No raw personnel/reports/transactions published.
Source facts: actual PP3 workbook code2=lackfusion vs RX2=porosity, UT base OK vs overall reject scopes. Hinge original SIMULATED log with input/output/with roles. BPI original actual PO-item traces GR/IR, no invoice/receipt business document IDs. BPI strict-order rule is researcher-authored. No raw-source auto extraction. Source anchors/hashes retained.
144 fully authored consumed DEVELOPMENT cases:3 sources*8 families*6 states, no heldout/generalization/real-factory claims. 8 families largely ID/value variants; Hinge depth1..4. Runtime payload excludes state/answers. Cause pairs identical. Separate candidate list/declared completeness/conformance; no final approval gate. Broken refs can have declared_complete true and conforms false. Runtime input contract finite typed JSON classes/single field values/unique IDs; arbitrary schema ingestion outside scope.
Claims: 144/144 Python/SQLite/RDF candidate parity and 144/144 Python/SHACL/expected conformance; 24/24 decoys qualified correct vs0/24 deliberately unqualified; not BM25/vector/LLM performance. PENELOPE code namespace+scope bundled, not isolated factor.24/24 conforming falsefacts disagree with external synthetic author gold.24 identical missing-cause pairs. Gold is authored expectation, not independently observed business truth. All outputs saved before evaluation read. No gold repair. API0. No OWL; RDF propertypath on SPARQL-constructed typed transitions. No latency/engine superiority. No statistical inference.
Canonical full Korean explanation docs/experiments/source-grounded-study.md; source protocol research/source-grounded-1/protocol.json; license/anchors/README in samefolder. Source tests tests/test_source_grounded.py. You MAY read those listed files to check exact prose/metadata/test scope; all are development, no secrets/heldout. Do not read other reviewers' output. Write only your designated result JSON.
Manual verification before review: run-001 completed, counts above;6 targeted unittest methods passed including cycle/role, equal-time, wrongdatatype/class, falsefact and all144 generated cases. MkDocs strict passed before final Korean polish; final build pending. No registered checks ([]); distinguish manual observations from registered runner checks. First license freezing attempt failed on absent version key in Zenodo PENELOPE API; fixed by explicitly marking landing-page v2 vs absentAPI, no invented versionmetadata. Failed attempt retained in session.
Review methods: scientific scope/claims, source rights conditions, input/gold separation, sourceabsence vsretrieval and deliberately weak ablation. Implementation: actual execution/query/validation consistency and reproducibility. Need blockers if actual current claims wrong; optional future extensions not blockers.


Final review revision: first reviewers ready but flagged wider candidate boundaries. Coordinator aligned Code/Bead/Item class checks and Hinge zero-hop Product target semantics (step*), added two regression methods. Eight tests now pass; run-002 repeats same144 only to verify this code change, outputs/counts unchanged. Run001 and old source retained. Old reviews could not be submitted after source changes; rejection preserved, this is a new job. Canonical docs/JSON/results finalized before this job. No general-input parity claim.

## scripts/source_grounded/generate.py
```python
"""Author small structural fixtures; never sample or relabel real transactions."""
import copy
import json
from pathlib import Path

STATES = ('clean', 'semantic_decoy', 'broken_reference', 'source_absence', 'retrieval_omission', 'false_fact')


def base(source, family):
    prefix = f'SYN_{source}_{family:02d}_'
    def ident(s):
        return prefix + s
    if source == 'penelope':
        records = [
            dict(id=ident('book'), type='Code', namespace='worksheet', code='2', meaning='lack_fusion'),
            dict(id=ident('setting'), type='Setting', current=400 + family * 10),
            dict(id=ident('bead'), type='Bead', setting=ident('setting')),
            dict(id=ident('obs'), type='Observation', coupon=ident('coupon'), book=ident('book'), bead=ident('bead'), scope='weld'),
        ]
        q = dict(target=ident('coupon'), meaning='lack_fusion', scope='weld')
        gold = [ident('obs')]
        essential = (ident('bead'), 'setting')
    elif source == 'hinge':
        depth = 1 + family % 4
        records = [dict(id=ident(f'n{i}'), type='Product' if i == depth else 'Material') for i in range(depth + 1)]
        records += [dict(id=ident(f'e{i}'), type='Event', input=ident(f'n{i}'), output=ident(f'n{i+1}')) for i in range(depth)]
        q = dict(target=ident('n0'))
        gold = [ident(f'n{depth}')]
        essential = (ident('e0'), 'input')
    else:
        records = [dict(id=ident('item'), type='Item'),
                   dict(id=ident('gr'), type='Receipt', item=ident('item'), time=10 + family),
                   dict(id=ident('ir'), type='Invoice', item=ident('item'), time=20 + family)]
        q = dict(target=ident('item'))
        gold = [ident('ir')]
        essential = (ident('gr'), 'item')
    return records, q, gold, essential, ident


def cases():
    for source in ('penelope', 'hinge', 'bpi'):
        for family in range(8):
            rows, q, gold, (subject, predicate), ident = base(source, family)
            for state in STATES:
                records = copy.deepcopy(rows)
                complete = True
                contract_gold = gold[:]
                if state == 'semantic_decoy':
                    if source == 'penelope':
                        records += [dict(id=ident('rx'), type='Code', namespace='radiography', code='2', meaning='porosity'),
                                    dict(id=ident('decoy'), type='Observation', coupon=q['target'], book=ident('rx'), bead=ident('bead'), scope='weld'),
                                    dict(id=ident('base'), type='Observation', coupon=q['target'], book=ident('book'), bead=ident('bead'), scope='base_material')]
                    elif source == 'hinge':
                        records += [dict(id=ident('other'), type='Material'), dict(id=ident('decoy'), type='Product'),
                                    dict(id=ident('other_event'), type='Event', input=ident('other'), output=ident('decoy'), with_role=q['target'])]
                    else:
                        records += [dict(id=ident('other_item'), type='Item'),
                                    dict(id=ident('decoy'), type='Invoice', item=ident('other_item'), time=30 + family)]
                if state in ('source_absence', 'retrieval_omission'):
                    # Both expose the same incomplete records. Cause is ONLY in scorer file.
                    for r in records:
                        if r['id'] == subject:
                            del r[predicate]
                    complete = False
                    contract_gold = []
                if state == 'broken_reference':
                    # A typed relation points to a missing node, not a missing real-world fact.
                    target = next(r[predicate] for r in records if r['id'] == subject)
                    records = [r for r in records if r['id'] != target]
                    contract_gold = []
                if state == 'false_fact':
                    # All structural requirements still hold, but the supplied assertion is false.
                    if source == 'penelope':
                        records[0]['meaning'] = 'porosity'
                    elif source == 'hinge':
                        records += [dict(id=ident('other'), type='Material')]
                        next(r for r in records if r['id'] == subject)['input'] = ident('other')
                    else:
                        next(r for r in records if r['type'] == 'Receipt')['time'] = 40 + family
                    contract_gold = []
                payload = dict(source=source, question=q, declared_complete=complete, records=records)
                evaluation = dict(id=f'{source}-{family:02d}-{state}', source=source, family=family, state=state,
                                  contract_candidates=contract_gold, external_candidates=gold,
                                  expected_conforms=state not in ('broken_reference', 'source_absence', 'retrieval_omission'))
                yield payload, evaluation


def write(root):
    root = Path(root)
    for payload, evaluation in cases():
        directory = root / evaluation['source']
        directory.mkdir(parents=True, exist_ok=True)
        (directory / (evaluation['id'] + '.json')).write_text(json.dumps(payload, indent=2) + '\n')
    (root / 'evaluation.json').write_text(json.dumps([e for _, e in cases()], indent=2) + '\n')
```

## scripts/source_grounded/runtime.py
```python
"""Runtime receives records/questions only; never imports generator or reads evaluation."""
import sqlite3
from rdflib import Graph, Literal, Namespace, RDF, BNode, XSD
from pyshacl import validate

EX = Namespace('urn:source-grounded:')
SH = Namespace('http://www.w3.org/ns/shacl#')
REFS = {'book': 'Code', 'bead': 'Bead', 'setting': 'Setting', 'input': 'Node', 'output': 'Node', 'with_role': 'Node', 'item': 'Item'}
REQUIRED = {
    'Code': {'namespace': 'str', 'code': 'str', 'meaning': 'str'},
    'Setting': {'current': 'int'}, 'Bead': {'setting': 'Setting'},
    'Observation': {'coupon': 'str', 'book': 'Code', 'bead': 'Bead', 'scope': 'str'},
    'Event': {'input': 'Node', 'output': 'Node'},
    'Receipt': {'item': 'Item', 'time': 'int'}, 'Invoice': {'item': 'Item', 'time': 'int'},
    'Item': {}, 'Product': {}, 'Material': {},
}


def python_conforms(data):
    lookup = {r['id']: r for r in data['records']}
    for r in data['records']:
        for key, kind in REQUIRED[r['type']].items():
            if key not in r:
                return False
            value = r[key]
            if kind == 'str' and not isinstance(value, str):
                return False
            if kind == 'int' and type(value) is not int:
                return False
            if kind not in ('str', 'int') and (value not in lookup or (kind != 'Node' and lookup[value]['type'] != kind)):
                return False
    return True


def graph(data):
    g = Graph()
    g.bind('ex', EX)
    for r in data['records']:
        node = EX[r['id']]
        g.add((node, RDF.type, EX.Node))
        for key, value in r.items():
            if key == 'id':
                continue
            g.add((node, RDF.type if key == 'type' else EX[key], EX[value] if key in REFS or key == 'type' else Literal(value)))
    return g


def shapes():
    g = Graph()
    g.bind('sh', SH)
    g.bind('ex', EX)
    for cls, fields in REQUIRED.items():
        node = EX[cls + 'Shape']
        g.add((node, RDF.type, SH.NodeShape))
        g.add((node, SH.targetClass, EX[cls]))
        for key, kind in fields.items():
            p = BNode(cls + '_' + key)
            g.add((node, SH.property, p))
            g.add((p, SH.path, EX[key]))
            g.add((p, SH.minCount, Literal(1)))
            g.add((p, SH.datatype if kind in ('str', 'int') else SH['class'],
                   XSD.string if kind == 'str' else XSD.integer if kind == 'int' else EX[kind]))
    return g


def shacl_conforms(data):
    conforms, report, message = validate(graph(data), shacl_graph=shapes(), inference='none')
    return bool(conforms), report, message


def python_candidates(data, unqualified=False):
    rows = data['records']
    lookup = {r['id']: r for r in rows}
    q = data['question']
    result = set()
    if data['source'] == 'penelope':
        target_codes = {r['code'] for r in rows if r['type'] == 'Code' and r['meaning'] == q['meaning']}
        for r in rows:
            if r['type'] != 'Observation' or r['coupon'] != q['target']:
                continue
            book = lookup.get(r.get('book'), {})
            bead = lookup.get(r.get('bead'), {})
            setting = lookup.get(bead.get('setting'), {})
            qualified = book.get('meaning') == q['meaning'] and r.get('scope') == q['scope']
            if (book.get('code') in target_codes if unqualified else qualified) and book.get('type') == 'Code' and bead.get('type') == 'Bead' and setting.get('type') == 'Setting':
                result.add(r['id'])
    elif data['source'] == 'hinge':
        reached = {q['target']} if q['target'] in lookup else set()
        changed = True
        while changed:
            old = reached.copy()
            for r in rows:
                inputs = [r.get('input')] + ([r.get('with_role')] if unqualified else [])
                if r['type'] == 'Event' and any(x in reached for x in inputs) and r.get('output') in lookup:
                    reached.add(r['output'])
            changed = old != reached
        result = {v for v in reached if lookup[v]['type'] == 'Product'}
    else:
        for r in rows:
            if r['type'] != 'Invoice' or lookup.get(r.get('item'), {}).get('type') != 'Item':
                continue
            if not unqualified and r['item'] != q['target']:
                continue
            if any(s['type'] == 'Receipt' and lookup.get(s.get('item'), {}).get('type') == 'Item' and
                   (unqualified or s['item'] == r['item']) and s['time'] < r['time'] for s in rows):
                result.add(r['id'])
    return sorted(result)


SPARQL = {
    'penelope': '''SELECT DISTINCT ?answer WHERE {
      ?answer a ex:Observation; ex:coupon ?target; ex:scope ?scope; ex:book ?book; ex:bead ?bead.
      ?book a ex:Code; ex:meaning ?meaning. ?bead a ex:Bead; ex:setting ?setting. ?setting a ex:Setting.
    }''',
    'hinge': '''SELECT DISTINCT ?answer WHERE {
      ?target ex:step* ?answer. ?answer a ex:Product.
    }''',
    'bpi': '''SELECT DISTINCT ?answer WHERE {
      ?answer a ex:Invoice; ex:item ?target; ex:time ?invoiceTime.
      ?receipt a ex:Receipt; ex:item ?target; ex:time ?receiptTime.
      ?target a ex:Item. FILTER(?receiptTime < ?invoiceTime)
    }''',
}


def rdf_candidates(data):
    q = data['question']
    bindings = {k: (EX[v] if k == 'target' and data['source'] != 'penelope' else Literal(v)) for k, v in q.items()}
    g = graph(data)
    if data['source'] == 'hinge':
        transitions = g.query('''SELECT DISTINCT ?a ?b WHERE {
            ?event a ex:Event; ex:input ?a; ex:output ?b.
            ?a a ex:Node. ?b a ex:Node.
        }''', initNs={'ex': EX})
        for a, b in transitions:
            g.add((a, EX.step, b))
    return sorted(str(row.answer).removeprefix(str(EX)) for row in g.query(SPARQL[data['source']], initNs={'ex': EX}, initBindings=bindings))


def sql_candidates(data):
    # SQLite uses normalized property rows, with no precomputed answers or graph closure.
    db = sqlite3.connect(':memory:')
    try:
        db.execute('CREATE TABLE p (s TEXT, k TEXT, v)')
        db.executemany('INSERT INTO p VALUES (?,?,?)', [(r['id'], k, v) for r in data['records'] for k, v in r.items() if k != 'id'])
        q = data['question']
        if data['source'] == 'penelope':
            sql = '''SELECT DISTINCT a.s FROM p a
            JOIN p c ON c.s=a.s AND c.k='coupon' AND c.v=:target
            JOIN p sc ON sc.s=a.s AND sc.k='scope' AND sc.v=:scope
            JOIN p b ON b.s=a.s AND b.k='book'
            JOIN p bt ON bt.s=b.v AND bt.k='type' AND bt.v='Code'
            JOIN p m ON m.s=b.v AND m.k='meaning' AND m.v=:meaning
            JOIN p bead ON bead.s=a.s AND bead.k='bead'
            JOIN p t ON t.s=bead.v AND t.k='type' AND t.v='Bead'
            JOIN p setting ON setting.s=bead.v AND setting.k='setting'
            JOIN p st ON st.s=setting.v AND st.k='type' AND st.v='Setting'
            WHERE a.k='type' AND a.v='Observation' '''
        elif data['source'] == 'hinge':
            sql = '''WITH RECURSIVE reachable(id) AS (
            SELECT s FROM p WHERE s=:target AND k='type'
            UNION SELECT o.v FROM reachable r JOIN p i ON i.v=r.id AND i.k='input'
            JOIN p e ON e.s=i.s AND e.k='type' AND e.v='Event'
            JOIN p o ON o.s=i.s AND o.k='output'
            JOIN p exists_node ON exists_node.s=o.v AND exists_node.k='type'
            ) SELECT DISTINCT r.id FROM reachable r JOIN p t ON t.s=r.id AND t.k='type' AND t.v='Product' '''
        else:
            sql = '''SELECT DISTINCT i.s FROM p i
            JOIN p ii ON ii.s=i.s AND ii.k='item' AND ii.v=:target
            JOIN p item ON item.s=ii.v AND item.k='type' AND item.v='Item'
            JOIN p it ON it.s=i.s AND it.k='time'
            JOIN p ri ON ri.v=ii.v AND ri.k='item'
            JOIN p r ON r.s=ri.s AND r.k='type' AND r.v='Receipt'
            JOIN p rt ON rt.s=r.s AND rt.k='time' AND rt.v<it.v
            WHERE i.k='type' AND i.v='Invoice' '''
        return sorted(row[0] for row in db.execute(sql, q))
    finally:
        db.close()
```
