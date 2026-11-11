import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rdflib import Literal
from apps.factory_lab.graph import snapshot, NAMESPACE
from apps.factory_lab.rdf_graph import RDFLibGraph, NeptuneGraph, project, export, graph_uri, templates, VOCAB, subject
from apps.factory_lab.review import review


def canonical_rows(rows):
    return sorted(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows)


def source_scan(version, tool, args):
    """Independent Python reference from authored snapshot; evaluator only."""
    d, _ = snapshot(version)
    ns = {n['id']: dict(n, namespace=NAMESPACE, version=version, entity_id=n['id']) for n in d['nodes']}
    edges = d['edges'];result=[]
    if tool == 'find_entities':
        text=args['text'].lower()
        return [{'entity':n} for _,n in sorted(ns.items()) if text in n['id'].lower() or text in n['name'].lower()][:30]
    if tool == 'inspect_entity':
        entity=ns.get(args['entity_id'])
        if not entity:return []
        for a,r,b in edges:
            if a==entity['id'] or b==entity['id']:
                result.append({'entity':entity,'neighbor':ns[b if a==entity['id'] else a],'relation':r,'from_id':a})
        return sorted(result,key=lambda r:(r['relation'],r['neighbor']['id']))[:60] or [{'entity':entity,'neighbor':None,'relation':None,'from_id':None}]
    if tool == 'qualification_records':
        m=ns.get(args['machine_id'])
        if not m:return []
        return [{'machine':m,'qualification':ns[b]} for a,r,b in sorted(edges,key=lambda e:e[2]) if a==m['id'] and r=='HAS_QUALIFICATION'][:30] or [{'machine':m,'qualification':None}]
    for o,r,c in edges:
        if tool=='impacted_orders' and r=='ASSIGNED_TO' and c==args['machine_id']:
            caps=[b for a,rel,b in edges if a==o and rel=='REQUIRES'] or [None]
            result.extend({'order':ns[o],'machine':ns[c],'required_capability':cap} for cap in caps)
        if tool=='replacement_candidates' and r=='REQUIRES' and o==args['order_id']:
            result.extend({'order':ns[o],'machine':ns[a],'required_capability':c} for a,rel,b in edges if rel=='CAPABLE_OF' and b==c)
    return sorted(result,key=lambda r:((r['order'] if tool=='impacted_orders' else r['machine'])['id'],r['required_capability'] or ''))[:30]


CASES=[('find_entities',{'text':'M0'}),('find_entities',{'text':'자격'}),('find_entities',{'text':'not present'}),
       ('find_entities',{'text':'" } UNION { ?s ?p ?o } #'}),
       ('inspect_entity',{'entity_id':'M01'}),('inspect_entity',{'entity_id':'Q03'}),('inspect_entity',{'entity_id':'O17'}),('inspect_entity',{'entity_id':'missing'}),
       ('impacted_orders',{'machine_id':'M02'}),('impacted_orders',{'machine_id':'M01'}),
       ('replacement_candidates',{'order_id':'O17'}),('replacement_candidates',{'order_id':'O18'}),('replacement_candidates',{'order_id':'O19'}),
       ('qualification_records',{'machine_id':'M01'}),('qualification_records',{'machine_id':'M02'}),('qualification_records',{'machine_id':'M03'})]

class FactoryRDFTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.g=RDFLibGraph()
    def test_five_tools_reference_parity(self):
        for v in ('factory-v1','factory-v2','factory-v3'):
            for t,a in CASES:
                with self.subTest(version=v,tool=t,args=a):
                    self.assertEqual(canonical_rows(self.g.run(v,t,a)['rows']),canonical_rows(source_scan(v,t,a)))
    def test_dates_types_and_stable_export(self):
        from rdflib import RDF, XSD
        g=project('factory-v3');self.assertIn((subject('factory-v3','Q03R'),RDF.type,VOCAB.Qualification),g)
        self.assertEqual(g.value(subject('factory-v3','Q03R'),VOCAB.valid_from).datatype,XSD.date)
        self.assertEqual(export('factory-v3'),export('factory-v3'))
    def test_change_scope_python_shacl(self):
        flags={}
        for v in ('factory-v2','factory-v3'):
            ev=[self.g.run(v,'replacement_candidates',{'order_id':o}) for o in ('O17','O18')]
            ev += [self.g.run(v,'qualification_records',{'machine_id':m}) for m in ('M01','M02','M03')]
            py=review(ev,'python');sh=review(ev,'shacl');self.assertEqual(py['flags'],sh['flags']);flags[v]=py['flags']
        removed=[f for f in flags['factory-v2'] if f not in flags['factory-v3']]
        self.assertEqual(removed,[{'candidate':'O17|M03|CAP-CUT','code':'qualification-not-applicable'}])
        self.assertIn({'candidate':'O18|M03|CAP-CUT','code':'qualification-not-applicable'},flags['factory-v3'])
    def test_tamper_fail_closed(self):
        g=RDFLibGraph(('factory-v2',));g.dataset.graph(graph_uri('factory-v2')).add((subject('factory-v2','M02'),VOCAB.status,Literal('available')))
        with self.assertRaises(RuntimeError):g.run('factory-v2','impacted_orders',{'machine_id':'M02'})
    def test_unknown_and_injection(self):
        with self.assertRaises(ValueError):templates('factory-v2','cypher',{'query':'DELETE'})
        with self.assertRaises(ValueError):project('../factory-v2')
        self.assertEqual(self.g.run('factory-v2','inspect_entity',{'entity_id':'x> } SERVICE <https://invalid> {'})['rows'],[])
    def test_no_authorization_no_aws_client(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a.json';p.write_text('{}')
            with self.assertRaises(RuntimeError):NeptuneGraph(p)
    def test_persistent_import_never_clears_nonmatching_graph(self):
        n=NeptuneGraph.__new__(NeptuneGraph)
        with patch.object(n,'_authorize'),patch.object(n,'select',return_value=[{'s':'existing'}]),patch.object(n,'verify_content',side_effect=RuntimeError('mismatch')),patch.object(n,'request') as req:
            with self.assertRaises(RuntimeError):n.load('factory-v2')
            req.assert_not_called()

if __name__=='__main__':unittest.main()


class NeoImportSafety(unittest.TestCase):
    def test_unmarked_and_conflicting_marked_do_not_write(self):
        from apps.factory_lab.graph import Graph
        for answers in ([[], [{'count': 1}]], [[{'sha256': 'wrong'}]]):
            g=Graph()
            with patch.object(g, 'query', side_effect=answers) as q:
                with self.assertRaises(RuntimeError):g.load('factory-v3')
                self.assertTrue(all('MERGE' not in call.args[0] and 'SET ' not in call.args[0] for call in q.call_args_list))

    def test_empty_creation_verified_and_marked_reuse(self):
        from apps.factory_lab.graph import Graph
        _,sha=snapshot('factory-v3')
        for marked in (False, True):
            g=Graph(); reads=iter([[{'sha256':sha}]] if marked else [[],[{'count':0}]])
            def query(q,p):
                return [] if 'MERGE' in q else next(reads)
            with patch.object(g,'query',side_effect=query) as q, patch.object(g,'verify_content',return_value={'verified_before_query':True}) as verify:
                g.load('factory-v3');verify.assert_called_once_with('factory-v3')
                if marked:self.assertEqual(q.call_count,1)
