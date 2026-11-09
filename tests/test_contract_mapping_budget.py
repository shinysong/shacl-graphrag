import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from scripts.run_contract_mapping import admit, used, assess, strict


class Budget(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.deadline = (self.now+timedelta(hours=1)).isoformat()
        self.ledger = {'reservations': [], 'attempts': 0}

    def test_failure_reservation_never_refunded(self):
        r = admit(self.ledger, 'one', Decimal('2'), self.now, self.deadline)
        r.update(state='resolved', status='output_failure', reported_usd='.01')
        self.assertEqual(used(self.ledger), Decimal('2'))
        with self.assertRaisesRegex(ValueError, 'budget_cap'):
            admit(self.ledger, 'two', Decimal('14'), self.now, self.deadline)

    def test_unresolved_duplicate_deadline(self):
        r = admit(self.ledger, 'one', Decimal('.1'), self.now, self.deadline)
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            admit(self.ledger, 'two', Decimal('.1'), self.now, self.deadline)
        r.update(state='resolved', status='completed', reported_usd='.01')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            admit(self.ledger, 'one', Decimal('.1'), self.now, self.deadline)
        with self.assertRaisesRegex(ValueError, 'deadline'):
            admit(self.ledger, 'two', Decimal('.1'), self.now, self.now.isoformat())

    def test_wrong_contract_remains_outcome(self):
        data = {'model': 'm', 'provider': 'p', 'usage': {'cost': .01, 'prompt_tokens': 20, 'completion_tokens': 10},
                'choices': [{'finish_reason': 'stop', 'message': {'content': '{"operation":"wrong","target":"wrong","scope":"wrong"}'}}]}
        result = assess(data, {'model': 'm', 'provider': 'p'}, 100, Decimal('.1'))
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['contract']['operation'], 'wrong')
        data['model'] = 'other'
        with self.assertRaisesRegex(ValueError, 'route_mismatch'):
            assess(data, {'model': 'm', 'provider': 'p'}, 100, Decimal('.1'))

    def test_duplicate_json_and_nonfinite_rejected(self):
        for value in ['{"a":1,"a":2}', '{"a":NaN}']:
            with self.assertRaises(ValueError):
                strict(value)


if __name__ == '__main__':
    unittest.main()
