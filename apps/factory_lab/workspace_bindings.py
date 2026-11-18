"""Bounded exact-value dependencies between fixed question tools.

No query generation, arbitrary paths, first-row choice or semantic identity test.
"""
from copy import deepcopy


class BindingError(ValueError):
    pass


def resolve(tool, arguments, evidence):
    args=deepcopy(arguments)
    if tool not in ('source_rows','relation_rows') or not isinstance(args.get('value'),dict):
        return args,None
    ref=args['value']
    if set(ref)!={'from_evidence','column'} or not all(isinstance(v,str) and 1<=len(v)<=1024 for v in ref.values()):
        raise BindingError('Invalid evidence binding; select an earlier source_rows evidence and column')
    prior=next((e for e in evidence if e['id']==ref['from_evidence']),None)
    if prior is None or prior.get('state')!='completed' or prior.get('tool')!='source_rows':
        raise BindingError('Binding requires a successful earlier source_rows result')
    result=prior.get('result',{})
    if result.get('lookup_kind')!='source_rows':raise BindingError('Binding source is not raw source rows')
    records=result.get('records',[])
    if not records:raise BindingError('Binding source has no matching records')
    values=[]
    for record in records:
        value=record.get('values',{}).get(ref['column'])
        if not isinstance(value,str) or not value.strip() or len(value)>2000:
            raise BindingError('Binding column is unavailable, blank or exceeds the value limit')
        values.append(value)
    if len(set(values))!=1:raise BindingError('Binding source contains multiple distinct values; no row was selected')
    args['value']=values[0]
    return args,{'from_evidence':prior['id'],'column':ref['column'],'value':values[0],
                 'records':[deepcopy(r['source']) for r in records],
                 'notice':'One distinct exact value across all returned rows; not unique entity or relationship verification.'}
