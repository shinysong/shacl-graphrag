"""Shared-draft advisory review messages, offline only; no provider admission."""
import copy
import hashlib
import json
from jsonschema import Draft202012Validator
from scripts.postreview_declarations import review_declarations
from scripts.postreview_source_pack import pack_sources

SCHEMA={'type':'object','additionalProperties':False,'required':['answer','claims','limitations'],'properties':{
 'answer':{'type':'string','minLength':1},
 'claims':{'type':'array','maxItems':16,'items':{'type':'object','additionalProperties':False,'required':['claim_id','text','kind','declaration'],'properties':{'claim_id':{'type':'string','minLength':1},'text':{'type':'string','minLength':1},'kind':{'enum':['recorded','lookup','difference','selection','role','temporal','unverified']},'declaration':{'type':'object'}}}},
 'limitations':{'type':'array','items':{'type':'string'}}}}
SYSTEM='''Answer only from selected_context. Return one JSON object matching response_schema. Do not recommend physical process changes. Distinguish nominal settings from actual measurements, missing selected evidence from global source absence, and latest supplied version from event-time applicability. Include factual assertions as separate claims; text must faithfully describe each declaration. Do not omit difficult claims to evade checking. No checker establishes correct question interpretation, complete evidence, prose coverage or external truth.
Each claim has claim_id,text,kind,declaration. Declare bindings yourself, never supply evidence values as a replacement source. Allowed declarations:
recorded: {source_id,field,value,unit}; field names refer to source.values.
lookup: {anchor_id,dictionary_id,lookup_kind,value,unit}; lookup_kind=defect_label or nominal_idc. Follow declared dictionary_refs within same workbook path/hash, match column A code, read column B defect label or column C nominal Idc under header Idc (A).
difference: {left,right,value,unit}; each operand is {anchor_id,dictionary_id,value,unit} for nominal_idc; value is right minus left. Binding and arithmetic checks are separate; claimed operand units are not checked by native lookup.
selection: {universe_ids,lower,upper,target_label,selected_ids,count}; declare the question's bounded row universe, inclusive x_init_mm bounds and codebook defect label. A self-declared smaller universe can pass and still answer the question wrongly.
role: {source_id,role}; compare the shared role_catalog, not a measured-value claim inferred from a settings table.
temporal: {event_date,scope,state,selected_id,latest_ids}; ISO dates, state=selected/ambiguous/unknown; selected_id=null unless selected. Intervals include start and exclude end. Latest=max release_date in supplied scope, ties kept; this does not establish knowledge at event time. Shared history completeness is declared, not independently verified.
unverified: {}; keep out-of-policy interpretations in text and limitations, not as validated facts.
If sources_format is packed, reconstruct each record from worksheet_templates[worksheet_template] plus record, then cell_table columns/rows using present boolean masks; false means absent key, true with null means explicit null. No source fields were intentionally removed. If raw, sources are direct source objects. The shared policies apply equally to every condition.
'''
REVIEW='''Review the supplied unchanged draft against the same selected context. review_report, when present, is advisory. With no report, perform self-review. Retain, qualify or revise only with that evidence; no new retrieval or compulsory veto. Return the same response schema. Explain material changes and remaining uncertainty in limitations. The report may omit prose errors or contain unknown/input_failure; these are not whole-answer judgements.'''


def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def validate_draft(draft):
    Draft202012Validator(SCHEMA).validate(draft)
    if not draft['answer'].strip():raise ValueError('blank answer')
    ids=[c['claim_id'] for c in draft['claims']]
    if len(ids)!=len(set(ids)) or any(not x.strip() for x in ids) or any(not c['text'].strip() for c in draft['claims']):raise ValueError('claim IDs/text')


def build_messages(question,context,condition='draft',draft=None,representation='raw',engine='pyshacl'):
    if condition not in ('draft','self_review','report') or representation not in ('raw','packed'):raise ValueError('condition/representation')
    if not isinstance(question,str) or not question.strip():raise ValueError('question')
    if set(context)!={'sources','role_catalog','history','policies'}:raise ValueError('shared context keys')
    if condition=='draft':
        if draft is not None:raise ValueError('initial draft must not receive prior answer')
    else:validate_draft(draft)
    selected=copy.deepcopy(context);selected['sources_format']=representation
    if representation=='packed':selected['sources']=pack_sources(context['sources'])
    reviewed=None;advisory=None
    # Self-review has schema admission only; checker failures cannot remove it.
    if condition=='report':
        reviewed=review_declarations(draft,context,engine)
        advisory={'scope':reviewed['scope'],'limits':reviewed['limits'],'declared_claim_count':reviewed['declared_claim_count'],'claims':[]}
        for c in reviewed['claims']:
            item={k:c[k] for k in ['claim_id','kind','state']}
            item['results']=[{k:r[k] for k in ['component','check_id','status'] if k in r} for r in c['results']]
            if 'error_type' in c:item['error_type']=c['error_type']
            advisory['claims'].append(item)
    user={'question':question,'selected_context':selected,'draft':copy.deepcopy(draft),'review_report':advisory,'response_schema':copy.deepcopy(SCHEMA)}
    messages=[{'role':'system','content':SYSTEM+('' if condition=='draft' else REVIEW)},{'role':'user','content':canonical(user)}]
    return {'messages':messages,'message_sha256':hashlib.sha256(canonical(messages).encode()).hexdigest(),'review_artifact':reviewed,
            'status':'offline candidate; token counts/provider caps/cost admission not certified'}
