import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import run_yago_binding_diagnostic as d

class TestBindingGuard(unittest.TestCase):
    def test_insufficient_budget_does_not_launch(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'ledger.json';p.write_text(json.dumps({'attempts':133,'reservations':[]}))
            with patch.object(d.study,'LEDGER',p),patch.object(d.study,'Gateway') as gateway:
                with self.assertRaises(d.study.BudgetStop):d.main()
                gateway.assert_not_called();self.assertFalse((p.parent/'binding-diagnostic-reservation.json').exists())
    def test_one_shot_guard_prevents_duplicate(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'ledger.json';p.write_text(json.dumps({'attempts':124,'reservations':[]}))
            g=p.parent/'binding-diagnostic-reservation.json';g.write_text('preserved')
            with patch.object(d.study,'LEDGER',p),patch.object(d.study,'Gateway') as gateway:
                with self.assertRaises(FileExistsError):d.main()
                gateway.assert_not_called();self.assertEqual(g.read_text(),'preserved')
