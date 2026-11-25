"""Hosted opt-in deadline and monetary allocation never renew on restart."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from apps.factory_lab.public_runtime import PublicGateway
from apps.factory_lab.store import Store


class HostedDeadlineTests(unittest.TestCase):
    def test_fixed_deadline_and_ledger_survive_restart_and_reject_changed_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            end = (datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
            config = {'model': 'offline/model', 'provider': 'offline',
                'prompt_per_million': '1', 'completion_per_million': '2',
                'max_tokens': 1024, 'max_calls': 300, 'max_usd': '10',
                'hours': 8, 'absolute_deadline': end}
            store = Store(root/'state.sqlite')
            first = PublicGateway(store, root, config, 'offline-secret')
            store.reserve('offline', '0.1', first.session)
            again = PublicGateway(store, root, config, 'offline-secret')
            self.assertEqual(again.session, first.session)
            self.assertEqual(again.session['deadline'], end)
            self.assertEqual(store.budget()['attempts'], 1)
            with self.assertRaises(ValueError):
                PublicGateway(store, root, config|{'absolute_deadline':(datetime.now(timezone.utc)+timedelta(days=3)).isoformat()}, 'offline-secret')
            with self.assertRaises(ValueError):
                PublicGateway(store, root, config|{'absolute_deadline': '2026-12-03T14:59:59'}, 'offline-secret')
            with self.assertRaises(ValueError):
                PublicGateway(store, root, {k:v for k,v in config.items() if k!='absolute_deadline'}, 'offline-secret')
