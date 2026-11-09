import unittest
from scripts.answer_withholding_accounting import classify_field, summarize, STATUSES


def row(i='q:B:voltage', support=True, status='completed', withheld=False):
    return dict(field_id=i, selected_support=support, execution_status=status, withheld=withheld)


class AccountingTests(unittest.TestCase):
    def test_all_support_and_observation_combinations(self):
        for support in (True, False, None):
            for withheld in (True, False, None):
                got = classify_field(row(support=support, withheld=withheld))
                expected = ('unknown', 'not_evaluable') if support is None else (
                    ('ineligible', 'not_applicable') if not support else
                    ('eligible', 'not_evaluable' if withheld is None else ('yes' if withheld else 'no')))
                self.assertEqual(tuple(got.values()), expected)

    def test_failure_is_unknown_not_safe(self):
        for status in STATUSES - {'completed'}:
            self.assertEqual(classify_field(row(status=status, withheld=None))['rating'], 'not_evaluable')
            with self.assertRaises(ValueError): classify_field(row(status=status))

    def test_full_denominator_and_order_invariance(self):
        rows = [row('a', withheld=True), row('b'), row('c', status='provider_failure', withheld=None),
                row('d', support=False, withheld=True), row('e', support=None, withheld=None)]
        got = summarize(rows)
        self.assertEqual(got, summarize(reversed(rows)))
        self.assertEqual(got['planned_fields'], 5)
        self.assertEqual(got['counts']['eligible'], 3)
        self.assertEqual(got['eligible_unknown'], 1)
        self.assertEqual(got['observed_unnecessary_withholding_lower_bound'], 1/3)
        self.assertEqual(got['conditional_evaluable_rate'], 1/2)
        self.assertEqual(sum(got['execution_status_counts'].values()), 5)

    def test_empty_and_no_eligible_not_perfect(self):
        for rows in ([], [row(support=False)]):
            got = summarize(rows)
            self.assertIsNone(got['observed_unnecessary_withholding_lower_bound'])
            self.assertIsNone(got['conditional_evaluable_rate'])

    def test_duplicate_or_invalid_input_rejected(self):
        with self.assertRaises(ValueError): summarize([row(), row()])
        for change in ({'selected_support': 1}, {'withheld': 0}, {'field_id': ''},
                       {'execution_status': []}, {'extra': 'gold'}):
            with self.assertRaises(ValueError): classify_field(dict(row(), **change))

    def test_no_mutation(self):
        original=row(); snapshot=original.copy(); summarize([original]); self.assertEqual(original,snapshot)
