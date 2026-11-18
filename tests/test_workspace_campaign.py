"""Offline runner lifecycle tests; no provider or quality assertions."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.workspace_proposal_campaign import execute, export_attempts
from scripts.workspace_proposal_preflight import inspect
import test_workspace_preflight


class CampaignTests(unittest.TestCase):
    def fixture(self, root):
        _, config = test_workspace_preflight.PreflightTests().fixture(root)
        report = inspect(root, root/'endpoints.json', config)
        auth = {k: report[k] for k in ('config_sha256','manifest_sha256','endpoints_sha256')}
        auth.update(approved=True, approval_reference='Offline scripted fixture only',
                    deadline=(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat())
        return config, auth

    def test_saved_response_and_no_rerun(self):
        with tempfile.TemporaryDirectory() as tmp, patch('httpx.Client', side_effect=AssertionError('No network')):
            root=Path(tmp);config,auth=self.fixture(root);calls=[]
            class Scripted:
                def __init__(self, store, directory, config, key): self.store=store
                def call(self,rid,messages):
                    self_outer.assertEqual(self.store.get(rid)['status'],'running')
                    calls.append(rid);return {'role':'assistant','content':'{"relation_assessments":[]}'}
            self_outer=self
            result=execute(root,root/'endpoints.json',config,auth,root/'run',None,Scripted)
            self.assertEqual(result['attempts'][0]['status'],'response')
            self.assertEqual(export_attempts(root/'run'),result)
            with self.assertRaises(FileExistsError):execute(root,root/'endpoints.json',config,auth,root/'run',None,Scripted)
            self.assertEqual(len(calls),1)

    def test_interruption_preserves_unresolved_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config,auth=self.fixture(root)
            class Interrupted:
                def __init__(self,store,directory,config,key):
                    self.store=store;self.session=json.loads((directory/'session.json').read_text())
                def call(self,rid,messages):
                    self.store.reserve(rid,'0.01',self.session)
                    raise KeyboardInterrupt()
            with self.assertRaises(KeyboardInterrupt):execute(root,root/'endpoints.json',config,auth,root/'run',None,Interrupted)
            result=export_attempts(root/'run')
            self.assertEqual(result['attempts'][0]['error'],'running')
            self.assertEqual(result['budget']['unresolved'],1)
            self.assertEqual(result['budget']['reserved_nonrefunded_usd'],'0.01')

    def test_invalid_scope_and_failed_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config,auth=self.fixture(root)
            for change in ({'approved':False},{'manifest_sha256':'wrong'},{'deadline':'2000-01-01T00:00:00+00:00'}):
                with self.assertRaises(ValueError):execute(root,root/'endpoints.json',config,auth|change,root/'run',None)
            self.assertFalse((root/'run').exists())
            class Failed:
                def __init__(self,*args):pass
                def call(self,*args):raise RuntimeError('do not persist sensitive exception text')
            result=execute(root,root/'endpoints.json',config,auth,root/'run',None,Failed)
            self.assertEqual(result['attempts'][0]['status'],'failed')
            self.assertNotIn('sensitive',json.dumps(result))
