"""Authored date-role development cases; not semantic extraction accuracy."""
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from apps.factory_lab import preparation as p, policy_dates as dates, workspace_policy
from apps.factory_lab.workspace_service import WorkspaceService
from apps.factory_lab.workspace_diff import decision_changes

META={'snapshot_id':'dates','as_of':'2026-11-17','currency':'KRW'}
class PolicyDateTests(unittest.TestCase):
 def draft(self,text):return p.create([{'name':'policy.md','content':text}],META)
 def approve(self,d,roles):
  e=d['entries'][0];items=dates.candidates(e['source']['text'])
  for item,role in zip(items,roles):item['role']=role
  return p.change(d,e['id'],'approved','shipping',interpretation='Reviewed source scope and date roles',temporal=items)
 def test_roles_distinguish_start_end_reference_and_expiry(self):
  cases=[('2027-01-01','start',False),('2027-01-01','end',True),('2027-01-01','context',True),
         ('2026-01-01','end',False),('2026-11-17','start',True),('2026-11-17','end',True),('2026-01-01','unresolved',False)]
  for value,role,allowed in cases:
   with self.subTest(value=value,role=role):
    d=self.draft('무료배송 정책 '+value)
    if allowed:
     reviewed=self.approve(d,[role]);workspace_policy.require_unambiguous(reviewed)
     self.assertEqual(p.restore_draft(reviewed),reviewed)
    else:
     with self.assertRaises(ValueError):self.approve(d,[role])
 def test_occurrences_and_unsupported_periods_are_not_silently_merged(self):
  d=self.draft('무료배송: 2026-01-01부터 2027-01-01까지. 검토일 2027-01-01.')
  reviewed=self.approve(d,['start','end','context'])
  self.assertEqual(len(reviewed['entries'][0]['temporal']),3)
  for roles in (['start','end','end'],['end','start','context']):
   with self.assertRaises(ValueError):self.approve(d,roles)
  bad=deepcopy(reviewed);bad['entries'][0]['temporal'][0]['start']+=1
  with self.assertRaises(ValueError):p.restore_draft(bad)
 def test_history_diff_refresh_and_legacy_execution_boundary(self):
  d=self.draft('무료배송 2026-01-01')
  legacy=p.change(d,d['entries'][0]['id'],'approved','shipping',interpretation='Legacy review')
  self.assertEqual(p.restore_draft(legacy),legacy)
  with self.assertRaisesRegex(ValueError,'date roles'):workspace_policy.require_unambiguous(legacy)
  reviewed=self.approve(legacy,['start']);changed=self.approve(reviewed,['context'])
  self.assertIn('temporal',decision_changes(reviewed,changed)[0]['changed_fields'])
  self.assertEqual(p.restore_draft(changed),changed)
  fresh=p.refresh(changed,[{'name':'policy.md','content':'무료배송 2026-02-01'}])
  self.assertNotIn('temporal',fresh['entries'][0])
  self.assertEqual(fresh['entries'][0]['previous_decision']['temporal'][0]['role'],'context')
  self.assertEqual(p.restore_draft(fresh),fresh)
 def test_service_buffer_save_and_reload_do_not_approve(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'db';service=WorkspaceService(path)
   row=service.store.create('dates',self.draft('📅 무료배송은 2027-01-01까지 적용'))
   view=service.view(row['id']);e=view['draft']['entries'][0]
   items=view['policy_date_candidates'][e['id']];items[0]['role']='end'
   decision=dict(entry_id=e['id'],status='approved',target='shipping',note='',interpretation='Inclusive end date',temporal=items)
   service.handle(dict(action='save_review_buffer',id=row['id'],revision=1,generation=0,content={'entries':[decision],'policies':[]}))
   restarted=WorkspaceService(path);self.assertEqual(restarted.view(row['id'])['draft']['entries'][0]['status'],'pending')
   updated=restarted.handle(dict(action='change',id=row['id'],revision=1,decisions=[decision]))
   self.assertEqual(updated['draft']['entries'][0]['temporal'][0]['role'],'end')
   self.assertEqual(restarted.store.get(row['id'],1)['draft']['entries'][0]['status'],'pending')
