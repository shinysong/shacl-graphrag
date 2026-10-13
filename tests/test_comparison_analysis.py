"""Invented scored records only; these tests are not benchmark evidence."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from scripts import analyze_comparison_study as analysis


def fixture(answerable=True):
    record = {'status': 'completed', 'config': {'conditions': ['shacl', 'code', 'llm', 'none'], 'repeat_count': 3},
              'cases': [], 'rows': []}
    for entity in ['A'*20, 'B'*20]:
        for variant in ['clean', 'missing']:
            case_id = entity + '-' + variant
            record['cases'].append({'case_id': case_id, 'entity': entity})
            for condition in record['config']['conditions']:
                for repeat in range(3):
                    abstain = variant == 'missing'
                    record['rows'].append({'case_id': case_id, 'entity': entity, 'condition': condition, 'repeat': repeat,
                                           'status': 'ok', 'source_answerable': answerable,
                                           'answer': {'status': 'abstain' if abstain else 'answer'},
                                           'correct': not abstain, 'wrong': False,
                                           'unnecessary_abstention': abstain and answerable, 'extra_retrievals': 0})
    return record


class ComparisonAnalysisTests(unittest.TestCase):
    def test_identical_groups_have_zero_ci_without_repeat_pseudoreplication(self):
        result = analysis.analyze(fixture())
        for comparison in result['primary_contrasts'].values():
            for metric in ['wrong_rate_all', 'unnecessary_abstention_rate']:
                self.assertEqual(comparison[metric], {'difference': 0, 'ci95': [0, 0], 'eligible_clusters': 2})
        self.assertEqual(result['descriptive']['shacl']['total'], 12)

    def test_zero_eligible_is_null(self):
        result = analysis.analyze(fixture(False))
        self.assertIsNone(result['descriptive']['code']['unnecessary_abstention_rate'])
        self.assertEqual(result['primary_contrasts']['shacl-minus-code']['unnecessary_abstention_rate'],
                         {'difference': None, 'ci95': None, 'eligible_clusters': 0})

    def test_errors_remain_in_denominator_and_exclusive_counts(self):
        record = fixture()
        row = record['rows'][0]
        row.update(status='error', answer=None, correct=False, wrong=False)
        record['status'] = 'completed_with_errors'
        group = analysis.analyze(record)['descriptive']['shacl']
        self.assertEqual(group['errors'], 1)
        self.assertEqual(group['total'], 12)
        self.assertEqual(group['source_answerable'], 12)
        self.assertEqual(group['coverage'], 5/12)
        self.assertEqual(sum(group[k] for k in ['correct', 'wrong', 'abstained', 'errors']), group['total'])

    def test_unbalanced_repeats_and_duplicates_are_rejected(self):
        record = fixture()
        record['rows'].pop()
        with self.assertRaisesRegex(ValueError, 'grid'):
            analysis.analyze(record)
        record = fixture()
        record['rows'].append(copy.deepcopy(record['rows'][0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            analysis.analyze(record)

    def test_entire_missing_case_is_rejected_from_manifest(self):
        record = fixture()
        case_id = record['cases'][0]['case_id']
        record['rows'] = [r for r in record['rows'] if r['case_id'] != case_id]
        with self.assertRaisesRegex(ValueError, 'grid'):
            analysis.analyze(record)

    def test_cluster_contrast_direction_and_determinism(self):
        record = fixture()
        for row in record['rows']:
            if row['condition'] == 'shacl' and row['answer']['status'] == 'answer':
                row.update(correct=False, wrong=True)
        result = analysis.analyze(record)
        difference = result['primary_contrasts']['shacl-minus-code']['wrong_rate_all']
        self.assertEqual(difference['difference'], .5)
        self.assertEqual(difference['ci95'], [.5, .5])
        self.assertEqual(analysis.paired_bootstrap([-.2, .5]), analysis.paired_bootstrap([-.2, .5]))

    def test_cli_freezes_raw_bytes_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            record = Path(temp) / 'input.json'
            record.write_text(json.dumps(fixture()))
            output = Path(temp) / 'analysis'
            analysis.main([str(record), '--output-dir', str(output)])
            self.assertEqual((output / 'record.json').read_bytes(), record.read_bytes())
            result = json.loads((output / 'analysis.json').read_text())
            self.assertEqual(result['analysis_config']['bootstrap_samples'], 10000)
            self.assertIn('<svg', (output / 'risk-coverage.svg').read_text())
            with self.assertRaises(FileExistsError):
                analysis.main([str(record), '--output-dir', str(output)])

    def test_no_answers_has_null_risk(self):
        rows = [{'condition': 'llm', 'status': 'error', 'answer': None, 'source_answerable': False}]
        group = analysis.summarize(rows)['llm']
        self.assertIsNone(group['risk_among_answers'])
        self.assertEqual(group['coverage'], 0)


if __name__ == '__main__':
    unittest.main()
