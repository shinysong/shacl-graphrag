"""Read approved field mappings without treating an observation as permission.

This is an exact identifier lookup over a source table, not natural-language
interpretation, policy validation, or a statement of global completeness.
"""
from . import preparation as p, workspace_documents
from copy import deepcopy


def catalog(draft):
    specs,_=p.adapter_config(draft['adapter'])
    result=[]
    for table in specs:
        if table=='cases':continue
        ids=[e for e in draft['entries'] if e['kind']=='mapping' and
             e['status']=='approved' and e['target']==table+'.id']
        if len(ids)!=1:continue
        ref=ids[0]['source']
        source=next(s for s in draft['sources'] if s['name']==ref['file'])
        result.append({'table':table,'file':source['name'],'sha256':source['sha256'],
                       'identifiers':list(dict.fromkeys(r[ref['column']] for r in source['rows'] if r[ref['column']]))})
    return result


def execute(draft, selection):
    draft=p.restore_draft(draft)
    if isinstance(selection,dict) and set(selection)=={'entry_id'}:
        return workspace_documents.execute(draft,selection)
    if isinstance(selection,dict) and set(selection)=={'entry_id','value'}:
        return execute_rows(draft,selection)
    if (not isinstance(selection,dict) or set(selection)!={'table','identifier'} or
            any(not isinstance(v,str) for v in selection.values()) or
            not 1<=len(selection['identifier'])<=2000):
        raise ValueError('Select a supported table and a nonempty exact identifier')
    table=selection['table'];identifier=selection['identifier']
    selected=next((c for c in catalog(draft) if c['table']==table),None)
    if selected is None:raise ValueError('Approve exactly one identifier field for this table first')
    source=next(s for s in draft['sources'] if s['name']==selected['file'])
    specs,_=p.adapter_config(draft['adapter'])
    fields={};unresolved=[]
    for field in ('id',*specs[table]):
        entries=[e for e in draft['entries'] if e['kind']=='mapping' and
                 e['status']=='approved' and e['target']==f'{table}.{field}']
        if len(entries)!=1 or entries[0]['source']['file']!=source['name']:
            unresolved.append(field)
        else:fields[field]=entries[0]['source']['column']
    records=[]
    for number,row in enumerate(source['rows'],1):
        if row[fields['id']]!=identifier:continue
        records.append({'record':number,'values':{f:row[c] for f,c in fields.items()},
                        'source':{'file':source['name'],'sha256':source['sha256'],'record':number},
                        'columns':fields})
    status='not_found_in_source' if not records else 'ambiguous_identifier' if len(records)>1 else 'found'
    return {'mode':'source_lookup','question':f'{table}의 {identifier} 원본 기록 확인',
            'status':status,'records':records,'unreviewed_fields':unresolved,
            'metadata':draft['metadata'],'scope':selected,
            'answer':('선택한 원본에서 해당 식별자를 찾지 못했습니다. 다른 자료에 없다는 뜻은 아닙니다.' if not records else
                      '같은 식별자의 기록이 여러 개입니다. 하나를 임의로 선택하지 않았습니다.' if len(records)>1 else
                      '승인한 필드 연결에 따라 원본 기록을 확인했습니다.'),
            'notice':'원본 문자열 그대로 표시합니다. 미검토 필드는 사용하지 않았으며 정책 판단·관계 추론·SHACL 검증·LLM 호출은 수행하지 않았습니다.'}


def row_catalog(draft):
    """Approved source columns; no unique-business-identifier assumption."""
    result=[]
    sources={s['name']:s for s in draft['sources']}
    for entry in draft['entries']:
        if entry['kind']!='mapping' or entry['status']!='approved':continue
        ref=entry['source'];source=sources[ref['file']]
        result.append({'entry_id':entry['id'],'file':ref['file'],'column':ref['column'],
                       'sha256':source['sha256'],'reviewed_target':entry['target'],
                       'reviewed_interpretation':entry.get('interpretation',''),
                       'interpretation_origin':'user_review_not_source_fact'})
    return result


def execute_rows(draft,selection):
    """Exact string filter retaining every matched logical CSV record."""
    if (not isinstance(selection,dict) or set(selection)!={'entry_id','value'} or
            not isinstance(selection['entry_id'],str) or not isinstance(selection['value'],str) or
            len(selection['value'])>2000):
        raise ValueError('Choose a reviewed source column and an exact value of at most 2000 characters')
    chosen=next((c for c in row_catalog(draft) if c['entry_id']==selection['entry_id']),None)
    if chosen is None:raise ValueError('Review the source column before querying its rows')
    source=next(s for s in draft['sources'] if s['name']==chosen['file'])
    reviewed=[c for c in row_catalog(draft) if c['file']==chosen['file']]
    columns=list(dict.fromkeys(c['column'] for c in reviewed))
    records=[]
    for row,location in zip(source['rows'],source['locations']):
        if row[chosen['column']]!=selection['value']:continue
        provenance={'file':source['name'],'sha256':source['sha256'],**deepcopy(location)}
        records.append({'record':location['record'],'values':{c:row[c] for c in columns},
                        'source':provenance,'columns':{c:c for c in columns}})
    return {'mode':'source_lookup','lookup_kind':'source_rows','status':'matched_rows' if records else 'not_found_in_source',
            'question':f"{chosen['file']} · {chosen['column']} = {selection['value']} 원본 행 조회",
            'records':records,'unreviewed_fields':[c for c in source['headers'] if c not in columns],
            'metadata':deepcopy(draft['metadata']),'scope':{**chosen,'value':selection['value'],'reviewed_columns':reviewed},
            'answer':f'선택한 파일에서 조건과 일치하는 원본 행 {len(records)}개를 확인했습니다.',
            'notice':'승인한 열의 원본 문자열과 모든 일치 행을 표시합니다. 같은 값이 같은 업무 객체라는 뜻은 아닙니다. 합계·중복 제거·파일 간 연결·정책 판단은 수행하지 않았으며 선택한 파일 밖의 자료는 확인하지 않았습니다.'}
