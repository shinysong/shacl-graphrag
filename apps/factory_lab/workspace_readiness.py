"""Read-only preparation guidance, never an execution authorization."""
from . import preparation as p, workspace_lookup, workspace_documents, workspace_relations, workspace_stock
from . import workspace_policy, policy_agreement


def describe(draft):
    capabilities = {
        'source_rows': len(workspace_lookup.row_catalog(draft)),
        'source_document': len(workspace_documents.catalog(draft)),
        'relation_rows': len(workspace_relations.catalog(draft)),
        'stock_check': int(workspace_stock.catalog(draft) is not None),
    }
    report = {'capabilities': capabilities, 'replacement': None,
              'notice': 'Preparation guidance only. Values, references, selected arguments and policy eligibility remain checked at execution.'}
    if draft['adapter'] != p.ADAPTER:
        return report
    specs, policies = p.adapter_config(draft['adapter'])
    issues = []
    def issue(code, subject, entries=()):
        issues.append({'code': code, 'subject': subject, 'entry_ids': list(entries)})
    if draft['metadata'].get('currency') != 'KRW':
        issue('currency', draft['metadata'].get('currency', ''))
    pending = [e['id'] for e in draft['entries'] if e['status'] not in ('approved', 'excluded')]
    if pending:
        issue('pending', 'entries', pending)
    approved = [e for e in draft['entries'] if e['status'] == 'approved']
    for target in policies:
        matches = [e for e in approved if e['kind'] == 'policy' and e['target'] == target]
        if not matches:
            issue('policy_missing', target)
        elif len(matches) > 1:
            issue('policy_multiple', target, (e['id'] for e in matches))
    for table, fields in specs.items():
        if table == 'cases':
            continue  # Interactive intent supplies this collection, not uploaded data.
        files = set()
        for field in ('id', *fields):
            target = table + '.' + field
            matches = [e for e in approved if e['kind'] == 'mapping' and e['target'] == target]
            if len(matches) != 1:
                issue('field_missing' if not matches else 'field_multiple', target, (e['id'] for e in matches))
            else:
                files.add(matches[0]['source']['file'])
        if len(files) > 1:
            issue('collection_split', table)
    # Existing guards remain authoritative; each returns its first error only.
    for code, check in (('policy_scope', workspace_policy.require_unambiguous),
                        ('policy_agreement', policy_agreement.require_confirmed)):
        try:
            check(draft)
        except ValueError as exc:
            issue(code, str(exc))
    report['replacement'] = {'state': 'needs_review' if issues else 'execution_checks_remaining',
                             'issues': issues,
                             'unchecked': ['source value types', 'duplicate identifiers', 'references',
                                           'chosen proposal', 'external truth', 'source completeness']}
    return report
