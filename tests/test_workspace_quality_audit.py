"""Mutation controls for saved-artifact integrity, not generator quality."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from scripts.workspace_quality_audit import audit


def fixture():
    files=[{'name':'x.csv','content':'ref\nA\n'}]
    hashes={'x.csv':hashlib.sha256(files[0]['content'].encode()).hexdigest()}
    expected={'target':'shipping','basis':'unresolved','question_required':True}
    packet={'cases':[{'id':'sample','files':files,'mapping_expectations':{'x.csv:ref':''},'policy_expectations':[expected],'relation_expected':True,'comparison_expected':True}]}
    entries=[{'id':'map:x.csv:ref','kind':'mapping','status':'pending','target':'','extraction':{'candidates':[],'table_candidate':None}},
             {'id':'policy:note:1','kind':'policy','status':'pending','target':'shipping','extraction':{'basis':'unresolved','questions':['Which basis?'],'related_policy_count':1}},
             {'id':'relation:0','kind':'relation','status':'pending','target':{'file':'x.csv','column':'ref'}}]
    draft={'sources':[{**files[0],'sha256':hashes['x.csv']}],'entries':entries}
    row={'id':'sample','files_sha256':hashes,'mapping_checks':[{'field':'x.csv:ref','expected':'','actual':'','matches':True,'candidates':[],'table_candidate':None}],
         'policy_checks':[{'expected':expected,'actual':deepcopy(expected),'matches':True,'questions':['Which basis?']}],
         'relations':[deepcopy(entries[2])],'comparison_counts':[1],'all_unapproved':True}
    return packet,{'results':[row]},draft


class QualityAuditTests(unittest.TestCase):
    def run_audit(self, mutate=None):
        packet,saved,draft=fixture()
        if mutate:mutate(packet,saved,draft)
        raw=json.dumps(packet).encode();saved['case_file_sha256']=hashlib.sha256(raw).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'cases.json').write_bytes(raw);(root/'results.json').write_text(json.dumps(saved));(root/'sample-draft.json').write_text(json.dumps(draft))
            return audit(root)

    def test_consistent_artifact(self):
        result=self.run_audit();self.assertEqual(result['cases'][0]['annotated_mappings'],1)

    def test_mutations_rejected(self):
        mutations={
          'mapping_expected':lambda p,s,d:s['results'][0]['mapping_checks'][0].update(expected='orders.id'),
          'missing_annotation':lambda p,s,d:s['results'][0].update(mapping_checks=[]),
          'extra_annotation':lambda p,s,d:s['results'][0]['mapping_checks'].append(deepcopy(s['results'][0]['mapping_checks'][0])),
          'duplicate_entry':lambda p,s,d:d['entries'].append(deepcopy(d['entries'][0])),
          'policy_expected':lambda p,s,d:s['results'][0]['policy_checks'][0]['expected'].update(target='coupon'),
          'relation':lambda p,s,d:s['results'][0].update(relations=[]),
          'comparison':lambda p,s,d:s['results'][0].update(comparison_counts=[0]),
          'source_content':lambda p,s,d:d['sources'][0].update(content='ref\nB\n'),
          'candidate':lambda p,s,d:s['results'][0]['mapping_checks'][0].update(candidates=['orders.id']),
          'policy_questions':lambda p,s,d:s['results'][0]['policy_checks'][0].update(questions=[]),
          'approval':lambda p,s,d:d['entries'][0].update(status='approved'),
        }
        for name,mutation in mutations.items():
            with self.subTest(name=name),self.assertRaises(ValueError):self.run_audit(mutation)
