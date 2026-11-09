import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from scripts.sbom_change_scope import query, sql_answer, flags, evaluate


class ChangeScope(unittest.TestCase):
    def graph(self, edges, sha):
        return {'nodes': set('ABCD'), 'edges': set(edges), 'versions': {n: '1' for n in 'ABCD'}, 'source_sha256': sha}

    def test_new_predecessor_not_in_old_answer(self):
        before = self.graph([('A','B')], 'old')
        after = self.graph([('A','B'),('C','A')], 'new')
        old, footprint = query(before, 'B', 'transitive_dependents')
        new, _ = query(after, 'B', 'transitive_dependents')
        self.assertEqual(old, {'A'}); self.assertEqual(new, {'A','C'})
        f = flags(before, after, 'B', 'transitive_dependents', old, footprint)
        self.assertTrue(f['complete_delta_read_footprint'])
        self.assertFalse(f['answer_node_versions_only'])

    def test_cycle_and_direct_self_edge(self):
        g = self.graph([('A','A'),('A','B'),('B','A'),('B','C')], 'old')
        for operation in ('direct_dependencies','transitive_dependencies','direct_dependents','transitive_dependents'):
            self.assertEqual(query(g,'A',operation)[0],sql_answer(g,'A',operation))
        self.assertIn('A',query(g,'A','direct_dependencies')[0])
        self.assertNotIn('A',query(g,'A','transitive_dependencies')[0])

    def test_reference_failure_keeps_all_planned_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = {'metadata': {'component': {'bom-ref': 'A', 'type': 'application', 'name': 'a'}},
                   'components': [], 'dependencies': [{'ref': 'A', 'dependsOn': []}]}
            source = root/'source.json'; source.write_text(json.dumps(doc))
            with patch('scripts.sbom_change_scope.sql_answer', side_effect=RuntimeError('injected_reference_failure')):
                evaluate(source, source, root/'result')
            result = json.loads((root/'result/evaluation.json').read_text())
            self.assertEqual((result['planned'],result['completed'],result['failures']), (4,0,4))
            self.assertEqual(len((root/'result/rows.jsonl').read_text().splitlines()),4)
            self.assertTrue(all(r['error_type']=='RuntimeError' and r['before']==[] for r in result['rows']))
