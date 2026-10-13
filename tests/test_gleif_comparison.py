"""Software tests on invented fixtures, not experimental benchmark results."""
import tempfile
import unittest
from pathlib import Path
from rdflib import Graph, Literal, RDF, XSD
from scripts import run_gleif_comparison as c


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.ids = ['A'*18+'01','B'*18+'02','C'*18+'03']
        self.dataset = {'entities': {x:{'lei':x,'name':'Fixture '+x[0]} for x in self.ids}}
        self.item = {'lei':self.ids[0], 'kind':'parent', 'parent':self.ids[1], 'split':'development'}
        self.subject = c.LEI[self.ids[0]]
        self.shapes = Graph().parse(c.FIX / 'shapes.ttl')

    def evidence(self, variant, item=None):
        source = c.build_case(self.dataset, item or self.item, variant)
        return source, c.omit(c.old.retrieve(source,self.subject),self.subject,variant)

    def test_missing_vs_wrong_type_and_source_absence(self):
        expected = {'clean':'pass','irrelevant_name_missing':'pass','retrieval_relation_missing':'unknown',
                    'retrieval_type_missing':'unknown','source_relation_missing':'unknown',
                    'wrong_class':'fail','wrong_parent':'pass'}
        for variant, expected_j in expected.items():
            with self.subTest(variant=variant):
                source,evidence=self.evidence(variant)
                self.assertEqual(c.code_judge(evidence,self.subject),expected_j)
                self.assertEqual(c.shacl_judge(evidence,self.subject,self.shapes)[0],expected_j)
                self.assertEqual(c.canonical(evidence),c.canonical(c.omit(c.lpg_reference(source,self.subject),self.subject,variant)))

    def test_retry_recovers_only_retrieval_omission(self):
        for variant,retries,status in [('retrieval_type_missing',1,'answer'),('source_relation_missing',1,'abstain'),('wrong_class',0,'abstain'),('wrong_parent',0,'answer')]:
            source,first=self.evidence(variant)
            with tempfile.TemporaryDirectory() as t:
                r=c.run_condition(source,first,self.subject,'shacl',self.shapes,Path(t))
                self.assertEqual(r['extra_retrievals'],retries)
                self.assertEqual(r['answer']['status'],status)
                if variant=='wrong_parent':self.assertNotEqual(r['answer']['value'],self.item['parent'])

    def test_unchecked_does_not_hide_type_validation(self):
        source,first=self.evidence('wrong_class')
        for condition in ('none','refresh'):
            with tempfile.TemporaryDirectory() as t:
                r=c.run_condition(source,first,self.subject,condition,self.shapes,Path(t))
                self.assertEqual(r['answer']['status'],'answer')
                self.assertEqual(r['extra_retrievals'],condition=='refresh')

    def test_exception_semantics_and_conflicting_candidates(self):
        item={'lei':self.ids[0],'kind':'exception','reason':'NON_CONSOLIDATING'}
        for variant,expected in [('clean','pass'),('retrieval_exception_missing','unknown'),('invalid_reason','fail')]:
            _,ev=self.evidence(variant,item)
            self.assertEqual(c.code_judge(ev,self.subject),expected)
            self.assertEqual(c.shacl_judge(ev,self.subject,self.shapes)[0],expected)
        _,ev=self.evidence('clean')
        ev.add((self.subject,c.EX.exceptionReason,Literal('NO_LEI')))
        self.assertEqual(c.code_judge(ev,self.subject),'fail')
        self.assertEqual(c.shacl_judge(ev,self.subject,self.shapes)[0],'fail')
        self.assertEqual(c.extract(ev,self.subject)['status'],'abstain')

    def test_lpg_reference_preserves_typed_and_language_literals(self):
        source,_=self.evidence('clean')
        source.add((self.subject,c.EX.label,Literal('법인',lang='ko')))
        source.add((self.subject,c.EX.score,Literal('7',datatype=XSD.integer)))
        self.assertEqual(c.canonical(c.old.retrieve(source,self.subject)),c.canonical(c.lpg_reference(source,self.subject)))

    def test_errors_stay_in_denominator(self):
        rows=[{'condition':'x','status':'error','source_answerable':True},
              {'condition':'x','status':'ok','source_answerable':True,'answer':{'status':'abstain'},'unnecessary_abstention':True}]
        s=c.summarize(rows)['x']
        self.assertEqual((s['total'],s['errors'],s['source_answerable'],s['unnecessary_abstentions']),(2,1,2,1))

if __name__=='__main__':unittest.main()
