import unittest
from scripts import analyze_shared_semantics_study as a


class SharedSemanticsAnalysisTests(unittest.TestCase):
    def test_independent_decisions_missing_blocked_and_cost(self):
        source = {'products': [{'id': 'p'}], 'suppliers': [
            {'id': 's1', 'location': 'X', 'cost': 5},
            {'id': 's2', 'location': 'Y', 'cost': 2}], 'edges': [
            {'id': 'e1', 'product': 'p', 'supplier': 's1', 'role': 'main'},
            {'id': 'e2', 'product': 'p', 'supplier': 's2', 'role': 'main'}]}
        config = dict(location_field='location', role_aliases={'main': 'primary'},
                      allowed_roles=['primary'], restricted_countries=['X'])
        self.assertEqual(a.reference(source, config, 'p', 'audit')['output']['decision'], 'blocked')
        self.assertEqual(a.reference(source, config, 'p', 'recommend')['output']['value'], 's2')
        del source['suppliers'][1]['location']
        self.assertEqual(a.reference(source, config, 'p', 'audit')['output']['decision'], 'blocked')
        self.assertEqual(a.reference(source, config, 'p', 'recommend')['output']['decision'], 'unknown')
        self.assertEqual(a.reference(source, config, 'missing', 'countries')['output'],
                         {'decision': 'unknown', 'value': []})

    def test_complete_matrix_missing_duplicate_and_id_binding(self):
        ids = ['/'.join(map(str, (n, s, c, f, p, t, arm))) for n in [24, 96]
               for s in [17, 29] for c in a.STATES for f in a.FAULTS for p in a.SUBJECTS
               for t in a.TASKS for arm in a.ARMS]
        rows = []
        for identity in ids:
            n, s, c, f, p, t, arm = identity.split('/')
            rows.append(dict(id=identity, size=int(n), seed=int(s), snapshot=c, fault=f,
                             subject=p, workflow=t, arm=arm, status='ok'))
        manifest = dict(sizes=[24, 96], seeds=[17, 29], protocol='shared-semantics-1',
                        status='complete', completed_rows=12288, planned_rows=12288)
        a.reconcile(manifest, ids, rows)
        for bad in (rows[:-1], rows[:-1] + rows[:1], [{**rows[0], 'subject': 'wrong'}, *rows[1:]]):
            with self.assertRaises(ValueError):
                a.reconcile(manifest, ids, bad)
        with self.assertRaises(ValueError):
            a.reconcile(manifest, ids[:-1] + ids[:1], rows)
