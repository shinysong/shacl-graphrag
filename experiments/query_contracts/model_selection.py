"""Model-selection packets and deterministic post-selection checks, no API client."""
import copy
import json
from .core import BINDINGS, CatalogIndex, validate_plan

SYSTEM = '''Select reusable fixed queries for the supplied compound question. The task decomposition and bindings are supplied interpretations, not verified truth. Select one presented tool per task, or null if no presented tool supplies the required evidence. Do not substitute a vaguely related query for a missing service. Consider temporal scope and what the contract does NOT establish. Query execution is not answer truth or completeness. No physical approval. Do not invent tools or alter bindings. Return only JSON {"decisions":[{"id":"task id","tool":"presented tool or null","reason":"brief public selection explanation"}]}, exactly once for every task in original order. No final business answer or arbitrary SQL/SPARQL.'''


def packet(request,catalog,arm):
    if arm not in ('full_catalog','retrieved'):raise ValueError('Unknown arm')
    index=CatalogIndex(catalog); presented={}; ranks={}
    for task in request['tasks']:
        ranked=index.search(task['text'],3)
        ranks[task['id']]=[{'tool':r['tool'],'score':r['score']} for r in ranked]
        presented[task['id']]=copy.deepcopy(catalog) if arm=='full_catalog' else [r['contract'] for r in ranked]
    content={'request':request,'catalog_per_task':presented,'scope':'Synthetic selected view, no schedule/load/document-authenticity service. Do not assume all tasks are answerable.'}
    messages=[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(content,ensure_ascii=False,separators=(',',':'))}]
    return {'messages':messages,'presented_tools':{k:[c['tool'] for c in v] for k,v in presented.items()},'rankings':ranks}


def parse(request,prepared,message):
    body=json.loads(message['content'])
    if not isinstance(body,dict) or set(body)!={'decisions'} or not isinstance(body['decisions'],list):raise ValueError('response_schema')
    items=body['decisions']
    if [x.get('id') for x in items if isinstance(x,dict)]!=[t['id'] for t in request['tasks']]:raise ValueError('missing_duplicate_or_reordered_tasks')
    for item in items:
        if set(item)!={'id','tool','reason'} or not isinstance(item['reason'],str) or len(item['reason'])>600:raise ValueError('response_schema')
        if item['tool'] is not None and item['tool'] not in prepared['presented_tools'][item['id']]:raise ValueError('selection_outside_presented_catalog')
    return items


def plans(request,decisions):
    raw=[]; checked=[]; rejected=[]
    for task,item in zip(request['tasks'],decisions):
        if item['tool'] is None:continue
        step={'id':task['id'],'obligation':task['id'],'tool':item['tool'],'binding':copy.deepcopy(task['binding'])}
        raw.append(step)
        candidate={'obligations':{t['id']:t['text'] for t in request['tasks']},'steps':checked+[step]}
        try:validate_plan(candidate);checked.append(step)
        except ValueError as exc:rejected.append({'id':task['id'],'tool':item['tool'],'error':str(exc)})
    common={'obligations':{t['id']:t['text'] for t in request['tasks']}}
    return {'raw':dict(common,steps=raw),'checked':dict(common,steps=checked),'rejections':rejected,
            'check_scope':'Input/output/dependency compatibility only, not semantic intent or answer validation'}
