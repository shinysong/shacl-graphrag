"""Advisory checks of model-declared contracts against frozen selected evidence.

Question interpretation and prose-to-declaration faithfulness are NOT verified.
No evaluator references, new retrieval, source repair or model calls.
"""
from scripts.post_answer_review import review as atomic_review
from scripts.postreview_mixed import direct_sources
from scripts.postreview_lookup import validate_sources, cell_value
from scripts.postreview_native_paths import review_native_paths
from scripts.postreview_extended import review_extended


def exact(obj,keys):
    if not isinstance(obj,dict) or set(obj)!=set(keys.split()):raise ValueError('declaration keys')


def nonblank(x):
    if not isinstance(x,str) or not x.strip():raise ValueError('nonempty identifier')
    return x


def nominal_operand(binding,by):
    exact(binding,'anchor_id dictionary_id value unit')
    nonblank(binding['anchor_id']);nonblank(binding['dictionary_id'])
    node=by.get(binding['dictionary_id'])
    if node is None:return None
    row=node.get('excel_row');value=cell_value(node,'C'+str(row)) if row else None
    header=next((c for r in node['header_rows'] for c in r['cells'] if c['cell']=='C2'),None)
    if value is None or not header or header.get('formula') is not None or header.get('value')!='Idc (A)':return None
    return {'source_id':binding['dictionary_id'],'value':value,'unit':'A'}


def check_one(claim,context,engine):
    exact(claim,'claim_id text kind declaration');nonblank(claim['claim_id']);nonblank(claim['text'])
    d=claim['declaration'];kind=claim['kind']
    # Context carries raw immutable source nodes; existing checkers require envelopes.
    sources=[{'source_id':nonblank(node['id']),'source':node} for node in context['sources']]
    by=validate_sources(sources)
    if kind=='recorded':
        exact(d,'source_id field value unit')
        return [atomic_review({'claims':[dict(d,claim_id=claim['claim_id'],kind='recorded')],'sources':direct_sources(sources)},engine)]
    if kind=='lookup':
        exact(d,'anchor_id dictionary_id lookup_kind value unit')
        return [review_native_paths(dict(d,claim_id=claim['claim_id']),sources,engine)]
    if kind=='difference':
        exact(d,'left right value unit')
        operands={side:nominal_operand(d[side],by) for side in ['left','right']}
        reports=[review_native_paths(dict(d[side],claim_id=claim['claim_id']+'/'+side,lookup_kind='nominal_idc'),sources,engine) for side in ['left','right']]
        reports.append(review_extended({'kind':'difference','claim':{'value':d['value'],'unit':d['unit']},'evidence':operands},engine))
        return reports
    if kind=='role':
        exact(d,'source_id role');nonblank(d['source_id'])
        # Published manual role catalog belongs to shared context, never model declaration.
        role=context.get('role_catalog',{}).get(d['source_id'])
        if d['source_id'] not in by:role=None
        return [review_extended({'kind':'role','claim':{'role':d['role']},'evidence':{'declared_role':role}},engine)]
    if kind=='selection':
        exact(d,'universe_ids lower upper target_label selected_ids count')
        if not isinstance(d['universe_ids'],list):raise ValueError('universe list')
        rows=[];bindings=[];direct={r['source_id']:r for r in direct_sources(sources)}
        for sid in d['universe_ids']:
            nonblank(sid);node=by.get(sid);field=direct.get(sid,{}).get('fields',{}).get('x_init_mm')
            if node is None or field is None or field['unit']!='mm':continue
            did=node.get('dictionary_refs',{}).get('defect');dictionary=by.get(did)
            if dictionary is None:continue
            row=dictionary.get('excel_row');label=cell_value(dictionary,'B'+str(row)) if row else None
            if label is None:continue
            # Valid source relationship is separate from numerical selection rules.
            binding=review_native_paths({'claim_id':claim['claim_id']+'/'+sid,'anchor_id':sid,'dictionary_id':did,'lookup_kind':'defect_label','value':label,'unit':None},sources,engine)
            bindings.append(binding)
            if any(r['status']!='pass' for r in binding['results']):continue
            rows.append({'id':sid,'position':field['value'],'label':label})
        return bindings+[review_extended({'kind':'selection','claim':{k:d[k] for k in ['selected_ids','count']},'evidence':{**{k:d[k] for k in ['universe_ids','lower','upper','target_label']},'rows':rows}},engine)]
    if kind=='temporal':
        exact(d,'event_date scope state selected_id latest_ids')
        h=context.get('history')
        if h is None:h={'history_complete':False,'documents':[]}
        return [review_extended({'kind':'temporal','claim':{k:d[k] for k in ['state','selected_id','latest_ids']},'evidence':{**h,'event_date':d['event_date'],'scope':d['scope']}},engine)]
    if kind=='unverified':
        exact(d,'')
        return [{'results':[{'check_id':'declared_scope','status':'not_applicable'}]}]
    raise ValueError('unsupported kind')


def review_declarations(draft,context,engine='python'):
    if engine not in ('python','pyshacl'):raise ValueError('engine')
    exact(draft,'answer claims limitations');nonblank(draft['answer'])
    if not isinstance(draft['claims'],list) or len(draft['claims'])>16:raise ValueError('claim list bound')
    if not isinstance(draft['limitations'],list) or any(not isinstance(x,str) for x in draft['limitations']):raise ValueError('limitations')
    ids=[c.get('claim_id') for c in draft['claims'] if isinstance(c,dict)]
    if len(ids)!=len(draft['claims']) or any(not isinstance(x,str) or not x.strip() for x in ids) or len(set(ids))!=len(ids):raise ValueError('claim IDs')
    records=[]
    for claim in draft['claims']:
        record={'claim_id':claim['claim_id'],'kind':claim.get('kind')}
        try:
            reports=check_one(claim,context,engine)
            record.update(state='completed',reports=reports,results=[{'component':i,**r} for i,report in enumerate(reports) for r in report['results']])
        except (ValueError,KeyError,TypeError) as e:record.update(state='input_failure',error_type=type(e).__name__,results=[])
        except Exception as e:record.update(state='execution_failure',error_type=type(e).__name__,results=[])
        records.append(record)
    return {'claims':records,'engine':engine,'answer_modified':False,'declared_claim_count':len(ids),
            'scope':'advisory declared contracts only; empty claims not whole-answer pass',
            'limits':['question interpretation/prose faithfulness unverified','source-only supplied policy and projection shared','model-declared selection universe/date/scope may be wrong and pass','role catalog manually supplied equally to all arms','native lookup checks exclude claimed unit; difference checks final unit only','no source lookup or gold repair','input/execution failures retained per declared claim']}
