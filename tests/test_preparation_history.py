"""Historical review annotations survive source changes without granting approval."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from apps.factory_lab import preparation as p
from tests.test_preparation import approved, example


def review(draft):
    for entry in list(draft['entries']):
        if entry['kind']=='relation':
            draft=p.change(draft,entry['id'],'excluded',entry['target'],'Reviewed candidate')
        else:
            draft=p.change(draft,entry['id'],'approved',entry['target'] or 'context',
                           interpretation='Reviewed applicability')
    return draft


class PreparationHistoryTests(unittest.TestCase):
    def test_multiple_refresh_retirement_and_roundtrip(self):
        draft=approved()
        original=deepcopy(draft['review_history'])
        files,_=example()
        files.append({'name':'context.md','content':'First context'})
        draft=review(p.refresh(draft,files))
        first_hashes={s['name']:s['sha256'] for s in draft['sources']}
        first_history=deepcopy(draft['review_history'])
        files[-1]['content']='Second context'
        draft=p.refresh(draft,files)
        self.assertTrue(all(e['status']=='pending' for e in draft['entries']))
        self.assertEqual(draft['review_history'][:len(first_history)],first_history)
        old=next(e['previous_decision'] for e in draft['entries'] if e['source']['file']=='context.md')
        self.assertEqual(old['dependencies'],first_hashes)
        draft=review(draft)
        draft=review(p.refresh(draft,files[:-1]))
        retired=deepcopy(draft['retired_entries'])
        self.assertTrue(any(r['source']['file']=='context.md' for r in retired))
        draft=review(p.refresh(draft,files))
        self.assertEqual(draft['retired_entries'],retired)
        self.assertEqual(draft['review_history'][:len(original)],original)
        bundle=p.freeze(draft)
        restored=p.restore(json.loads(json.dumps(bundle)))
        self.assertEqual(restored['review_history'],draft['review_history'])
        self.assertEqual(restored['retired_entries'],retired)
        self.assertEqual(p.freeze(restored),bundle)
        changed=p.refresh(restored,example()[0])
        self.assertTrue(all(e['status']=='pending' for e in changed['entries']))

    def test_relation_index_shift_does_not_misattribute_history(self):
        files=[{'name':name,'content':'id\nvalue\n'} for name in ('a.csv','b.csv')]
        draft=p.create(files,example()[1])
        old=next(e for e in draft['entries'] if e['id']=='relation:0')
        draft=p.change(draft,old['id'],'excluded',old['target'],'Old source relation')
        # Reordering identical uploads is now a no-op, preserving original IDs.
        unchanged=p.refresh(draft,list(reversed(files)))
        self.assertEqual(unchanged,p.restore_draft(draft))
        # A changed snapshot still regenerates candidates; positional ID reuse
        # must not attach the old decision to a different directed relation.
        metadata={**draft['metadata'],'snapshot_id':'reordered-snapshot'}
        refreshed=p.refresh(draft,list(reversed(files)),metadata=metadata)
        new=next(e for e in refreshed['entries'] if e['id']=='relation:0')
        self.assertNotEqual(new['source']['file'],old['source']['file'])
        self.assertEqual(new['status'],'pending')
        self.assertNotIn('previous_decision',new)
        self.assertTrue(any(r['id']==old['id'] and r['note']=='Old source relation' for r in refreshed['retired_entries']))

    def test_direct_reapproval_preserves_superseded_decision(self):
        draft=approved()
        entry=next(e for e in draft['entries'] if e['kind']=='mapping')
        draft=p.change(draft,entry['id'],'excluded',entry['target'],'First reason')
        draft=p.change(draft,entry['id'],'approved',entry['target'],'Second reason')
        self.assertEqual(draft['review_history'][-1]['note'],'First reason')
        self.assertEqual(draft['review_history'][-1]['dependencies'],entry['dependencies'])
        self.assertEqual(p.restore(p.freeze(draft))['review_history'],draft['review_history'])

    def test_legacy_bundle_without_history_is_accepted(self):
        draft=approved()
        draft.pop('review_history')
        draft.pop('retired_entries')
        restored=p.restore(p.freeze(draft))
        self.assertEqual(restored['review_history'],[])

    def test_rehashed_malformed_history_is_rejected(self):
        bundle=p.freeze(approved())
        for field,value in [('dependencies',{'orders.csv':'bad'}),('status',[]),
                            ('source',{'file':'absent.csv','column':'id'}),
                            ('target',{}),('id','wrong'),('event','execute')]:
            with self.subTest(field=field):
                bad=deepcopy(bundle)
                bad['payload']['draft']['review_history'][0][field]=value
                bad['sha256']=p.digest(bad['payload'])
                with self.assertRaises(ValueError): p.restore(bad)
        bad=deepcopy(bundle)
        bad['payload']['draft']['entries'][0]['previous_decision']={'status':'approved'}
        bad['sha256']=p.digest(bad['payload'])
        with self.assertRaisesRegex(ValueError,'Historical annotations'): p.restore(bad)

    def test_limits_reject_without_mutation(self):
        draft=approved()
        before=deepcopy(draft)
        entry=draft['entries'][0]
        with patch.object(p,'MAX_HISTORY',len(draft['review_history'])):
            with self.assertRaisesRegex(ValueError,'Review history'):
                p.change(draft,entry['id'],'excluded',entry['target'],'Another decision')
        self.assertEqual(draft,before)
        with patch.object(p,'MAX_HISTORY_BYTES',10):
            with self.assertRaisesRegex(ValueError,'Review history'): p.freeze(draft)
        with patch.object(p,'MAX_DRAFT_BYTES',10):
            with self.assertRaisesRegex(ValueError,'Draft exceeds'): p.create(*example())
