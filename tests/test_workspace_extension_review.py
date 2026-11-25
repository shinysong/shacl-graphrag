"""Authored export fixtures exercise local approval/reuse, not upstream efficacy."""
import base64
from copy import deepcopy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import yaml

from apps.factory_lab import preparation as p, workspace_lookup
from apps.factory_lab.workspace_service import WorkspaceService
from tests.workspace_fixtures import approved


class ExtensionReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.service = WorkspaceService(Path(self.temp.name) / 'work.sqlite')
        self.row = self.service.store.create('Authored review integration', approved())
        self.entry = next(e for e in self.row['draft']['entries'] if e['kind'] == 'mapping' and
                          any(s['name'] == e['source']['file'] and s['rows'] for s in self.row['draft']['sources']))
        self.source = next(s for s in self.row['draft']['sources'] if s['name'] == self.entry['source']['file'])
        self.document = {'data_layer': {'databases': [{'id': 'opaque-db', 'schemas': [
            {'id': 'opaque-schema', 'tables': [{'id': 'opaque-table', 'name': Path(self.source['name']).stem,
                'columns': [{'id': 'opaque-column', 'name': self.entry['source']['column']}]}]}]}]},
            'semantic_layer': {'terms': [{'id': 'opaque-term', 'represents': ['opaque-table'],
                'columns_attributes': [{'id': 'opaque-attribute', 'name': 'Meaning', 'column_id': 'opaque-column'}]}]}}

    def import_proposal(self, document=None, key='import'):
        return self.service.handle({'action': 'extension_import', 'id': self.row['id'], 'revision': 1,
            'request_key': key, 'raw_base64': base64.b64encode(yaml.safe_dump(document or self.document).encode()).decode()})['operation']

    def request(self, operation, **changes):
        return {'action': 'extension_review', 'id': self.row['id'], 'revision': 1,
                'request_key': 'review', 'operation_id': operation['id'],
                'candidate_id': operation['result']['fields'][0]['id'], 'entry_id': self.entry['id'],
                'target': 'source_only', 'interpretation': 'User-edited column interpretation',
                'note': 'Explicit local decision', 'manual_binding': '', **changes}

    def test_approval_reuses_existing_lookup_preserves_proposal_and_other_decisions(self):
        original = self.import_proposal()
        request = self.request(original)
        result = self.service.handle(request)
        self.assertEqual(result['operation']['state'], 'completed')
        row = self.service.store.get(self.row['id'])
        self.assertEqual(row['revision'], 2)
        self.assertEqual(row['draft']['sources'], self.row['draft']['sources'])
        self.assertEqual(row['draft']['saved_suggestions'], self.row['draft']['saved_suggestions'])
        self.assertEqual([e for e in row['draft']['entries'] if e['id'] != self.entry['id']],
                         [e for e in self.row['draft']['entries'] if e['id'] != self.entry['id']])
        self.assertEqual(self.service.store.operation(self.row['id'], original['id']), original)
        self.assertEqual(original['result']['status'], 'pending')
        value = self.source['rows'][0][self.entry['source']['column']]
        lookup = self.service.handle({'action': 'lookup', 'id': row['id'], 'revision': 2,
            'request_key': 'lookup', 'selection': {'entry_id': self.entry['id'], 'value': value}})['operation']
        self.assertEqual(lookup['state'], 'completed')
        evidence = lookup['result']
        self.assertTrue(evidence['records'])
        self.assertEqual(evidence['records'][0]['values'][self.entry['source']['column']], value)
        annotation = evidence['scope']['extension_reviews'][0]
        self.assertEqual(annotation['operation_id'], original['id'])
        self.assertEqual(annotation['raw_sha256'], original['result']['raw_sha256'])
        self.assertFalse(annotation['producer_authenticated'])
        self.assertEqual(annotation['interpretation'], request['interpretation'])
        replay = WorkspaceService(self.service.store.path).handle(request)
        self.assertTrue(replay['reused'])
        self.assertEqual(replay['operation'], result['operation'])
        self.assertEqual(self.service.store.get(row['id'])['revision'], 2)
        with self.assertRaisesRegex(ValueError, 'different input'):
            self.service.handle({**request, 'interpretation': 'Changed'})

    def test_attribute_can_map_to_existing_canonical_target(self):
        op = self.import_proposal()
        candidate = next(c for c in op['result']['fields'] if c['kind'] == 'column_attribute')
        result = self.service.handle(self.request(op, candidate_id=candidate['id'], target=self.entry['target']))
        self.assertEqual(result['operation']['state'], 'completed')
        self.assertEqual(p.restore_draft(self.service.store.get(self.row['id'])['draft'])['extension_reviews'][0]['candidate_id'], candidate['id'])

    def test_unrelated_ids_require_visible_manual_binding(self):
        doc = deepcopy(self.document)
        table = doc['data_layer']['databases'][0]['schemas'][0]['tables'][0]
        table['name'] = 'UnrelatedTable'
        table['columns'][0]['name'] = 'UnrelatedColumn'
        op = self.import_proposal(doc)
        failed = self.service.handle(self.request(op))['operation']
        self.assertEqual(failed['state'], 'failed')
        self.assertIn('explicit manual', failed['error'])
        self.assertEqual(self.service.store.get(self.row['id'])['draft'], self.row['draft'])
        success = self.service.handle(self.request(op, request_key='manual', manual_binding='I explicitly bind this exported field to the selected uploaded column.'))['operation']
        self.assertEqual(success['state'], 'completed')
        self.assertEqual(success['result']['review']['binding_method'], 'explicit_manual_binding')

    def test_unresolved_sql_and_unknown_targets_fail_without_adoption(self):
        doc = deepcopy(self.document)
        doc['semantic_layer']['terms'][0]['represents'] = ['missing-table']
        unresolved = self.import_proposal(doc, 'unresolved')
        result = self.service.handle(self.request(unresolved, request_key='unresolved-review'))['operation']
        self.assertEqual(result['state'], 'failed')
        self.assertIn('references', result['error'])
        op = self.import_proposal(key='valid')
        for changes in ({'candidate_id': 'sql:SELECT * FROM source'}, {'target': 'new_table.new_field'}, {'interpretation': ''}):
            request = self.request(op, request_key='bad-' + str(len(self.service.store.operations(self.row['id']))), **changes)
            failed = self.service.handle(request)['operation']
            self.assertEqual(failed['state'], 'failed')
            self.assertTrue(self.service.handle(request)['reused'])
        self.assertEqual(self.service.store.get(self.row['id'])['draft'], self.row['draft'])

    def test_stale_revision_digest_and_operation_scope_are_rejected(self):
        op = self.import_proposal()
        changed = p.change(self.row['draft'], self.entry['id'], 'approved', self.entry['target'], 'New note')
        self.service.store.save(self.row['id'], changed, 1)
        with self.assertRaisesRegex(ValueError, 'current active revision'):
            self.service.handle(self.request(op))
        failed = self.service.handle(self.request(op, revision=2))['operation']
        self.assertEqual(failed['state'], 'failed')
        self.assertEqual(self.service.store.get(self.row['id'])['revision'], 2)
        # A digest mismatch is independent of the proposal's claimed revision.
        from apps.factory_lab.workspace_extension_review import _adopt
        with self.assertRaisesRegex(ValueError, 'digest'):
            _adopt(self.row['draft'], 'f' * 64, 1, op,
                   {k: v for k, v in self.request(op).items() if k not in ('action', 'id', 'revision', 'request_key')}, 'review')
        foreign = self.service.store.create('Other workspace', approved())
        failed = self.service.handle({**self.request(op), 'id': foreign['id']})['operation']
        self.assertEqual(failed['state'], 'failed')
        self.assertIn('this workspace', failed['error'])

    def test_capacity_failure_rolls_back_decision_and_retains_failed_attempt(self):
        op = self.import_proposal()
        from apps.factory_lab import workspace_store
        original = workspace_store.require_capacity
        calls = []
        def fail_commit(db, amount):
            calls.append(amount)
            if len(calls) == 2:
                raise ValueError('Injected commit capacity failure')
            return original(db, amount)
        with patch.object(workspace_store, 'require_capacity', fail_commit):
            result = self.service.handle(self.request(op))
        self.assertEqual(result['operation']['state'], 'failed')
        self.assertEqual(self.service.store.get(self.row['id'])['draft'], self.row['draft'])
        self.assertEqual(len(self.service.store.revisions(self.row['id'])), 1)
        self.assertTrue(self.service.handle(self.request(op))['reused'])

    def test_refresh_retains_historical_annotation_without_active_claim_and_export_restores(self):
        op = self.import_proposal()
        self.service.handle(self.request(op))
        draft = self.service.store.get(self.row['id'])['draft']
        restored = p.restore_draft(draft)
        self.assertEqual(restored['extension_reviews'], draft['extension_reviews'])
        exported = self.service.handle({'action': 'export', 'id': self.row['id'], 'revision': 2})
        imported = self.service.handle({'action': 'import', 'title': 'Portable annotation', 'bundle': exported})
        self.assertFalse(imported['draft']['extension_reviews'][0]['producer_authenticated'])
        import csv
        import io
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=self.source['headers'])
        writer.writeheader()
        writer.writerows(self.source['rows'] + self.source['rows'][:1])
        files = [{'name': s['name'], 'content': output.getvalue() if s['name'] == self.source['name'] else s['content']} for s in draft['sources']]
        refreshed = p.refresh(draft, files)
        self.assertTrue(refreshed['extension_reviews'][0]['invalidated'])
        self.assertFalse(workspace_lookup.row_catalog(refreshed))
        self.assertEqual(p.restore_draft(refreshed)['extension_reviews'], refreshed['extension_reviews'])
        forged = deepcopy(draft)
        forged['extension_reviews'][0]['producer_authenticated'] = True
        with self.assertRaisesRegex(ValueError, 'authenticate'):
            p.restore_draft(forged)

    def test_current_decision_change_no_longer_advertises_previous_annotation(self):
        self.service.handle(self.request(self.import_proposal()))
        draft = self.service.store.get(self.row['id'])['draft']
        changed = p.change(draft, self.entry['id'], 'approved', 'source_only', interpretation='New later interpretation')
        field = next(c for c in workspace_lookup.row_catalog(changed) if c['entry_id'] == self.entry['id'])
        self.assertEqual(field['extension_reviews'], [])
        self.assertEqual(len(changed['extension_reviews']), 1)

    def test_group_adopts_multiple_fields_once_and_rejects_partial_group(self):
        second = next(e for e in self.row['draft']['entries'] if e['kind'] == 'mapping' and
                      e['source']['file'] == self.source['name'] and e['id'] != self.entry['id'])
        doc = deepcopy(self.document)
        doc['data_layer']['databases'][0]['schemas'][0]['tables'][0]['columns'].append(
            {'id': 'second-column', 'name': second['source']['column']})
        op = self.import_proposal(doc)
        first = self.request(op)
        decision = {k: first[k] for k in ('candidate_id', 'entry_id', 'target', 'interpretation', 'note', 'manual_binding')}
        candidate = next(c for c in op['result']['fields'] if c['source_id'] == 'second-column')
        decisions = [decision, {**decision, 'candidate_id': candidate['id'], 'entry_id': second['id']}]
        request = {'action': 'extension_review_batch', 'id': self.row['id'], 'revision': 1,
                   'request_key': 'batch', 'operation_id': op['id'], 'decisions': decisions}
        bad = deepcopy(request)
        bad['request_key'] = 'bad-batch'
        bad['decisions'][1]['target'] = 'unsupported.sql'
        self.assertEqual(self.service.handle(bad)['operation']['state'], 'failed')
        self.assertEqual(self.service.store.get(self.row['id'])['draft'], self.row['draft'])
        result = self.service.handle(request)
        self.assertEqual(result['operation']['state'], 'completed')
        self.assertEqual(len(result['operation']['result']['reviews']), 2)
        row = self.service.store.get(self.row['id'])
        self.assertEqual(row['revision'], 2)
        self.assertEqual(len(row['draft']['extension_reviews']), 2)
        self.assertTrue(self.service.handle(request)['reused'])
        duplicate = deepcopy(request)
        duplicate['decisions'][1]['entry_id'] = self.entry['id']
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.service.handle(duplicate)
