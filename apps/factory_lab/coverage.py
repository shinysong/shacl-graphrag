"""Versioned, evidence-only target projection. Declarations are not verified intent."""
import json
from datetime import date
from .review import python_flags, shacl_flags, POLICY

CONTRACT = 'factory-review-coverage-v1'
TOOL_NAME = 'declare_review_targets'
TOOL = {'type': 'function', 'function': {'name': TOOL_NAME,
    'description': 'Declare order/machine pairs you intend to assess before the draft, even when using inspect_entity instead of replacement_candidates. This is NOT a graph query or evidence. Quote original user text exactly for attribution; pair selection may still be wrong. Calls accumulate; never declare physical approval. Other question dimensions remain outside this checker.',
    'parameters': {'type': 'object', 'properties': {'targets': {'type': 'array', 'maxItems': 24,
        'items': {'type': 'object', 'properties': {k: {'type': 'string'} for k in ('order_id','machine_id','quote')},
                 'required': ['order_id','machine_id','quote'], 'additionalProperties': False}}},
        'required': ['targets'], 'additionalProperties': False}}}


def declarations(args, turns):
    if not isinstance(args, dict) or set(args) != {'targets'} or not isinstance(args['targets'], list) or len(args['targets']) > 24:
        raise ValueError('Invalid target declaration')
    for t in args['targets']:
        if not isinstance(t, dict) or set(t) != {'order_id','machine_id','quote'}:
            raise ValueError('Invalid target fields')
        for k, limit in [('order_id',100),('machine_id',100),('quote',500)]:
            if not isinstance(t[k], str) or not 1 <= len(t[k].strip()) <= limit or '|' in t[k]:
                raise ValueError('Invalid target value')
        if not any(t['quote'] in turn for turn in turns):
            raise ValueError('Target quote must occur in original user text')
    return json.loads(json.dumps(args['targets']))


def project(evidence, declared, snapshot):
    """Only explicit pairs; no order × machine cross product or source lookup."""
    nodes, links, refs, rejected = {}, set(), {}, []
    pairs = {(t['order_id'], t['machine_id']): 'explicit_declaration' for t in declared}
    def node(n, eid):
        if not isinstance(n, dict) or not isinstance(n.get('id'), str):
            return
        clean = {k:v for k,v in n.items() if k not in ('namespace','version','entity_id')}
        nodes.setdefault(n['id'], []).append(clean)
        refs.setdefault(n['id'], set()).add(eid)
    def edge(a, rel, b):
        if a and b: links.add((a,rel,b))
    limited = False
    for e in evidence:
        eid = e.get('evidence_id', '?')
        if not snapshot.get('sha256') or not snapshot.get('version') or not snapshot.get('as_of') or any(
            e.get(k) != snapshot[v] for k,v in [('source_sha256','sha256'),('snapshot','version'),('as_of','as_of')]):
            rejected.append(eid); continue
        limited |= bool(e.get('limit_reached'))
        tool = e.get('tool')
        for r in e.get('rows', []):
            if tool == 'find_entities': node(r.get('entity'),eid)
            elif tool == 'inspect_entity':
                a,b = r.get('entity') or {},r.get('neighbor') or {}
                node(a,eid);node(b,eid)
                if r.get('from_id') == a.get('id'):edge(a.get('id'),r.get('relation'),b.get('id'))
                elif r.get('from_id') == b.get('id'):edge(b.get('id'),r.get('relation'),a.get('id'))
            elif tool in ('replacement_candidates','impacted_orders'):
                o,m,c = r.get('order') or {},r.get('machine') or {},r.get('required_capability')
                node(o,eid);node(m,eid);edge(o.get('id'),'REQUIRES',c)
                if tool == 'replacement_candidates' and o.get('id') and m.get('id'):
                    pairs.setdefault((o['id'],m['id']),'replacement_query')
                    edge(m['id'],'CAPABLE_OF',c)
            elif tool == 'qualification_records':
                m,q = r.get('machine') or {},r.get('qualification') or {}
                node(m,eid);node(q,eid);edge(m.get('id'),'HAS_QUALIFICATION',q.get('id'))
    merged, conflicts = {}, set()
    for nid, values in nodes.items():
        merged[nid] = {}
        for value in values:
            for k,v in value.items():
                if k in merged[nid] and merged[nid][k] != v:conflicts.add(nid)
                merged[nid][k] = v
    def iso(value):
        try:return isinstance(value,str) and date.fromisoformat(value).isoformat()==value
        except ValueError:return False
    rows, coverage = [], []
    for (oid,mid),origin in sorted(pairs.items()):
        o,m = merged.get(oid,{}),merged.get(mid,{})
        caps = sorted(b for a,r,b in links if a==oid and r=='REQUIRES')
        qids = sorted(b for a,r,b in links if a==mid and r=='HAS_QUALIFICATION')
        reasons = []
        if not iso(snapshot.get('as_of')):reasons.append('invalid_assessment_date')
        if {oid,mid,*qids} & conflicts:reasons.append('conflicting_selected_facts')
        if o.get('kind') != 'Order' or not o.get('product'):reasons.append('order_product_not_retrieved')
        if m.get('kind') != 'Machine' or not m.get('status'):reasons.append('machine_status_not_retrieved')
        if not caps:reasons.append('required_capability_not_retrieved')
        if any((mid,'CAPABLE_OF',c) not in links for c in caps):reasons.append('capability_relation_not_retrieved')
        records = [merged[q] for q in qids if q in merged]
        if len(records)!=len(qids):reasons.append('qualification_node_not_retrieved')
        if any(not iso(q.get(k)) for q in records for k in ('valid_from','valid_until')):reasons.append('invalid_qualification_dates')
        if any(q.get('kind')!='Qualification' or not all(isinstance(q.get(k),str) for k in ('product','capability','valid_from','valid_until')) for q in records):
            reasons.append('qualification_fields_not_retrieved')
        entry = {'order_id':oid,'machine_id':mid,'origin':origin,'status':'not_assessed' if reasons else 'projected',
                 'reasons':reasons,'evidence_ids':sorted(set().union(*(refs.get(n,set()) for n in [oid,mid,*qids]))), 'candidate_keys':[]}
        if not reasons:
            for cap in caps:
                key = '|'.join([oid,mid,cap]);entry['candidate_keys'].append(key)
                rows.append({'key':key,'order_id':oid,'machine_id':mid,'status':m['status'],
                    'capability':cap,'required':cap,'product':o['product'],'at':snapshot['as_of'],'records':records})
        coverage.append(entry)
    return rows, coverage, rejected, limited


def review(evidence, mode, declared, snapshot):
    if mode not in ('self','python','shacl'):raise ValueError('Unknown review mode')
    rows, targets, rejected, limited = project(evidence, declared, snapshot)
    flags = [] if mode=='self' else (python_flags(rows) if mode=='python' else shacl_flags(rows))
    for t in targets:
        if t['status']=='projected':
            t['status']='not_assessed' if mode=='self' else 'checked'
            if mode=='self':t['reasons']=['self_review_no_checker']
    checked = [r['key'] for r in rows] if mode!='self' else []
    return {'engine':mode,'review_contract':CONTRACT,'policy_revision':POLICY['id'],
        'candidate_count':len(rows),'flags':flags,'checked_candidates':checked,
        'assessment':'selected_candidates_checked' if checked else 'not_assessed',
        'coverage':{'targets':targets,'rejected_evidence_ids':rejected,'retrieval_limit_reached':limited,
            'declaration_count':len(declared),'question_coverage':'unverified',
            'outside_checker':['schedule_and_load','delivery_promises','impact_list_completeness','external_truth','physical_approval']},
        'scope':'Advisory on declared or replacement-query pairs in selected evidence only. No new lookup. Declarations do not verify intent or exhaustive question coverage. Missing relations are unassessed, not false. Flags concern retrieved records, not source absence. No flags certify neither truth nor complete retrieval.'}
