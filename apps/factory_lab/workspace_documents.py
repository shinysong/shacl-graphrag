"""Read approved document paragraphs without asserting policy applicability."""
from copy import deepcopy


def catalog(draft):
    return [{'entry_id': e['id'], 'file': e['source']['file'],
             'paragraph': e['source']['paragraph'],
             'preview': e['source']['text'][:240],
             'preview_truncated': len(e['source']['text']) > 240,
             'reviewed_interpretation': e['interpretation'],
             'notice': 'Approved for reference; applicability and conflicts are not checked.'}
            for e in draft['entries'] if e['kind'] == 'policy' and e['status'] == 'approved']


def execute(draft, arguments):
    if not isinstance(arguments, dict) or set(arguments) != {'entry_id'} or not isinstance(arguments['entry_id'], str):
        raise ValueError('Document lookup requires one reviewed entry_id')
    entry = next((e for e in draft['entries'] if e['id'] == arguments['entry_id']
                  and e['kind'] == 'policy' and e['status'] == 'approved'), None)
    if entry is None:
        raise ValueError('Document paragraph is not approved in this version')
    return {'mode': 'source_document', 'metadata': deepcopy(draft['metadata']),
            'entry_id': entry['id'], 'source': deepcopy(entry['source']),
            'review': {'interpretation': entry['interpretation'], 'target': entry['target'],
                       'temporal': deepcopy(entry.get('temporal', [])),
                       'origin': 'user_review_not_source_fact'},
            'unchecked': ['applicability_to_question', 'conflicting_or_other_paragraphs',
                          'policy_calculation', 'external_truth', 'source_completeness'],
            'notice': 'Selected original paragraph only. Approval is not proof of current applicability, precedence or completeness. No policy calculation or SHACL check was executed.'}
