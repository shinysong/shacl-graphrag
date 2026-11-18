"""Catalog-size selector study. No evaluator, credentials, or model calls.

Nested catalogs retain six original targets and add genuinely executable synthetic
record queries. This isolates distractor growth, not a growing number of user intents.
"""
import copy
import hashlib
import json
import sqlite3
from pathlib import Path
from .core import CatalogIndex
from .model_selection import SYSTEM, parse

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'research/query-contracts-1/selection-development-001/catalog.json'
KINDS = ('MaintenanceRecord', 'CalibrationRecord', 'InspectionRecord',
         'SupplierAssignment', 'MaterialLotRecord', 'WorkInstruction',
         'OperatorAssignment', 'ToolAssignment', 'ShipmentRecord',
         'PurchaseOrderRecord', 'DocumentRevision')
SIZES = (6, 24, 72)
SCOPES = ('all', 'current', 'expired')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def catalog(size):
    if size not in SIZES:
        raise ValueError('Unsupported catalog size')
    result = json.loads(BASE.read_text())['catalog']
    for kind in KINDS:
        for subject in ('Machine', 'Order'):
            for scope in SCOPES:
                tool = f'{kind.lower()}_{subject.lower()}_{scope}'
                temporal = {'all': 'complete current and past history in selected view',
                            'current': 'valid on the snapshot date',
                            'expired': 'expired before the snapshot date'}[scope]
                result.append({
                    'id': tool + '.v1', 'tool': tool, 'revision': 1,
                    'description': f'{kind} records linked to a {subject}; {temporal}.',
                    'input': {subject.lower() + '_id': {'semantic_type': subject + 'Id'}},
                    'output_bindings': {'rows[].subject.id': subject + 'Id',
                                        'rows[].record.id': kind + 'Id'},
                    'evidence_support': [kind, scope + '_records'],
                    'does_not_establish': ['qualification_applicability', 'delivery_feasibility',
                                           'document_authenticity', 'physical_approval'],
                    'result_limit': 30,
                    'empty_semantics': 'No matching record in selected synthetic ledger; not source absence.',
                    'execution': 'fixed parameterized SQLite record lookup',
                    'implementation': {'kind': kind, 'subject': subject, 'scope': scope}})
    return result[:size]


def metadata(contract):
    # Same public semantic fields in every arm; internal SQL dispatch is not a model input.
    return {key: ({name: value['semantic_type'] for name, value in contract[key].items()}
                  if key == 'input' else copy.deepcopy(contract[key]))
            for key in ('tool', 'description', 'input', 'output_bindings',
                        'evidence_support', 'does_not_establish', 'result_limit')}


def packet(request, contracts, arm, k=3):
    if arm not in ('full_catalog', 'retrieved'):
        raise ValueError('Unknown arm')
    if len({c['tool'] for c in contracts}) != len(contracts):
        raise ValueError('Duplicate tool')
    index = CatalogIndex(contracts)
    rankings = {t['id']: index.search(t['text'], min(k, len(contracts))) for t in request['tasks']}
    # Catalog appears once; per-task visible IDs encode retrieval without duplicating full metadata.
    visible = {t['id']: ([c['tool'] for c in contracts] if arm == 'full_catalog'
                         else [r['tool'] for r in rankings[t['id']]]) for t in request['tasks']}
    union = set(tool for tools in visible.values() for tool in tools)
    payload = {'request': request,
               'catalog': [metadata(c) for c in contracts if c['tool'] in union],
               'allowed_tools_per_task': visible,
               'scope': 'Synthetic selected view. No schedule/load/document-authenticity service. Supplied decomposition and bindings.'}
    messages = [{'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': canonical(payload)}]
    return {'messages': messages, 'presented_tools': visible,
            'rankings': {key: [{'tool': r['tool'], 'score': r['score']} for r in rows]
                         for key, rows in rankings.items()},
            'input_bytes': len(canonical({'messages': messages, 'tools': []}).encode()),
            'input_tokens': None, 'token_measurement': 'unmeasured until provider usage'}


def input_kind(contract):
    inputs = contract['input']
    if len(inputs) != 1:
        raise ValueError('Only one input supported')
    value = next(iter(inputs.values()))['semantic_type']
    if not value.endswith('Id'):
        raise ValueError('Unsupported semantic input')
    return value[:-2]


def checked_choices(request, decisions, contracts):
    by_tool = {c['tool']: c for c in contracts}
    result = []
    for task, decision in zip(request['tasks'], decisions):
        choice = decision['tool']
        binding = task['binding']
        rejection = None
        if choice is not None:
            if choice not in by_tool:
                rejection = 'unknown_tool'
            elif set(binding) != {'literal', 'kind'} or not isinstance(binding['literal'], str) or not binding['literal']:
                rejection = 'unsupported_binding'
            elif binding['kind'] != input_kind(by_tool[choice]):
                rejection = 'incompatible_input_kind'
        result.append({'id': task['id'], 'raw_tool': choice,
                       'tool': None if rejection else choice, 'rejection': rejection})
    return result


class RecordTools:
    """66 executable distractors, each a distinct record/subject/time predicate.

Records are synthetic supplied examples, not acquired manufacturing facts. No aliases
or duplicated descriptions are counted as new query capabilities.
"""
    def __init__(self, snapshot):
        self.snapshot = copy.deepcopy(snapshot)
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.executescript('CREATE TABLE records(id TEXT,kind TEXT,subject_id TEXT,subject_kind TEXT,valid_from TEXT,valid_until TEXT);')
        subjects = [n for n in snapshot['nodes'] if n['kind'] in ('Machine', 'Order')]
        records = []
        for kind in KINDS:
            for subject in subjects:
                for period, start, end in [('past', '2024-01-01', '2025-12-31'),
                                           ('present', '2026-01-01', '2027-12-31'),
                                           ('future', '2028-01-01', '2029-12-31')]:
                    records.append((f'{kind}:{subject["id"]}:{period}', kind, subject['id'], subject['kind'], start, end))
        self.db.executemany('INSERT INTO records VALUES(?,?,?,?,?,?)', records)
        self.source_sha256 = digest(records)
        self.entities = {n['id']: n['kind'] for n in subjects}

    def close(self):
        self.db.close()

    def run(self, contract, binding):
        spec = contract['implementation']
        if binding.get('kind') != spec['subject'] or self.entities.get(binding.get('literal')) != spec['subject']:
            raise ValueError('entity_type_not_verified')
        query = 'SELECT * FROM records WHERE kind=? AND subject_id=? AND subject_kind=?'
        params = [spec['kind'], binding['literal'], spec['subject']]
        if spec['scope'] == 'current':
            query += ' AND valid_from<=? AND valid_until>=?'
            params += [self.snapshot['as_of']] * 2
        elif spec['scope'] == 'expired':
            query += ' AND valid_until<?'
            params += [self.snapshot['as_of']]
        elif spec['scope'] != 'all':
            raise ValueError('Unknown time scope')
        query += ' ORDER BY id LIMIT 30'
        rows = [dict(r) for r in self.db.execute(query, params)]
        return {'tool': contract['tool'], 'rows': rows, 'query': query,
                'parameters': params, 'source_sha256': self.source_sha256,
                'as_of': self.snapshot['as_of'], 'limit_reached': len(rows) >= 30}
