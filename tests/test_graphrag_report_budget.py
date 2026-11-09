import copy
import json
import unittest
from scripts.graphrag_message_pack import pack_base
from scripts.graphrag_report_budget import account_report
from scripts.graphrag_input_contract import COVERAGE


def source():
    data={'id':'n'};text=json.dumps(data)
    return dict(nodes=[dict(node_id='n',source=data,text=text)],edges=[],chunks=[dict(chunk_id='node:n',chunk_type='node',node_id='n',text=text)])


def report():
    return dict(raw_conforms=True,results=[],applicable_bindings=0,coverage=COVERAGE,no_bindings_status='unknown')


def counter(base_count, full_count):
    def count(raw):
        return base_count if json.loads(json.loads(raw)[1]['content'])['validation'] is None else full_count
    return count


class ReportTest(unittest.TestCase):
    def test_exact_caps_and_no_mutation(self):
        count=counter(3072,4096);b=pack_base('q',['node:n'],source(),count);before=copy.deepcopy(b);r=report()
        out=account_report('q',b,r,count)
        self.assertEqual(out['D']['status'],'ok');self.assertEqual(out['D']['increment_tokens'],1024)
        self.assertEqual(out['C'],b);self.assertEqual(b,before)
        self.assertEqual(out['D']['report']['no_bindings_status'],'unknown')
        self.assertEqual(json.loads(out['D']['full']['messages'][1]['content'])['evidence'],b['selected_chunks'])
        self.assertFalse(out['D']['generator_ready'])

    def test_overflow_retains_all(self):
        for bc,dc in [(3072,4097),(100,1125)]:
            with self.subTest(bc=bc):
                count=counter(bc,dc);b=pack_base('q',['node:n'],source(),count);o=account_report('q',b,report(),count)
                self.assertEqual(o['D']['status'],'report_budget_error');self.assertEqual(o['C'],b)
                self.assertIsNotNone(o['D']['full']);self.assertEqual(o['D']['report'],report())

    def test_byte_increment_without_token_overflow(self):
        count=counter(1,1);b=pack_base('q',['node:n'],source(),count);r=report()
        r.update(raw_conforms=False,applicable_bindings=1,no_bindings_status=None,results=[dict(check_id='x',status='unknown',missing=['가'*6000],conflicts=[],evidence_ids=['node:n'])])
        o=account_report('q',b,r,count)
        self.assertEqual(o['D']['status'],'report_budget_error');self.assertGreater(o['D']['increment_bytes'],16000)
        self.assertEqual(o['C'],b)

    def test_checker_and_report_error_isolation(self):
        count=counter(1,2);b=pack_base('q',['node:n'],source(),count)
        for r,status in [(report(),'failed'),({},'ok')]:
            with self.subTest(status=status):
                o=account_report('q',b,r,count,status);self.assertEqual(o['C'],b)
                self.assertEqual(o['D']['status'],'validation_execution_error');self.assertIsNone(o['D']['full'])

    def test_accounting_error_and_tamper(self):
        count=counter(1,2);b=pack_base('q',['node:n'],source(),count)
        def bad(raw):
            if json.loads(json.loads(raw)[1]['content'])['validation'] is not None:raise RuntimeError('adapter failed')
            return 1
        o=account_report('q',b,report(),bad);self.assertEqual(o['D']['status'],'accounting_error');self.assertEqual(o['C'],b)
        wrong=copy.deepcopy(b);wrong['base']['tokens']=99
        self.assertEqual(account_report('q',wrong,report(),count)['D']['status'],'input_error')
        self.assertEqual(account_report('different',b,report(),count)['D']['status'],'input_error')


if __name__=='__main__':unittest.main()
