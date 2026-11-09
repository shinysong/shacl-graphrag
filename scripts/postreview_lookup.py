"""Advisory declared-lookup trace review over supplied worksheet snapshots.

Compiles source-backed comparisons into the reviewed atomic checker. The compiler
is SHARED by both engines; this is not an independent semantic implementation.
No natural-language interpretation, retrieval, gold or answer rewriting.
"""
from scripts.post_answer_review import review, token

POLICIES={
 'defect_label':{'selector':'defect','column':'B','header_cell':'B1','header':'Defect','unit':None},
 'nominal_idc':{'selector':'welding_setting','column':'C','header_cell':'C2','header':'Idc (A)','unit':'A'},
}

def validate_sources(sources):
    if not isinstance(sources, list):
        raise ValueError('source list')
    by = {}

    def validate_cells(cells):
        if not isinstance(cells, list):
            raise ValueError('cell list')
        addresses = set()
        for cell in cells:
            if not isinstance(cell, dict) or 'value' not in cell:
                raise ValueError('cell shape')
            address = cell.get('cell')
            if not isinstance(address, str) or not address or address in addresses:
                raise ValueError('cell address or duplicate')
            addresses.add(address)
            token(cell['value'])
            if cell.get('formula') is not None and not isinstance(cell['formula'], str):
                raise ValueError('formula shape')
        return addresses

    for item in sources:
        if not isinstance(item, dict) or set(item) != {'source_id', 'source'}:
            raise ValueError('source envelope')
        sid, source = item['source_id'], item['source']
        if not isinstance(sid, str) or not sid or sid in by:
            raise ValueError('source ID')
        required = ('archive_path', 'sheet', 'sha256', 'cells', 'header_rows')
        if not isinstance(source, dict) or not all(k in source for k in required):
            raise ValueError('source fields')
        if not all(isinstance(source[k], str) and source[k] for k in required[:3]):
            raise ValueError('source provenance')
        validate_cells(source['cells'])
        if not isinstance(source['header_rows'], list):
            raise ValueError('header rows')
        header_addresses = set()
        for row in source['header_rows']:
            if not isinstance(row, dict) or 'cells' not in row:
                raise ValueError('header row shape')
            addresses = validate_cells(row['cells'])
            if addresses & header_addresses:
                raise ValueError('duplicate header address')
            header_addresses.update(addresses)
        for key in ('dictionary_refs', 'field_cells'):
            if key in source:
                mapping = source[key]
                if not isinstance(mapping, dict) or any(
                    not isinstance(k, str) or not k or
                    (v is not None and (not isinstance(v, str) or not v))
                    for k, v in mapping.items()
                ):
                    raise ValueError('source mapping')
        row = source.get('excel_row')
        if row is not None and (type(row) is not int or row < 1):
            raise ValueError('source row')
        by[sid] = source
    return by

def cell_value(source,address):
    found=[c for c in source['cells'] if c['cell']==address]
    if not found or found[0].get('formula') is not None:return None
    token(found[0]['value'])
    return found[0]['value']

def compile_trace(claim,sources):
    if not isinstance(claim,dict) or set(claim)!={'claim_id','lookup_kind','anchor_id','dictionary_id','value','unit'}:raise ValueError('claim shape')
    for k in ('claim_id','lookup_kind','anchor_id','dictionary_id'):
        if not isinstance(claim[k],str) or not claim[k]:raise ValueError('claim binding')
    if claim['lookup_kind'] not in POLICIES:raise ValueError('unsupported lookup kind')
    token(claim['value'])
    if claim['unit'] is not None and not isinstance(claim['unit'],str):raise ValueError('unit')
    policy=POLICIES[claim['lookup_kind']];by=validate_sources(sources);anchor=by.get(claim['anchor_id']);target=by.get(claim['dictionary_id'])
    comparisons=[]
    def add(rule,observed,expected,locator,missing=False):
        comparisons.append({'rule':rule,'observed':observed,'expected':expected,'locator':locator,
                            'missing':missing or observed is None or expected is None})
    field=policy['selector'];ref=anchor.get('dictionary_refs',{}).get(field) if anchor else None
    add('declared_reference',claim['dictionary_id'],ref,f"{claim['anchor_id']} / dictionary_refs.{field}",anchor is None)
    address=anchor.get('field_cells',{}).get(field) if anchor else None
    value=cell_value(anchor,address) if anchor and address else None
    row=target.get('excel_row') if target else None
    if row is not None and (type(row) is not int or row<1):raise ValueError('dictionary row')
    key=cell_value(target,'A'+str(row)) if target and row else None
    add('dictionary_key',value,key,f"{claim['anchor_id']} / {address}; {claim['dictionary_id']} / A{row}",anchor is None or target is None)
    actual=cell_value(target,policy['column']+str(row)) if target and row else None
    add('lookup_value',claim['value'],actual,f"{claim['dictionary_id']} / {policy['column']}{row}",target is None)
    # Same workbook is a declared namespace policy, not content deduplication.
    add('workbook_hash',anchor.get('sha256') if anchor else None,target.get('sha256') if target else None,
        f"{claim['anchor_id']} / sha256; {claim['dictionary_id']} / sha256",anchor is None or target is None)
    add('workbook_path',anchor.get('archive_path') if anchor else None,target.get('archive_path') if target else None,
        f"{claim['anchor_id']} / archive_path; {claim['dictionary_id']} / archive_path",anchor is None or target is None)
    headers=[c for h in target.get('header_rows',[]) for c in h.get('cells',[]) if c.get('cell')==policy['header_cell']] if target else []
    if len(headers)>1:raise ValueError('duplicate header address')
    header=headers[0].get('value') if headers and headers[0].get('formula') is None else None
    add('declared_header',header,policy['header'],f"{claim['dictionary_id']} / header {policy['header_cell']}",target is None)
    if policy['unit'] is not None:
        # Unit policy is applicable only when the supplied header matches it.
        add('declared_unit',claim['unit'],policy['unit'],f"{claim['dictionary_id']} / header {policy['header_cell']}",header!=policy['header'])
    packet={'claims':[],'sources':[]}
    for i,c in enumerate(comparisons):
        cid=claim['claim_id']+'/'+c['rule'];sid='compiled-comparison/'+str(i)
        packet['claims'].append({'claim_id':cid,'kind':'recorded','source_id':sid,'field':'source_comparison','value':c['observed'],'unit':None})
        packet['sources'].append({'source_id':sid,'fields':{'source_comparison':{'value':None if c['missing'] else c['expected'],'unit':None,'locator':c['locator']}}})
    return packet,comparisons

def review_lookup(claim,sources,engine='python'):
    packet,comparisons=compile_trace(claim,sources);raw=review(packet,engine)
    statuses={r['claim_id']:r['status'] for r in raw['results'] if r['check_id']=='value_agreement'}
    results=[{'check_id':c['rule'],'status':statuses[claim['claim_id']+'/'+c['rule']],
              'observed':c['observed'],'selected_or_declared_reference':c['expected'],
              'locator':c['locator'],'basis':'selected source cells/references and explicit typed lookup policy'} for c in comparisons]
    return {'engine':engine,'claim_id':claim['claim_id'],'results':results,'answer_modified':False,
            'compiler_shared':True,'raw_atomic_report':raw,'compiled_packet':packet,
            'scope':'Declared lookup trace only; not question interpretation, external truth or physical applicability.'}
