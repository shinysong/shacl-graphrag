"""Lossless selected-source representation for shared model inputs.

Only repeated worksheet metadata and cell keys are factored out. No source field,
formula, cached value, missing key or null is silently removed. Not tokenization.
"""
import copy
import json

FIELDS=('archive_path','sha256','sheet','header_rows')


def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def pack_sources(sources):
    if not isinstance(sources,list) or any(not isinstance(n,dict) for n in sources):
        raise ValueError('source object list required')
    templates=[];index={};records=[]
    for node in sources:
        template={k:copy.deepcopy(node[k]) for k in FIELDS if k in node}
        key=canonical(template)
        if key not in index:index[key]=len(templates);templates.append(template)
        rest={k:copy.deepcopy(v) for k,v in node.items() if k not in FIELDS}
        cells=rest.pop('cells',None);has_cells='cells' in node
        table=None
        if has_cells:
            if not isinstance(cells,list) or any(not isinstance(c,dict) for c in cells):raise ValueError('cells must be object list')
            columns=sorted({k for c in cells for k in c})
            # Presence mask preserves absent keys separately from explicit nulls.
            table={'columns':columns,'rows':[[c.get(k) for k in columns] for c in cells],
                   'present':[[k in c for k in columns] for c in cells]}
        records.append({'worksheet_template':index[key],'record':rest,'cell_table':table})
    return {'format':'selected-source-lossless-v1','worksheet_templates':templates,'records':records}


def unpack_sources(packed):
    if packed.get('format')!='selected-source-lossless-v1':raise ValueError('format')
    result=[]
    for entry in packed['records']:
        i=entry['worksheet_template']
        if type(i) is not int or not 0<=i<len(packed['worksheet_templates']):raise ValueError('template reference')
        template=packed['worksheet_templates'][i];record=entry['record']
        if set(template)&set(record):raise ValueError('duplicate template/record key')
        node=copy.deepcopy(template);node.update(copy.deepcopy(record))
        table=entry['cell_table']
        if table is not None:
            if 'cells' in node:raise ValueError('duplicate cells')
            cols=table['columns'];rows=table['rows'];present=table['present']
            if any(not isinstance(k,str) for k in cols) or len(set(cols))!=len(cols) or len(rows)!=len(present):raise ValueError('cell table')
            node['cells']=[]
            for row,mask in zip(rows,present):
                if len(row)!=len(cols) or len(mask)!=len(cols) or any(type(x) is not bool for x in mask):raise ValueError('cell row')
                node['cells'].append({k:copy.deepcopy(v) for k,v,exists in zip(cols,row,mask) if exists})
        result.append(node)
    return result
