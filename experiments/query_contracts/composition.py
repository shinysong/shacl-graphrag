"""Model-authored decomposition/DAG and evidence-grounded final answers.

No evaluator imports. Whole-question obligations and bindings are produced by the
model, never supplied by runtime fixtures. Typed checks do not certify user intent.
"""
import copy
import json
import re
from .core import CatalogIndex, BINDINGS, validate_plan, _value
from .catalog_scale import metadata, canonical

POLICY = '''Synthetic selected factory view only; source completeness is unknown. A qualification applies only if ONE record matches order product, required capability, and snapshot date. Never combine different records to manufacture applicability. Current date validity alone does not imply order applicability. No machine load, scheduling, delivery-feasibility or document-authenticity service exists. No physical approval or physical-process prescriptions. Empty selected results are not global source absence. Expose unresolved parts and distinguish evidence from inference. Never invent IDs, query text or facts.'''


def response_json(message):
    """Decode one optional whole-response JSON code fence; never repair JSON content."""
    text=message['content']
    if not isinstance(text,str):raise ValueError('response_content_not_string')
    match=re.fullmatch(r'\s*```(?:json)?[ \t]*\n(.*)\n```\s*',text,flags=re.S)
    return json.loads(match.group(1) if match else text)


def decomposition_messages(question, schema):
    return [{'role':'system','content':POLICY+'''\nRead the original compound user request and enumerate each distinct information need, including unsupported needs. Do NOT answer it or select tools. Return only JSON {"requirements":[{"id":"r1","text":"faithful description"}]}, 1..8 entries. IDs must be unique. This decomposition is your interpretation, not verified completeness.'''},
            {'role':'user','content':canonical({'question':question,'schema':schema})}]


def parse_decomposition(message):
    obj=response_json(message)
    if not isinstance(obj,dict) or set(obj)!={'requirements'} or not isinstance(obj['requirements'],list) or not 1<=len(obj['requirements'])<=8:
        raise ValueError('decomposition_schema')
    seen=set()
    for req in obj['requirements']:
        if not isinstance(req,dict) or set(req)!={'id','text'} or not isinstance(req['id'],str) or not 1<=len(req['id'])<=40 or req['id'] in seen or not isinstance(req['text'],str) or not 1<=len(req['text'])<=1200:
            raise ValueError('decomposition_requirement_schema')
        seen.add(req['id'])
    return obj['requirements']


def planning_packet(question, requirements, schema, catalog, arm):
    if arm not in ('full','retrieved'):
        raise ValueError('unknown_arm')
    index=CatalogIndex(catalog)
    ranks={r['id']:index.search(r['text'],3) for r in requirements}
    names={c['tool'] for c in catalog} if arm=='full' else {entry['tool'] for ranked in ranks.values() for entry in ranked}
    selected=[metadata(c) for c in catalog if c['tool'] in names]
    system=POLICY+'''\nCreate an ordered query DAG to address the interpreted requirements. You choose tools AND all literal or previous-step output bindings. Multiple steps may serve one requirement. A binding is either {"literal":"entity ID","kind":"Machine or Order"} or {"step":"earlier step ID","path":"declared output path without rows[] prefix"}. Use order.id or machine.id paths as appropriate. Fixed tools only, no arbitrary query. Output paths refer to rows, preserving order context on each branch. Do not place SQL/SPARQL in the plan. Leave unsupported requirements unplanned; do not substitute vaguely related tools. Return only JSON {"steps":[{"id":"s1","obligation":"requirement ID","tool":"tool ID","binding":{...}}],"unplanned":[{"id":"requirement ID","reason":"why unplanned"}]}. At most 8 steps; empty steps is permitted. Preserve declared requirements even if no tool can serve them. The executor can fan out bindings over prior rows; maximum 12 actual query attempts. You have not yet seen query results.'''
    payload={'question':question,'requirements':requirements,'schema':schema,'catalog':selected,
             'scope':'Same full contract fields on all visible tools. No externally supplied step plan or bindings.'}
    return {'messages':[{'role':'system','content':system},{'role':'user','content':canonical(payload)}],
            'catalog':selected,'visible_tools':sorted(names),
            'rankings':{k:[{'tool':r['tool'],'score':r['score']} for r in v] for k,v in ranks.items()}}


def parse_plan(message, requirements):
    obj=response_json(message)
    if not isinstance(obj,dict) or set(obj)!={'steps','unplanned'} or not isinstance(obj['steps'],list) or len(obj['steps'])>8 or not isinstance(obj['unplanned'],list) or len(obj['unplanned'])>8:
        raise ValueError('plan_schema')
    seen=set()
    for s in obj['steps']:
        if not isinstance(s,dict) or set(s)!={'id','obligation','tool','binding'} or not all(isinstance(s[k],str) and 0<len(s[k])<=100 for k in ('id','obligation','tool')) or s['id'] in seen:
            raise ValueError('step_schema')
        b=s['binding']
        if not isinstance(b,dict) or set(b) not in ({'literal','kind'},{'step','path'}) or not all(isinstance(v,str) and 0<len(v)<=100 for v in b.values()):
            raise ValueError('binding_schema')
        seen.add(s['id'])
    for u in obj['unplanned']:
        if not isinstance(u,dict) or set(u)!={'id','reason'} or not all(isinstance(v,str) for v in u.values()):
            raise ValueError('unplanned_schema')
    return {'obligations':{r['id']:r['text'] for r in requirements},'steps':obj['steps'],
            'model_unplanned':obj['unplanned']}


def checked_plan(plan, visible):
    accepted=[];rejected=[]
    for step in plan['steps']:
        candidate={'obligations':plan['obligations'],'steps':accepted+[step]}
        try:
            if step['tool'] not in visible:
                raise ValueError('tool_not_in_presented_catalog')
            validate_plan(candidate)
            accepted.append(copy.deepcopy(step))
        except ValueError as exc:
            rejected.append({'step':copy.deepcopy(step),'reason':str(exc)})
    return dict(plan,steps=accepted),rejected


def execute_plan(plan, tools, visible, max_calls=12):
    """Same per-step handling in every condition; raw plans can fail, never repair.

Source/type/binding/row checks are shared execution safety in A/B/C, not C-only
semantic knowledge. Wrong interpreted requirements remain wrong runtime outcomes.
"""
    snapshot,source=tools.views.snapshot('factory-v3');anchor=('factory-v3',source,snapshot['as_of'])
    entities={n['id']:n['kind'] for n in snapshot['nodes']}
    calls=[];outputs={};states={}
    for step in plan['steps']:
        sid=step['id'];errors=[];requests=[];rows_out=[];limited=False
        tool=step['tool'];binding=step['binding']
        if tool not in visible or tool not in BINDINGS:
            errors.append('tool_not_in_presented_catalog')
        elif step['obligation'] not in plan['obligations']:
            errors.append('undeclared_requirement')
        elif 'literal' in binding:
            requests=[(binding['literal'],{},[],False)]
            if binding['kind']!=BINDINGS[tool][1]:
                errors.append('incompatible_literal');requests=[]
        elif binding['step'] not in outputs:
            errors.append('forward_or_missing_dependency')
        else:
            upstream=states[binding['step']]
            limited=upstream['limited']
            if upstream['issues']:
                errors.append('upstream_unresolved')
            for row in outputs[binding['step']]:
                try:requests.append((_value(row['row'],binding['path']),row['context'],row['lineage'],row['limited']))
                except ValueError:errors.append('missing_output_binding')
            if not requests:errors.append('no_upstream_rows')
        for value,context,lineage,upstream_limited in requests:
            argument,kind,_=BINDINGS[tool]
            if not isinstance(value,str):
                errors.append('non_scalar_output_binding');continue
            if entities.get(value)!=kind:
                errors.append('entity_type_not_verified');continue
            if len(calls)>=max_calls:
                errors.append('call_budget_exhausted');continue
            eid='E'+str(len(calls)+1)
            call={'id':eid,'step':sid,'tool':tool,'arguments':{argument:value},'context':copy.deepcopy(context),'input_lineage':list(lineage)}
            calls.append(call)
            try:
                result=tools.run('factory-v3',tool,{argument:value});call['result']=result
                if (result['snapshot'],result['source_sha256'],result['as_of'])!=anchor or result['arguments']!={argument:value} or result['tool']!=tool:
                    raise ValueError('source_or_argument_binding_mismatch')
                if not isinstance(result.get('rows'),list) or type(result.get('limit_reached')) is not bool:
                    raise ValueError('invalid_result')
                batch=[]
                for row in result['rows']:
                    if _value(row,'order.id' if argument=='order_id' else 'machine.id')!=value:
                        raise ValueError('response_entity_mismatch')
                    ctx=copy.deepcopy(context)
                    if 'order' in row:
                        current={'id':row['order']['id'],'product':row['order'].get('product'),
                                 'required_capability':row.get('required_capability')}
                        if 'order' in ctx and ctx['order']!=current:
                            raise ValueError('order_context_mismatch')
                        ctx['order']=current
                    batch.append({'row':row,'context':ctx,'lineage':lineage+[eid],
                                  'limited':upstream_limited or result['limit_reached']})
                rows_out.extend(batch);limited|=result['limit_reached'];call['status']='completed'
            except Exception as exc:
                call.update(status='failed',error=str(exc));errors.append(str(exc))
        outputs[sid]=rows_out
        states[sid]={'obligation':step['obligation'],'issues':sorted(set(errors)),
                     'limited':limited,'row_count':len(rows_out)}
    return {'snapshot':list(anchor),'calls':calls,'outputs':outputs,'steps':states,
            'source_completeness':'unknown','source_absence_inference':'not_permitted'}


def report(plan, execution, rejected):
    requirements={}
    for rid,text in plan['obligations'].items():
        steps=[s['id'] for s in plan['steps'] if s['obligation']==rid]
        issues=sorted({v for sid in steps for v in execution['steps'].get(sid,{}).get('issues',[])})
        blocked=[r for r in rejected if r['step']['obligation']==rid]
        requirements[rid]={'text':text,'planned_steps':steps,'blocked_steps':blocked,'issues':issues,
                           'status':'not_planned' if not steps else ('retrieval_partial' if issues or any(execution['steps'][sid]['limited'] for sid in steps) else 'retrieval_executed'),
                           'semantic_satisfaction':'unverified_even_if_rows_returned'}
    return {'requirements':requirements,'rejected_connections':rejected,
            'scope':'Only model-declared requirements are tracked; undeclared original requirements can be missed. No truth/completeness/qualification verdict. No extra source lookup.'}


def evidence_payload(execution):
    # SQL text is retained in raw execution but omitted from all final prompts equally.
    return {'snapshot':execution['snapshot'],'calls':[
        {k:v for k,v in c.items() if k!='result'} | ({'result':{k:v for k,v in c['result'].items() if k in ('rows','snapshot','source_sha256','as_of','limit_reached','scope')}} if 'result' in c else {})
        for c in execution['calls']],
        'steps':execution['steps'],
        'source_completeness':'unknown'}


def final_messages(question, requirements, plan, execution, catalog, schema, review=None):
    system=POLICY+'''\nAnswer the ORIGINAL user request in Korean using only provided query evidence. Be concise: answer at most 1800 characters, each coverage explanation at most 160 characters. For every model-declared requirement, return coverage with its actual answer status, evidence IDs and unresolved explanation. A query executed or rows returned does NOT mean that a requirement is answered. If you omitted an original requirement during decomposition, acknowledge it when noticed. Explain order-specific applicability with a single matching record, preserve candidate/order provenance, and identify unverified schedule/authenticity/physical approval. No source lookup or new tool call is available. Review data, if supplied, is fallible procedural feedback, not a compulsory veto or truth oracle. Return only JSON {"answer":"natural language answer with evidence references", "coverage":[{"id":"declared requirement ID","status":"answered|partial|unresolved","evidence":["E1"],"explanation":"what is answered or missing"}], "additional_unresolved":["original requirement not captured, if any"]}. Never claim unsupported certainty just because a check passed.'''
    payload={'question':question,'requirements':requirements,'plan':plan,'schema':schema,
             'catalog':catalog,'evidence':evidence_payload(execution)}
    if review is not None:payload['procedural_review']=review
    return [{'role':'system','content':system},{'role':'user','content':canonical(payload)}]


def parse_answer(message, requirements, execution):
    obj=response_json(message)
    if not isinstance(obj,dict) or set(obj)!={'answer','coverage','additional_unresolved'} or not isinstance(obj['answer'],str) or len(obj['answer'])>14000 or not isinstance(obj['coverage'],list) or not isinstance(obj['additional_unresolved'],list) or not all(isinstance(x,str) for x in obj['additional_unresolved']):
        raise ValueError('final_schema')
    if [x.get('id') for x in obj['coverage'] if isinstance(x,dict)]!=[r['id'] for r in requirements]:
        raise ValueError('final_coverage_missing_or_reordered')
    known={c['id'] for c in execution['calls']}
    for entry in obj['coverage']:
        if set(entry)!={'id','status','evidence','explanation'} or entry['status'] not in ('answered','partial','unresolved') or not isinstance(entry['explanation'],str) or not isinstance(entry['evidence'],list):
            raise ValueError('final_coverage_schema')
    # Citation errors are outcomes, never oracle rejection/repair.
    obj['citation_reference_errors']=[{'id':x['id'],'evidence':e} for x in obj['coverage'] for e in x['evidence'] if not isinstance(e,str) or e not in known]
    return obj
