import unittest
from scripts.source_semantics_report import make_report


class AdvisoryReport(unittest.TestCase):
    def setUp(self):
        self.meta={'scope':{'default':'required'},'source_sha256':'fixture'}
        self.evidence={'component':{'bom-ref':'x'},'source_field_presence':{'dependencies':False},'source_component_pointer':'/components/0'}

    def test_same_policy_shacl_python(self):
        for task in ('consumer_scope','dependency_knowledge'):
            for present in (False,True):
                evidence={**self.evidence,'source_field_presence':{'dependencies':present}}
                if present:evidence['dependencies']=[{'ref':'x'}]
                for value in ('required','optional','excluded','explicit_empty','reported_nonempty','unknown','established','not_established'):
                    report=make_report(evidence,task,self.meta,{'classification':value,'basis':'x'})
                    self.assertEqual(report['status'],'completed')
                    self.assertEqual(report['conforms'],report['python_conforms'])

    def test_absence_not_projection_loss(self):
        e={**self.evidence,'source_field_presence':{'dependencies':True}}
        r=make_report(e,'dependency_knowledge',self.meta,{'classification':'unknown','basis':'x'})
        self.assertEqual(r['status'],'unknown');self.assertIsNone(r['conforms'])
        r=make_report(e,'dependency_knowledge',self.meta,None)
        self.assertEqual(r['status'],'input_rejected');self.assertIsNone(r['conforms'])
