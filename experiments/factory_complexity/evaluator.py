"""Offline source-side references. NEVER imported by the runtime tools/agent."""
from datetime import date


def decisions(source):
    nodes={n['id']:n for n in source['nodes']}
    edges=source['edges'];at=date.fromisoformat(source['as_of'])
    impact={};candidates={}
    for order in (n for n in source['nodes'] if n['kind']=='Order'):
        for a,relation,b in edges:
            if a==order['id'] and relation=='ASSIGNED_TO':impact.setdefault(b,[]).append(order['id'])
        required={b for a,r,b in edges if a==order['id'] and r=='REQUIRES'}
        for machine in (n for n in source['nodes'] if n['kind']=='Machine'):
            capabilities={b for a,r,b in edges if a==machine['id'] and r=='CAPABLE_OF'}
            for cap in sorted(required & capabilities):
                records=[nodes[b] for a,r,b in edges if a==machine['id'] and r=='HAS_QUALIFICATION']
                applicable=[]
                for record in records:
                    try:valid=date.fromisoformat(record['valid_from'])<=at<=date.fromisoformat(record['valid_until'])
                    except (KeyError,ValueError):valid=False
                    if valid and record.get('product')==order['product'] and record.get('capability')==cap:applicable.append(record['id'])
                key='|'.join((order['id'],machine['id'],cap))
                candidates[key]={'status_available':machine.get('status')=='available',
                    'record_ids':sorted(r['id'] for r in records),'applicable_record_ids':sorted(applicable),
                    'eligible_within_policy':machine.get('status')=='available' and bool(applicable)}
    return {'impact':{m:sorted(set(orders)) for m,orders in sorted(impact.items())},'candidates':dict(sorted(candidates.items()))}


def expected_selected_flags(source):
    """Independent dates/joins reference; only use on selected-view census evidence."""
    flags=[]
    for key,candidate in decisions(source)['candidates'].items():
        if key.split('|')[0] not in ('O17','O18'):continue
        if not candidate['status_available']:flags.append({'candidate':key,'code':'status-not-available'})
        if not candidate['record_ids']:flags.append({'candidate':key,'code':'qualification-not-retrieved'})
        elif not candidate['applicable_record_ids']:flags.append({'candidate':key,'code':'qualification-not-applicable'})
    return sorted(flags,key=lambda row:(row['candidate'],row['code']))
