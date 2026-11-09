"""Prepare equal-context advisory revision messages. No provider calls or scorer.

Only explicit draft mappings are checked. Natural-language coverage, interpretation
and factual truth remain unverified even if every declared scalar agrees.
"""
import hashlib,json
from pathlib import Path
from jsonschema import Draft202012Validator
from scripts.post_answer_review import review,validate_packet
ROOT=Path('research/post-answer-review-1')

def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)

def prepare(draft,sources,engine='python'):
    schema=json.loads((ROOT/'draft-schema-v1.json').read_text())
    Draft202012Validator(schema).validate(draft)
    claims=[{k:c[k] for k in ('claim_id','kind','source_id','field','value','unit')} for c in draft['claims']]
    packet={'claims':claims,'sources':sources};validate_packet(packet)
    report=review(packet,engine)
    normalized={'scope':'Advisory checks of explicitly declared mappings only. Not whole-answer correctness.',
                'coverage':'Natural-language claim coverage and binding correctness unverified.',
                'answer_modified':False,'results':report['results'],
                'declared_claims':len(claims),'declared_recorded_claims':sum(c['kind']=='recorded' for c in claims),
                'declared_derived_claims':sum(c['kind']=='derived' for c in claims)}
    # Same selected evidence and unchanged draft in both second-pass conditions.
    shared={'question':None,'draft':draft,'selected_evidence':sources}
    return {'normalized_report':normalized,'raw_report':report,'shared':shared,
            'normalized_report_sha256':hashlib.sha256(canonical(normalized).encode()).hexdigest()}

def messages(question,draft,sources,condition='report',engine='python'):
    if not isinstance(question,str) or not question.strip():raise ValueError('question')
    if condition not in ('report','self_review'):raise ValueError('condition')
    prepared=prepare(draft,sources,engine)
    payload=prepared['shared'];payload['question']=question
    payload['review_report']=prepared['normalized_report'] if condition=='report' else None
    system='''Review the supplied draft using only the same selected evidence. A report, when supplied, is advisory and limited to declared mappings. You may retain, qualify or revise the answer based on evidence; do not treat a flag as compulsory rejection or a pass as truth. A missing report is a self-review control, not a failed check. Do not look up additional sources, invent bindings, silently convert units, or recommend physical process changes. Preserve unknowns and distinguish missing selected evidence from absence in the original source. Return the revision schema, including a revision_log for retained, changed, removed and added claims. Explain your reasons; the log itself is not independent verification.'''
    output=[{'role':'system','content':system},{'role':'user','content':canonical(payload)}]
    return {'messages':output,'response_schema':json.loads((ROOT/'revision-schema-v1.json').read_text()),
            'normalized_report_sha256':prepared['normalized_report_sha256'] if condition=='report' else None,
            'raw_report':prepared['raw_report'],'condition':condition,'model_calls':0,
            'state':'prepared messages only; no tokens, provider budget or execution authorized'}
