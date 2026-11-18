"""Reviewed source-to-commerce bundles. Local heuristic drafts, no model calls.

Generation and execution are separate. Uploaded rule text is never evaluated.
Only explicitly selected, versioned adapter semantics can execute.
"""
from copy import deepcopy
from hashlib import sha256
from . import policy_dates, policy_inputs
import json
from pathlib import Path
import re
import tempfile
from uuid import uuid4
from typing import Protocol

from . import commerce, preparation_factory
from .preparation_sources import inspect_sources, relation_candidates

VERSION = 'data-preparation-1'
ADAPTER = 'commerce-csv-1'
SOURCE_ONLY = 'source_only'  # Explicit raw-column review, never an executable mapping.
STATES = {'pending', 'approved', 'excluded', 'insufficient'}
MAX_ENTRIES = 1024
MAX_HISTORY = 4096
MAX_HISTORY_BYTES = 2 * 1024 * 1024
MAX_DRAFT_BYTES = 16 * 1024 * 1024
POLICIES = {
    'shipping': {'kind':'SHACL/computed-feature', 'fields':['shipping_policies.minimum','shipping_policies.fee'],
                 'meaning':'Free-shipping threshold uses pre-discount subtotal; fee otherwise comes from the policy record'},
    'coupon': {'kind':'SHACL/computed-feature', 'fields':['coupons.minimum','coupons.discount'],
               'meaning':'Coupon threshold uses pre-discount subtotal; discount is capped at subtotal'},
    'approval': {'kind':'SHACL/computed-feature', 'fields':['approvals.order','approvals.sku','approvals.discount','approvals.status'],
                 'meaning':'Below threshold, preserve discount only with approved matching order, replacement SKU and discount'},
    'replacement': {'kind':'SHACL/computed-feature', 'fields':['orders.status','skus.product','skus.size','consents.status'],
                    'meaning':'Only unshipped orders; same product and size; approved consent for the order and replacement SKU'},
    'stock': {'kind':'SHACL/computed-feature', 'fields':['skus.available','items.quantity'],
              'meaning':'Available stock must cover quantity; blank stock remains unknown'},
    'arrival': {'kind':'SHACL/computed-feature', 'fields':['skus.arrival','skus.arrival_confirmed','orders.requested_arrival'],
                'meaning':'Arrival promise requires a confirmed date no later than requested; otherwise delivery remains unresolved'},
    'split': {'kind':'SHACL/computed-feature', 'fields':['shipping_policies.split_allowed'],
              'meaning':'Split shipment requires split_allowed true'},
}


def adapter_config(adapter):
    if adapter==ADAPTER:
        return commerce.SPECS, POLICIES
    if adapter==preparation_factory.ADAPTER:
        return preparation_factory.SPECS, preparation_factory.POLICIES
    raise ValueError('Unsupported adapter')


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',',':')).encode()).hexdigest()


class DraftGenerator(Protocol):
    """Generators return suggestions, never approvals or executable code."""
    name: str
    def suggest(self, sources: list) -> list: ...


def validate_model_questions(questions):
    """Bound display-only model clarification prompts; no truth validation."""
    if (not isinstance(questions, list) or len(questions) > 8
            or any(not isinstance(q, str) or not q.strip() or len(q) > 1000 for q in questions)
            or len(set(questions)) != len(questions)):
        raise ValueError('Model questions require at most 8 unique nonblank strings of at most 1000 characters')


def validate_annotations(entry, sources):
    """Validate optional display metadata, not the meaning of its assertions."""
    def bounded(value, depth=0):
        if depth > 8:
            raise ValueError('Suggestion annotation nesting exceeds limit')
        if value is None or isinstance(value, bool):return
        if isinstance(value, str) and len(value) <= 16000:return
        if type(value) is int and abs(value) <= 10**12:return
        if isinstance(value, list) and len(value) <= 256:
            for item in value:bounded(item, depth+1)
            return
        if isinstance(value, dict) and len(value) <= 256:
            for key,item in value.items():
                if not isinstance(key,str) or len(key)>256:
                    raise ValueError('Invalid annotation key')
                bounded(item, depth+1)
            return
        raise ValueError('Invalid or oversized suggestion annotation')

    for field in ('extraction','overlap'):
        if field in entry:
            if not isinstance(entry[field],dict):raise ValueError('Annotation must be an object')
            bounded(entry[field])
    extraction=entry.get('extraction',{})
    if 'assessment' in extraction:
        if (entry.get('kind')!='relation' or not isinstance(extraction['assessment'],str)
                or extraction['assessment'] not in ('supported','contradicted','uncertain')
                or not isinstance(extraction.get('method'),str)
                or not extraction['method'].startswith('model-proposal-1:')):
            raise ValueError('Invalid saved relation assessment')
        if extraction['assessment']!='uncertain' and not extraction.get('source_evidence'):
            raise ValueError('Saved relation assessment requires source evidence')
    for field in ('questions','candidate_contracts','scope_candidates','conditions',
                  'exceptions','effective_dates','amount_expressions','unresolved',
                  'candidates','observed_values'):
        if field in extraction and (not isinstance(extraction[field],list) or
                any(not isinstance(v,str) for v in extraction[field])):
            raise ValueError('Annotation text field must be a list of strings')
    if isinstance(extraction.get('method'),str) and extraction['method'].startswith('model-proposal-1:') and 'questions' in extraction:
        validate_model_questions(extraction['questions'])
    if 'source_evidence' in extraction:
        from . import preparation_evidence
        preparation_evidence.validate(extraction['source_evidence'],sources)
    related=extraction.get('related_policy_statements',[])
    if not isinstance(related,list) or len(related)>8:
        raise ValueError('Invalid related policy annotations')
    refs={s['name']:s for s in sources}
    for ref in related:
        keys={'entry_id','file','paragraph','line_start','line_end','sha256','different_fields'}
        if not isinstance(ref,dict) or set(ref)!=keys:
            raise ValueError('Invalid related policy locator')
        source=refs.get(ref['file']) if isinstance(ref['file'],str) else None
        para=next((p for p in source.get('paragraphs',[]) if p['paragraph']==ref['paragraph']),None) if source else None
        if (not para or source['sha256']!=ref['sha256'] or
                ref['entry_id']!=f'policy:{source["name"]}:{para["paragraph"]}' or
                any(type(ref[k]) is not int or ref[k]!=para[k] for k in ('paragraph','line_start','line_end'))):
            raise ValueError('Related policy locator does not match source')
        differences=ref['different_fields']
        if not isinstance(differences,list) or not differences or any(
                not isinstance(v,str) or v not in ('basis','amount_expressions','effective_dates','exceptions') for v in differences):
            raise ValueError('Invalid related policy difference fields')
    if 'related_policy_count' in extraction and (type(extraction['related_policy_count']) is not int or
            not len(related)<=extraction['related_policy_count']<=MAX_ENTRIES):
        raise ValueError('Invalid related policy count')


def validate_suggestions(entries, sources):
    """Check source locators and coverage, never the truth of suggested meanings."""
    if not isinstance(entries,list) or len(entries)>MAX_ENTRIES:
        raise ValueError('Generator must return at most 1024 review entries')
    refs={s['name']:s for s in sources}
    required={f'map:{s["name"]}:{c}' for s in sources if s['kind']=='table' for c in s['headers']}
    required|={f'policy:{s["name"]}:{v["paragraph"]}' for s in sources if s['kind']!='table' for v in s['paragraphs']}
    ids=set()
    for e in entries:
        if not isinstance(e,dict) or not {'id','kind','source','target','reason'}<=set(e) or set(e)-{'id','kind','source','target','reason','extraction','overlap'}:
            raise ValueError('Invalid suggestion fields; generators cannot approve entries')
        if not isinstance(e['id'],str) or not 1<=len(e['id'])<=1024 or e['id'] in ids:
            raise ValueError('Invalid or duplicate suggestion ID')
        ids.add(e['id'])
        validate_annotations(e,sources)
        if not isinstance(e['reason'],str) or len(e['reason'])>4000 or not isinstance(e['source'],dict):
            raise ValueError('Invalid suggestion explanation/source')
        source=refs.get(e['source'].get('file'))
        if source is None:raise ValueError('Suggestion source does not exist')
        if e['kind'] in ('mapping','relation'):
            column=e['source'].get('column')
            if source['kind']!='table' or column not in source['headers']:
                raise ValueError('Suggestion column does not exist')
            expected={'file':source['name'],'column':column}
            if e['kind']=='relation':expected['sha256']=source['sha256']
            if e['source']!=expected:raise ValueError('Suggestion source locator mismatch')
            if e['kind']=='mapping' and e['id']!=f'map:{source["name"]}:{column}':
                raise ValueError('Mapping ID does not match source')
            if e['kind']=='relation':
                target=e['target']
                dest=refs.get(target.get('file')) if isinstance(target,dict) else None
                if not dest or dest['kind']!='table' or target.get('column') not in dest['headers'] or target!={'file':dest['name'],'column':target['column'],'sha256':dest['sha256']}:
                    raise ValueError('Invalid suggested relation target')
        elif e['kind']=='policy':
            if source['kind']=='table':raise ValueError('Policy requires document source')
            para=next((v for v in source['paragraphs'] if v['paragraph']==e['source'].get('paragraph')),None)
            if para is None or e['source']!={'file':source['name'],**para} or e['id']!=f'policy:{source["name"]}:{para["paragraph"]}':
                raise ValueError('Policy text/locator does not match source')
        else:raise ValueError('Unsupported suggestion kind')
        if e['kind']!='relation' and not isinstance(e['target'],str):
            raise ValueError('Suggestion target must be text')
    if not required<=ids:raise ValueError('Suggestions omit source columns or policy paragraphs')


def policy_hint(text):
    """Bounded lexical extraction. These spans are not certified semantics."""
    cues = [('shipping',('무료배송',)), ('approval',('승인','할인')),
            ('coupon',('쿠폰',)), ('replacement',('출고 전',)),
            ('stock',('재고',)), ('arrival',('도착',)), ('split',('부분 출고',)),
            ('qualification',('자격',)), ('availability',('가용',))]
    matches = [key for key,words in cues if all(word in text for word in words)]
    # Exception approval is more specific than the coupon mention in its clause.
    if 'approval' in matches and 'coupon' in matches:
        matches.remove('coupon')
    target = matches[0] if len(matches)==1 else ''
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n',text) if s.strip()]
    return {'target':target, 'candidate_contracts':matches,
            'scope_candidates':[s for s in sentences if any(w in s.lower() for w in
                ('주문','상품','고객','설비','제품','자격','지역','order','product','customer','machine','region'))],
            'conditions':[s for s in sentences if any(w in s for w in ('이상','이하','미달','필요','때','경우','must','if '))],
            'exceptions':[s for s in sentences if any(w in s for w in ('예외','제외','단,','unless','except'))],
            'effective_dates':re.findall(r'(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)',text),
            'amount_expressions':re.findall(r'\d[\d,]*(?:만)?\s*원',text),
            'basis': 'before_discount' if '할인 전' in text and '할인 후' not in text else
                     'after_discount' if '할인 후' in text and '할인 전' not in text else 'unresolved',
            'unresolved':['Check scope, exceptions, effective date and compatibility with the selected adapter contract']}


class LocalGenerator:
    name = 'local-exact-name-and-paragraphs-1'

    def __init__(self, adapter=ADAPTER):
        self.specs,self.policies=adapter_config(adapter)

    def suggest(self, sources):
        base_count = sum(len(s['headers']) if s['kind']=='table' else len(s['paragraphs']) for s in sources)
        if base_count > MAX_ENTRIES:
            raise ValueError('Draft exceeds 1024 review entries; split the input bundle')
        suggestions = []
        for source in sources:
            if source['kind'] == 'table':
                table = Path(source['name']).stem
                for column in source['headers']:
                    target = f'{table}.{column}' if table in self.specs and column in {'id', *self.specs[table]} else ''
                    suggestions.append({'id': f'map:{source["name"]}:{column}', 'kind':'mapping',
                        'source': {'file':source['name'],'column':column}, 'target':target,
                        'reason':'Exact file-stem and field-name match' if target else 'No exact-name mapping; select explicitly'})
            else:
                for p in source['paragraphs']:
                    hint = policy_hint(p['text'])
                    applicable = [key for key in hint['candidate_contracts'] if key in self.policies]
                    hint['target'] = applicable[0] if len(applicable)==1 else ''
                    suggestions.append({'id':f'policy:{source["name"]}:{p["paragraph"]}', 'kind':'policy',
                        'source':{'file':source['name'], **p}, 'target':hint['target'] if hint['target'] in self.policies else '', 'extraction':hint,
                        'reason':'Local keyword/span extraction only; policy meaning and applicability require review'})
        for index, candidate in enumerate(relation_candidates(sources)):
            if len(suggestions) >= MAX_ENTRIES:
                raise ValueError('Draft exceeds 1024 review entries; split the input bundle')
            suggestions.append({'id':f'relation:{index}', 'kind':'relation',
                'source':candidate['source'], 'target':candidate['target'],
                'reason':candidate['reason'], 'overlap':candidate})
        return suggestions


def create(files, metadata, generator=None, adapter=ADAPTER):
    adapter_config(adapter)
    sources = inspect_sources(files)
    if not isinstance(metadata, dict) or set(metadata) != {'snapshot_id','as_of','currency'}:
        raise ValueError('Explicit snapshot_id, as_of and currency required')
    currency=metadata['currency']
    if adapter==ADAPTER:
        if not isinstance(currency,str) or not (currency in ('unknown','mixed','not_applicable') or re.fullmatch(r'[A-Z]{3}',currency)):
            raise ValueError('Declare a three-letter currency label, unknown, mixed or not_applicable')
    elif currency!='not_applicable':
        raise ValueError('Factory currency is not_applicable')
    commerce.check_date(metadata['as_of'])
    if not isinstance(metadata['snapshot_id'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',metadata['snapshot_id']):
        raise ValueError('Invalid snapshot ID')
    generator = generator or LocalGenerator(adapter)
    hashes = {s['name']:s['sha256'] for s in sources}
    entries = generator.suggest(deepcopy(sources))
    validate_suggestions(entries,sources)
    saved_suggestions=deepcopy(entries)
    for entry in entries:
        entry.update(status='pending', note='', interpretation='', dependencies=deepcopy(hashes))
    draft = {'version':VERSION, 'adapter':adapter, 'generator':generator.name,
            'metadata':deepcopy(metadata), 'sources':sources, 'entries':entries,
            'saved_suggestions':saved_suggestions,
            'notice':('Local heuristic suggestions, not LLM extraction. No policy is approved automatically.'
                      if generator.name==LocalGenerator.name else
                      'Saved generator suggestions, not verified facts. No policy is approved automatically.'),
            'ontology':{'kind':'OWL-RL', 'status':'fixed_adapter',
                        'axioms':['RunningShoe subClassOf Footwear','Socks subClassOf Apparel'] if adapter==ADAPTER else preparation_factory.ONTOLOGY,
                        'notice':'Existing authored category axioms; not extracted from policy documents'}}
    _check_draft_size(draft)
    return draft


def _check_draft_size(draft):
    try:
        size = len(json.dumps(draft,ensure_ascii=False).encode('utf-8'))
    except (TypeError, ValueError, RecursionError, UnicodeError) as exc:
        raise ValueError('Invalid draft serialization') from exc
    if size>MAX_DRAFT_BYTES:
        raise ValueError('Draft exceeds 16 MiB; split or archive this bundle')


def _history_record(entry, event):
    return {'event':event, 'id':entry['id'], 'kind':entry['kind'],
            'source':{k:deepcopy(entry['source'][k]) for k in ('file','column','paragraph') if k in entry['source']},
            'dependencies':deepcopy(entry['dependencies']),
            **{k:deepcopy(entry[k]) for k in ('status','target','note','interpretation')},
            **({'temporal':deepcopy(entry['temporal'])} if 'temporal' in entry else {}),
            **({'agreement':deepcopy(entry['agreement'])} if 'agreement' in entry else {})}


def _same_entry(left, right):
    if left['id']!=right['id'] or left['kind']!=right['kind']:
        return False
    keys = ('file','paragraph') if left['kind']=='policy' else ('file','column')
    if any(left['source'].get(k)!=right['source'].get(k) for k in keys):
        return False
    return left['kind']!='relation' or all(left['target'].get(k)==right['target'].get(k) for k in ('file','column'))


def _history_views(draft, history):
    draft['review_history'] = deepcopy(history)
    draft['retired_entries'] = [deepcopy(r) for r in history if r['event']=='retire']
    for entry in draft['entries']:
        entry.pop('previous_decision',None)
        previous = next((r for r in reversed(history) if r['event']=='refresh' and _same_entry(r,entry)),None)
        if previous is not None:
            entry['previous_decision'] = deepcopy(previous)


def _validated_history(draft):
    """History is untrusted annotation, never executable approval or authentication."""
    _check_draft_size(draft)
    history = draft.get('review_history',[])
    if not isinstance(history,list) or len(history)>MAX_HISTORY:
        raise ValueError('Review history exceeds 4096 records or is not a list')
    try:
        size = len(json.dumps(history,ensure_ascii=False).encode('utf-8'))
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError('Invalid review history') from exc
    if size>MAX_HISTORY_BYTES:
        raise ValueError('Review history exceeds 2 MiB; archive this bundle before further review')
    specs,policies = adapter_config(draft['adapter'])
    mappings = {f'{t}.{k}' for t,spec in specs.items() for k in ['id',*spec]}
    for r in history:
        if not isinstance(r,dict) or set(r)-{'temporal','agreement'}!={'event','id','kind','source','dependencies','status','target','note','interpretation'}:
            raise ValueError('Invalid review history record')
        if not isinstance(r['event'],str) or not isinstance(r['kind'],str) or r['event'] not in ('change','refresh','retire') or r['kind'] not in ('mapping','policy','relation'):
            raise ValueError('Invalid review history event/kind')
        if not isinstance(r['id'],str) or not 1<=len(r['id'])<=1024 or not isinstance(r['status'],str) or r['status'] not in STATES:
            raise ValueError('Invalid historical decision')
        if not all(isinstance(r[k],str) and len(r[k])<=4000 for k in ('note','interpretation')):
            raise ValueError('Invalid historical review text')
        if 'temporal' in r:
            if r['kind']!='policy':raise ValueError('Date roles require policy source')
            policy_dates.validate(r['temporal'])
        if 'agreement' in r:
            from . import policy_agreement
            if r['kind']!='policy':raise ValueError('Comparison requires policy source')
            policy_agreement.validate(r['agreement'])
        deps = r['dependencies']
        if not isinstance(deps,dict) or not 1<=len(deps)<=64 or not all(
            isinstance(k,str) and 1<=len(k)<=255 and isinstance(v,str) and re.fullmatch(r'[0-9a-f]{64}',v)
            for k,v in deps.items()):
            raise ValueError('Invalid historical source hashes')
        source = r['source']
        keys = {'file','paragraph'} if r['kind']=='policy' else {'file','column'}
        if not isinstance(source,dict) or set(source)!=keys or not isinstance(source['file'],str) or source['file'] not in deps:
            raise ValueError('Invalid historical source reference')
        if r['kind']=='policy':
            if type(source['paragraph']) is not int or source['paragraph']<1:
                raise ValueError('Invalid historical paragraph')
        elif not isinstance(source['column'],str) or not 1<=len(source['column'])<=1024:
            raise ValueError('Invalid historical column')
        if r['kind'] in ('mapping','policy'):
            prefix = 'map' if r['kind']=='mapping' else 'policy'
            locator = source['column'] if r['kind']=='mapping' else source['paragraph']
            if r['id']!=f"{prefix}:{source['file']}:{locator}":
                raise ValueError('Historical entry ID does not match its source')
        target = r['target']
        if r['kind']=='relation':
            if (not isinstance(target,dict) or set(target)!={'file','column','sha256'}
                or not isinstance(target['file'],str) or target['file'] not in deps
                or target['sha256']!=deps[target['file']]
                or not isinstance(target['column'],str) or not 1<=len(target['column'])<=1024):
                raise ValueError('Invalid historical relation target')
        elif not isinstance(target,str) or target not in (mappings|{'',SOURCE_ONLY} if r['kind']=='mapping' else set(policies)|{'','unsupported','context'}):
            raise ValueError('Invalid historical target')
        if r['status']=='approved' and (not target or (r['kind']=='policy' and (target=='unsupported' or not r['interpretation'].strip()))):
            raise ValueError('Invalid historical approval')
        if r['status']=='approved' and r['kind']=='mapping' and target==SOURCE_ONLY and not r['interpretation'].strip():
            raise ValueError('Invalid historical source-only approval')
        if r['status']=='excluded' and not r['note'].strip():
            raise ValueError('Invalid historical exclusion')
    expected = {'entries':[{k:deepcopy(e[k]) for k in ('id','kind','source','target')} for e in draft['entries']]}
    _history_views(expected,history)
    if draft.get('retired_entries',[]) != expected['retired_entries'] or any(
        e.get('previous_decision')!=v.get('previous_decision') for e,v in zip(draft['entries'],expected['entries'])):
        raise ValueError('Historical annotations do not match source-bound review history')
    return deepcopy(history)


def _set_history(draft, history):
    _history_views(draft,history)
    _validated_history(draft)


def change(draft, entry_id, status, target, note='', interpretation='', temporal=None):
    history = _validated_history(draft)
    specs,policies=adapter_config(draft['adapter'])
    if status not in STATES or not all(isinstance(s,str) and len(s)<=4000 for s in (note,interpretation)):
        raise ValueError('Invalid review decision')
    d = deepcopy(draft)
    entry = next((e for e in d['entries'] if e['id']==entry_id), None)
    if entry is None:
        raise ValueError('Unknown entry')
    if temporal is None and 'temporal' in entry:temporal=entry['temporal']
    if temporal is not None:
        if entry['kind']!='policy':raise ValueError('Date roles require policy source')
        policy_dates.validate(temporal,entry['source']['text'])
    if entry['kind']=='mapping':
        valid = {f'{t}.{k}' for t,spec in specs.items() for k in ['id',*spec]}
        if target not in valid | {'',SOURCE_ONLY}:
            raise ValueError('Unsupported mapping target')
        if status=='approved' and target==SOURCE_ONLY and not interpretation.strip():
            raise ValueError('Describe the source column before approving raw-only use')
    elif entry['kind']=='policy':
        if target not in set(policies)|{'','unsupported','context'}:
            raise ValueError('Unsupported policy contract')
        if status=='approved' and target not in policies and target!='context':
            raise ValueError('Unsupported policy cannot become an executable rule')
        if status=='approved' and not interpretation.strip():
            raise ValueError('Record the reviewed interpretation and applicability')
        if status=='approved' and target in policies:
            hint = policy_hint(entry['source']['text'])
            if target in ('shipping','coupon') and hint['basis']=='after_discount':
                raise ValueError('This adapter calculates before discount; after-discount policy is unsupported')
            if hint['exceptions']:
                raise ValueError('Policy exceptions need a supported adapter; leave this policy unresolved')
            if temporal is not None:
                policy_dates.require_applicable(temporal,d['metadata']['as_of'])
            else:
                # Preserve historical replay; workspace requires explicit roles before execution.
                for effective in hint['effective_dates']:
                    commerce.check_date(effective)
                    if effective > d['metadata']['as_of']:
                        raise ValueError('Policy date is later than the snapshot; applicability remains unresolved')
    elif entry['kind']=='relation':
        if not isinstance(target,dict) or set(target) != {'file','column','sha256'}:
            raise ValueError('Relation target must name a source column and hash')
        s = next((s for s in d['sources'] if s['name']==target['file']),None)
        if not s or s['kind']!='table' or target['column'] not in s['headers'] or target['sha256']!=s['sha256']:
            raise ValueError('Invalid relation target')
    if status=='approved' and not target:
        raise ValueError('Approval requires a target')
    if status=='excluded' and not note.strip():
        raise ValueError('Exclusion requires a reason')
    decision = dict(status=status,target=deepcopy(target),note=note,interpretation=interpretation)
    if temporal is not None:decision['temporal']=deepcopy(temporal)
    elif 'temporal' in entry:decision['temporal']=deepcopy(entry['temporal'])
    if any(entry.get(k)!=v for k,v in decision.items()):
        history.append(_history_record(entry,'change'))
    entry.update(decision)
    _set_history(d,history)
    return d


def add_relation(draft, source, target, reason):
    """Append a human-authored pending hypothesis, never an approval or query."""
    d = restore_draft(draft)
    if not isinstance(reason,str) or not reason.strip() or len(reason)>4000:
        raise ValueError('Describe why these columns may be related')
    refs={s['name']:s for s in d['sources'] if s['kind']=='table'}
    def locator(value):
        if not isinstance(value,dict) or set(value)!={'file','column'}:
            raise ValueError('Select an existing file and column')
        if not all(isinstance(v,str) for v in value.values()):
            raise ValueError('Select an existing file and column')
        table=refs.get(value['file'])
        if table is None or value['column'] not in table['headers']:
            raise ValueError('Selected relation column does not exist')
        return {**value,'sha256':table['sha256']}
    left,right=locator(source),locator(target)
    if left['file']==right['file']:raise ValueError('Select columns in two different files')
    pair=lambda a,b: {(a['file'],a['column']),(b['file'],b['column'])}
    if any(e['kind']=='relation' and pair(e['source'],e['target'])==pair(left,right) for e in d['entries']):
        raise ValueError('This relation already exists; review the existing entry')
    ident='relation:manual:'+uuid4().hex
    suggestion={'id':ident,'kind':'relation','source':left,'target':right,
                'reason':reason,'extraction':{'method':'human-relation-1'}}
    # Legacy local drafts may omit saved suggestions; materialize their original
    # proposals, not their subsequently edited decisions.
    if 'saved_suggestions' not in d:
        d['saved_suggestions']=LocalGenerator(d['adapter']).suggest(deepcopy(d['sources']))
    d['saved_suggestions'].append(deepcopy(suggestion))
    validate_suggestions(d['saved_suggestions'],d['sources'])
    d['entries'].append({**suggestion,'status':'pending','note':'','interpretation':'',
                         'dependencies':{s['name']:s['sha256'] for s in d['sources']}})
    return restore_draft(d)


def refresh(draft, files, generator=None, metadata=None):
    """Conservative invalidation: all decisions depend on the source bundle.

    A newly added policy can alter otherwise unchanged record applicability.
    Do not silently carry approvals just because their local column is unchanged.
    """
    # Reupload is not regeneration. Preserve original proposals separately from
    # edited decisions and avoid calling an optional generator for unchanged data.
    inspected = inspect_sources(files)
    if (sorted(inspected,key=lambda s:s['name'])==sorted(draft['sources'],key=lambda s:s['name'])
            and (metadata is None or metadata==draft['metadata'])):
        return restore_draft(draft)
    history = _validated_history(draft)
    fresh = create(files,draft['metadata'] if metadata is None else metadata,
                   adapter=draft['adapter'],generator=generator)
    before = {s['name']:s['sha256'] for s in draft['sources']}
    after = {s['name']:s['sha256'] for s in fresh['sources']}
    # Retain manually authored hypotheses when both columns still exist.
    # Refresh updates hashes and normal invalidation below removes approvals.
    for old in draft['entries']:
        if old.get('extraction',{}).get('method')!='human-relation-1':continue
        endpoints=[{k:e[k] for k in ('file','column')} for e in (old['source'],old['target'])]
        available=all(any(s['name']==e['file'] and s['kind']=='table' and e['column'] in s['headers'] for s in fresh['sources']) for e in endpoints)
        if available:
            # Local generation may now propose the same pair; keep the explicit
            # human identity and original proposal rather than duplicate it.
            same=lambda e: e['kind']=='relation' and e.get('extraction',{}).get('method')!='human-relation-1' and {(e['source']['file'],e['source']['column']),(e['target']['file'],e['target']['column'])}=={(v['file'],v['column']) for v in endpoints}
            fresh['entries']=[e for e in fresh['entries'] if not same(e)]
            fresh['saved_suggestions']=[e for e in fresh['saved_suggestions'] if not same(e)]
            original=next(e for e in draft['saved_suggestions'] if e['id']==old['id'])
            suggestion={**deepcopy(original),'source':{**endpoints[0],'sha256':after[endpoints[0]['file']]},
                        'target':{**endpoints[1],'sha256':after[endpoints[1]['file']]}}
            fresh['saved_suggestions'].append(deepcopy(suggestion))
            fresh['entries'].append({**suggestion,'status':'pending','note':'','interpretation':'',
                                     'dependencies':deepcopy(after)})
    validate_suggestions(fresh['saved_suggestions'],fresh['sources'])
    previous = {e['id']:e for e in draft['entries']}
    retained = set()
    for entry in fresh['entries']:
        old = previous.get(entry['id'])
        if old and _same_entry(old,entry):
            retained.add(old['id'])
            if before==after and fresh['metadata']==draft['metadata']:
                entry.update(deepcopy(old))
            else:
                history.append(_history_record(old,'refresh'))
                entry['reason'] += '; source bundle or metadata changed: review previous decision again'
    history.extend(_history_record(e,'retire') for e in draft['entries'] if e['id'] not in retained)
    _set_history(fresh,history)
    return fresh


def _convert(value, kind):
    kinds = kind if isinstance(kind,tuple) else (kind,)
    if value=='' and type(None) in kinds:
        return None
    if bool in kinds:
        if value not in ('true','false'): raise ValueError('Boolean must be true or false')
        return value=='true'
    if int in kinds:
        if not re.fullmatch(r'0|[1-9][0-9]*',value): raise ValueError('Nonnegative canonical integer required')
        return int(value)
    return value


def materialize(draft, proposal=None):
    if draft.get('adapter')==ADAPTER and draft.get('metadata',{}).get('currency')!='KRW':
        raise ValueError('Decision execution supports KRW only. Original-record lookup remains available; no currency conversion is performed.')
    specs,policies=adapter_config(draft.get('adapter'))
    if proposal is not None:
        if draft.get('adapter')!=ADAPTER:raise ValueError('Interactive proposals currently require commerce data')
        required={'item','replacement','retain_discount','free_shipping','split','promise_arrival'}
        if not isinstance(proposal,dict) or set(proposal)!=required:
            raise ValueError('Invalid replacement proposal fields')
        for key in required:
            kind=str if key in ('item','replacement') else bool
            if type(proposal[key]) is not kind:raise ValueError('Invalid replacement proposal type')
    if draft.get('version')!=VERSION:
        raise ValueError('Unsupported bundle version/adapter')
    pending = [e['id'] for e in draft['entries'] if e['status'] not in ('approved','excluded')]
    if pending:
        raise ValueError('Unresolved entries: '+', '.join(pending[:12]))
    covered = {e['target'] for e in draft['entries'] if e['kind']=='policy' and e['status']=='approved'}
    if set(policies)-covered:
        raise ValueError('Required policy interpretations missing: '+', '.join(sorted(set(policies)-covered)))
    source_map = {s['name']:s for s in draft['sources']}
    mappings = {}
    for e in draft['entries']:
        if e['kind']=='mapping' and e['status']=='approved' and e['target']!=SOURCE_ONLY:
            if e['target'] in mappings:
                raise ValueError('Multiple mappings for '+e['target'])
            mappings[e['target']] = e['source']
    data = {'schema_version':1, **draft['metadata']}
    for table,spec in specs.items():
        if table=='cases' and proposal is not None:
            # User intent is a separate input, never an uploaded source fact.
            data['cases']=[{'id':'interactive','label':'사용자 변경안 검토',
                            'question':f'{proposal["item"]} 항목을 {proposal["replacement"]} 옵션으로 바꾸는 조건을 검토합니다.',
                            **proposal}]
            continue
        required = {'id':str,**spec}
        missing = [k for k in required if f'{table}.{k}' not in mappings]
        if missing:
            raise ValueError(f'{table}: required mappings missing: '+', '.join(missing))
        refs = {k:mappings[f'{table}.{k}'] for k in required}
        filenames = {r['file'] for r in refs.values()}
        if len(filenames)!=1:
            raise ValueError(f'{table}: one CSV per collection required; multi-table joins need an adapter')
        source = source_map[next(iter(filenames))]
        data[table] = [{k:_convert(row[refs[k]['column']],kind) for k,kind in required.items()} for row in source['rows']]
    return commerce.check_data(data) if draft['adapter']==ADAPTER else preparation_factory.check(data)


def execute_proposal(draft, proposal, *, parameter_origin='user_input'):
    """Execute supplied parameters; origin is caller metadata, not approval."""
    if parameter_origin not in ('user_input','model_interpretation'):
        raise ValueError('Unsupported proposal parameter origin')
    draft=restore_draft(draft)
    data=materialize(draft,proposal=proposal)
    with tempfile.TemporaryDirectory(prefix='factory-proposal-') as temp:
        path=Path(temp)/'shop.json'
        path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
        result=commerce.run_case('interactive',path)
    result['preparation']={'draft_sha256':digest(draft),'adapter':draft['adapter'],
        'sources':[{'name':s['name'],'sha256':s['sha256']} for s in draft['sources']],
        'metadata':deepcopy(draft['metadata']),'proposal':deepcopy(proposal),
        'policy_inputs':policy_inputs.describe(draft,adapter_config(draft['adapter'])[1]),
        'parameter_origin':parameter_origin,
        'notice':'Supplied proposal parameters; fixed queries/checks and template answer. This tool execution makes no LLM calls or order changes; parameter origin is recorded separately.'}
    return result


def freeze(draft):
    _validated_history(draft)
    data = materialize(draft)
    payload = {'draft':deepcopy(draft),'data':data}
    return {'version':VERSION,'payload':payload,'sha256':digest(payload)}


def restore_draft(old):
    try:
        return _restore_draft(old)
    except (KeyError,TypeError,AttributeError,IndexError,RecursionError) as exc:
        raise ValueError('Malformed saved draft structure; original workspace was not changed') from exc


def _restore_draft(old):
    """Restore saved proposals without invoking their generator or trusting approvals.

    Recheck source bytes/locators, then replay supported human decisions. Imported
    history is annotation, not an authenticated record of who approved it.
    """
    _check_draft_size(old)
    if not isinstance(old,dict) or old.get('version')!=VERSION:
        raise ValueError('Unsupported draft revision')
    history=_validated_history(old)
    saved=old.get('saved_suggestions')
    generator=None
    if saved is not None:
        name=old.get('generator')
        if not isinstance(name,str) or not 1<=len(name)<=200:
            raise ValueError('Invalid saved generator identity')
        class SavedGenerator:
            def suggest(self,sources):return deepcopy(saved)
        generator=SavedGenerator()
        generator.name=name
    fresh=create([{'name':s['name'],'content':s['content']} for s in old['sources']],
                 old['metadata'],generator=generator,adapter=old['adapter'])
    if old['sources']!=fresh['sources']:
        raise ValueError('Saved source inspection does not match original bytes')
    if old['generator']!=fresh['generator']:
        raise ValueError('Legacy generator requires saved suggestions for restoration')
    if saved is None:fresh.pop('saved_suggestions',None)
    if len(old['entries'])!=len(fresh['entries']) or len({e['id'] for e in old['entries']})!=len(fresh['entries']) or {e['id'] for e in old['entries']}!={e['id'] for e in fresh['entries']}:
        raise ValueError('Bundle entries do not match original sources')
    for entry in old['entries']:
        validate_annotations(entry,fresh['sources'])
        rebuilt=next(e for e in fresh['entries'] if e['id']==entry['id'])
        for field in ('kind','source','extraction','overlap','dependencies'):
            if entry.get(field)!=rebuilt.get(field):
                raise ValueError('Saved entry differs from source-bound suggestion')
        if entry.get('reason') not in (rebuilt['reason'],
                rebuilt['reason']+'; source bundle changed: review previous decision again',
                rebuilt['reason']+'; source bundle or metadata changed: review previous decision again'):
            raise ValueError('Unsupported entry reason')
        rebuilt['reason']=entry['reason']
        fresh=change(fresh,entry['id'],entry['status'],entry['target'],entry['note'],entry['interpretation'],temporal=entry.get('temporal'))
    # Stale comparisons remain inspectable; they never become current merely
    # through import. Current binding is checked separately against all inputs.
    for entry in old['entries']:
        if 'agreement' in entry:
            from . import policy_agreement
            if entry['kind']!='policy':raise ValueError('Comparison requires policy source')
            policy_agreement.validate(entry['agreement'])
            next(e for e in fresh['entries'] if e['id']==entry['id'])['agreement']=deepcopy(entry['agreement'])
    _set_history(fresh,history)
    return fresh


def restore(bundle):
    """Rebuild derived inspection and replay decisions; hashes are not signatures."""
    if not isinstance(bundle,dict) or set(bundle)!={'version','payload','sha256'} or bundle['version']!=VERSION:
        raise ValueError('Invalid bundle envelope')
    payload = bundle['payload']
    if digest(payload)!=bundle['sha256']:
        raise ValueError('Bundle hash mismatch')
    fresh = restore_draft(payload['draft'])
    if materialize(fresh)!=payload['data']:
        raise ValueError('Materialized data mismatch')
    return fresh


def execute(bundle, case_id):
    draft = restore(bundle)
    data = materialize(draft)
    if draft['adapter']==ADAPTER:
        with tempfile.TemporaryDirectory(prefix='factory-prepared-') as temp:
            path = Path(temp)/'shop.json'
            path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
            result = commerce.run_case(case_id,path)
    else:
        result=preparation_factory.execute(data,case_id)
    result['preparation'] = {'bundle_sha256':bundle['sha256'],'adapter':draft['adapter'],
        'sources':[{'name':s['name'],'sha256':s['sha256']} for s in draft['sources']],
        'policies':[e for e in draft['entries'] if e['kind']=='policy'],
        'policy_inputs':policy_inputs.describe(draft,adapter_config(draft['adapter'])[1]),
        'notice':'Human-reviewed fixed adapter semantics; template answer, no LLM or order changes'}
    return result
