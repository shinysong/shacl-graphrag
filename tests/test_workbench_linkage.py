import copy

from rule_workbench.core import new_project
from rule_workbench.linkage import audit_relationship, table_digest


def fixture():
    p = new_project()
    for name, values in [('source', ['A', 'OLD', '', 'X', 'D', '001', 1]),
                         ('target', ['A', 'B', 'D', 'D', '1'])]:
        p['tables'].append({'id': name, 'name': name, 'columns': ['code'],
                            'rows': [{'code': v} for v in values],
                            'source': {'complete': True}})
    return p


def contract(p):
    return {'id': 'part', 'source_table': 'source', 'source_column': 'code',
            'target_table': 'target', 'target_column': 'code', 'status': 'confirmed',
            'source_digest': table_digest(p['tables'][0]),
            'target_digest': table_digest(p['tables'][1])}


def test_alias_duplicate_missing_and_type_distinctions():
    p = fixture(); before = copy.deepcopy(p)
    r = audit_relationship(p, contract(p), [{'source_value': 'OLD', 'target_value': 'B', 'evidence': 'legacy.csv:2'}])
    assert [x['status'] for x in r['results']] == [
        'linked', 'candidate_only', 'missing_key', 'unmatched_in_snapshot',
        'ambiguous', 'unmatched_in_snapshot', 'unmatched_in_snapshot']
    assert r['results'][1]['alias_candidates'] == [{'target_row': 2, 'evidence': 'legacy.csv:2'}]
    assert p == before


def test_partial_target_does_not_certify_unique_matches_or_absence():
    p = fixture(); p['tables'][1]['source']['truncated'] = True
    r = audit_relationship(p, contract(p))
    assert r['results'][0]['status'] == 'unknown_target_scope'
    assert r['results'][0]['exact_target_rows'] == [1]
    assert r['results'][3]['status'] == 'unknown_target_scope'
    assert r['results'][4]['status'] == 'ambiguous'


def test_undeclared_or_redacted_target_scope_is_unknown():
    for provenance in [{}, {'complete': True, 'redacted': True}]:
        p = fixture(); p['tables'][1]['source'] = provenance
        assert audit_relationship(p, contract(p))['results'][0]['status'] == 'unknown_target_scope'


def test_stale_and_unreviewed_mapping_cannot_link():
    p = fixture(); c = contract(p)
    p['tables'][0]['rows'][0]['code'] = 'B'
    assert set(audit_relationship(p, c)['counts']) == {'stale_mapping'}
    c['status'] = 'draft'
    assert set(audit_relationship(p, c)['counts']) == {'not_reviewed'}


def test_source_scope_preserved_in_denominator():
    p = fixture(); p['tables'][0]['source']['truncated'] = True
    r = audit_relationship(p, contract(p))
    assert r['source_truncated'] and r['denominator'] == 7
