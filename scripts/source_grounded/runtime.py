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
