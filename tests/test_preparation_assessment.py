"""Scripted model contract checks, not semantic quality measurements."""
import json
import unittest
from copy import deepcopy
from apps.factory_lab import preparation as p
from apps.factory_lab.preparation_model import ModelProposalGenerator


FILES=[{'name':'orders.csv','content':'id,status\nX1,paid\n'},
       {'name':'products.csv','content':'id,name,category\nX1,Shirt,clothes\n'},
       {'name':'dictionary.md','content':'The identifiers are unrelated despite equal strings.'}]
META={'snapshot_id':'assessment','as_of':'2026-11-17','currency':'KRW'}


class AssessmentTests(unittest.TestCase):
    def generate(self, mutate=lambda r: None):
        self.calls=[]
        def call(messages):
            packet=json.loads(messages[1]['content']);self.calls.append(packet)
            self.assertTrue(packet['existing_relations'])
            response={'choices':[{'id':e['id'],'target':'','reason':'Scripted unresolved'}
                                 for e in packet['entries']],
                      'relation_assessments':[{'id':e['id'],'assessment':'contradicted',
                          'reason':'Scripted denial assessment','evidence':['policy:dictionary.md:1'],
                          'questions':['Do these identifiers refer to different objects?']}
                          for e in packet['existing_relations']]}
            mutate(response)
            return {'content':json.dumps(response)}
        return p.create(FILES,META,generator=ModelProposalGenerator(call,'scripted-assessment'))

    def test_assessment_preserves_candidates_and_restore_without_call(self):
        draft=self.generate()
        relations=[e for e in draft['entries'] if e['kind']=='relation']
        self.assertEqual(len(relations),len(self.calls[0]['existing_relations']))
        for e in relations:
            self.assertEqual(e['status'],'pending')
            self.assertEqual(e['extraction']['assessment'],'contradicted')
            self.assertIn('overlap',e)
            self.assertEqual(e['extraction']['source_evidence'][0]['file'],'dictionary.md')
        self.assertEqual(p.restore_draft(draft)['entries'],draft['entries'])
        self.assertEqual(len(self.calls),1)
        damaged=deepcopy(draft)
        for collection in ['entries','saved_suggestions']:
            next(e for e in damaged[collection] if e['kind']=='relation')['extraction']['assessment']='approve'
        with self.assertRaises(ValueError):p.restore_draft(damaged)

    def test_invalid_assessments_are_rejected_without_retry(self):
        for field,value in [('id','unknown'),('assessment','approved'),('assessment',True),
                            ('evidence',[]),('evidence',['policy:missing.md:1']),('reason',' ')]:
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                self.generate(lambda r:r['relation_assessments'][0].update({field:value}))
            self.assertEqual(len(self.calls),1)
        with self.assertRaises(ValueError):
            self.generate(lambda r:r['relation_assessments'].append(r['relation_assessments'][0]))

    def test_omission_and_uncertain_are_not_approval(self):
        draft=self.generate(lambda r:r.pop('relation_assessments'))
        self.assertTrue(all('assessment' not in e.get('extraction',{}) for e in draft['entries']))
        def uncertain(r):
            for e in r['relation_assessments']:e.update(assessment='uncertain',evidence=[])
        draft=self.generate(uncertain)
        self.assertTrue(all(e['status']=='pending' for e in p.restore_draft(draft)['entries']))

    def test_refresh_preserves_original_proposals_and_edited_target(self):
        draft=self.generate()
        relation=next(e for e in draft['entries'] if e['kind']=='relation')
        target=deepcopy(relation['target']);target['column']='status' if target['file']=='orders.csv' else 'name'
        draft=p.change(draft,relation['id'],'pending',target,'Edited target','Different interpretation')
        class NoCall:
            def suggest(self,sources):raise AssertionError('Identical upload must not regenerate')
        unchanged=p.refresh(draft,list(reversed(FILES)),generator=NoCall())
        self.assertEqual(p.restore_draft(unchanged),p.restore_draft(draft))
        self.assertEqual(unchanged['saved_suggestions'],draft['saved_suggestions'])
        files=deepcopy(FILES);files[-1]['content']+=' Updated source.'
        changed=p.restore_draft(p.refresh(draft,files))
        self.assertTrue(all('assessment' not in e.get('extraction',{}) for e in changed['entries']))
        self.assertTrue(all(e['status']=='pending' for e in changed['entries']))
        self.assertEqual(len(self.calls),1)
