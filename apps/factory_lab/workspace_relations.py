"""Explicit one-hop exact-value comparison of reviewed CSV endpoints.

Available as a direct selection and a fixed question tool. Execution requires
approved endpoints and an approved relationship with a human interpretation.
Model-selected arguments are interpretations, not confirmed user intent. No inferred identity, cardinality, transitive join or business action.
"""
from copy import deepcopy
from . import preparation as p
from .workspace_lookup import row_catalog, execute_rows


def catalog(draft):
    columns = row_catalog(draft)
    result = []
    for entry in draft['entries']:
        if entry['kind'] != 'relation' or entry['status'] != 'approved':
            continue
        if not entry.get('interpretation', '').strip():
            continue
        endpoints = []
        for ref in (entry['source'], entry['target']):
            matches = [c for c in columns if c['file'] == ref['file']
                       and c['column'] == ref['column'] and c['sha256'] == ref['sha256']]
            if len(matches) != 1:
                break
            endpoints.append(matches[0])
        if len(endpoints) == 2 and endpoints[0]['file'] != endpoints[1]['file']:
            result.append({'relation_id': entry['id'], 'source': endpoints[0],
                           'target': endpoints[1], 'reviewed_interpretation': entry['interpretation'],
                           'interpretation_origin': 'user_review_not_source_fact'})
    return result


def execute(draft, selection):
    draft = p.restore_draft(draft)
    if (not isinstance(selection, dict) or set(selection) != {'relation_id', 'value'}
            or not isinstance(selection['relation_id'], str)
            or not isinstance(selection['value'], str)
            or not selection['value'].strip() or len(selection['value']) > 2000):
        raise ValueError('Select a reviewed relation and a nonblank exact string')
    relation = next((r for r in catalog(draft) if r['relation_id'] == selection['relation_id']), None)
    if relation is None:
        raise ValueError('Both endpoints and the described relation must be approved in this version')
    sides = {side: execute_rows(draft, {'entry_id': relation[side]['entry_id'],
                                       'value': selection['value']}) for side in ('source', 'target')}
    counts = {side: len(result['records']) for side, result in sides.items()}
    return {'mode': 'reviewed_relation_rows', 'metadata': deepcopy(draft['metadata']),
            'draft_digest': p.digest(draft), 'relation': relation, 'value': selection['value'],
            'sides': sides, 'record_counts': counts,
            'matching_pair_count': counts['source'] * counts['target'],
            'status': 'matched' if all(counts.values()) else 'missing_on_selected_side',
            'unchecked': ['business_identity', 'relationship_truth', 'cardinality_contract',
                          'other_values_or_files', 'transitive_relations', 'policy_applicability'],
            'notice': 'Exact nonblank string comparison in two explicitly selected reviewed columns. All matching raw records retained; no deduplication, aggregate, pair expansion, semantic identity inference or policy validation.'}
