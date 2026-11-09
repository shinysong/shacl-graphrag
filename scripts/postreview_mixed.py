"""Candidate v2: declared atomic and lookup claims, with explicit scope limits."""
import hashlib,json
from pathlib import Path
from jsonschema import Draft202012Validator
from scripts.post_answer_review import review,token
from scripts.postreview_lookup import review_lookup,validate_sources
from scripts.postreview_messages import canonical
ROOT=Path('research/post-answer-review-1')
HEADERS={'x_init_mm':('x_init [mm]','mm'),'x_end_mm':('x_end [mm]','mm'),
         'sample_init':('x_init [# sample]','# sample'),'sample_end':('x_end [# sample]','# sample')}

def direct_sources(sources):
    result=[]
    for sid,node in validate_sources(sources).items():
        fields={};values=node.get('values',{})
        if not isinstance(values,(dict,list)):raise ValueError('source values container')
        if not isinstance(values,dict):
            result.append({'source_id':sid,'fields':fields});continue
        for key,value in values.items():
            if not isinstance(key,str) or not key.strip():raise ValueError('source field')
            token(value);address=node.get('field_cells',{}).get(key)
            cells=[c for c in node['cells'] if c['cell']==address]
            if len(cells)!=1 or cells[0].get('formula') is not None:continue
            if token(cells[0]['value'])!=token(value):raise ValueError('source value/cell mismatch')
            unit=None
            if key in HEADERS:
                expected,candidate=HEADERS[key];headers=[c for row in node['header_rows'] for c in row['cells'] if c.get('value')==expected and c.get('formula') is None]
                # Same column as the bound cell; no fuzzy header inference.
                column=''.join(x for x in address if x.isalpha())
                if any(''.join(x for x in c['cell'] if x.isalpha())==column for c in headers):unit=candidate
            fields[key]={'value':value,'unit':unit,'locator':f"{node['archive_path']} | {node['sheet']} | {address}"}
        result.append({'source_id':sid,'fields':fields})
    return result

def mixed_review(draft,sources,engine='python'):
    if engine not in ('python','pyshacl'):raise ValueError('engine')
    Draft202012Validator(json.loads((ROOT/'draft-schema-v2.json').read_text())).validate(draft)
    ids=[c['claim_id'] for c in draft['claims']]
    if len(ids)!=len(set(ids)) or any(not x.strip() for x in ids):raise ValueError('claim IDs')
    direct=direct_sources(sources);results=[];raw=[]
    for c in draft['claims']:
        kind=c['kind']
        if any(c[k] is not None and not c[k].strip() for k in ('source_id','field','anchor_id','dictionary_id','lookup_kind')):raise ValueError('blank binding')
        if kind=='lookup':
            if c['source_id'] is not None or c['field'] is not None:raise ValueError('unused direct binding')
            # Missing lookup declarations are unknown, not inferred from question.
            if any(c[k] is None for k in ('lookup_kind','anchor_id','dictionary_id')):
                results.append({'claim_id':c['claim_id'],'kind':kind,'check_id':'lookup_declaration','status':'unknown','reason':'incomplete_model_declaration'});continue
            report=review_lookup({k:c[k] for k in ('claim_id','lookup_kind','anchor_id','dictionary_id','value','unit')},sources,engine);raw.append(report)
            results.extend({'claim_id':c['claim_id'],'kind':kind,**r} for r in report['results'])
        elif kind=='recorded':
            if any(c[k] is not None for k in ('anchor_id','dictionary_id','lookup_kind')):raise ValueError('unused lookup binding')
            packet={'claims':[{k:c[k] for k in ('claim_id','kind','source_id','field','value','unit')}],'sources':direct}
            report=review(packet,engine);raw.append(report);results.extend({'kind':kind,**r} for r in report['results'])
        else:
            if any(c[k] is not None for k in ('source_id','field','anchor_id','dictionary_id','lookup_kind')):raise ValueError('derived binding unsupported')
            token(c['value']);results.append({'claim_id':c['claim_id'],'kind':kind,'check_id':'declared_scope','status':'not_applicable','reason':'derived_claim_outside_supported_policy'})
    normalized={'schema':'postreview-normalized-v2','scope':'advisory declared mappings only; no whole-answer pass',
                'coverage':'Natural-language coverage, correct claim kind, question interpretation and external truth unverified.',
                'declared_claim_count':len(ids),'results':results,'answer_modified':False}
    return {'normalized_report':normalized,'normalized_report_sha256':hashlib.sha256(canonical(normalized).encode()).hexdigest(),'raw_reports':raw,'engine':engine}

def prepare_messages(question,draft,sources,condition='report',engine='python'):
    if not isinstance(question,str) or not question.strip() or condition not in ('self_review','report'):raise ValueError('message condition')
    if engine not in ('python','pyshacl'):raise ValueError('engine')
    # Common response-format admission, but no checker dependency for self-review.
    # Binding/coverage errors are outcomes for the advisory arm, not reasons to
    # silently remove its otherwise schema-valid self-review counterpart.
    Draft202012Validator(json.loads((ROOT/'draft-schema-v2.json').read_text())).validate(draft)
    reviewed=mixed_review(draft,sources,engine) if condition=='report' else None
    system=(ROOT/'draft-system-v2.txt').read_text()+'''\nReview the supplied unchanged draft using the same selected evidence. A report, if present, is advisory. With no report, perform self-review on the same evidence. Retain, qualify or revise only as justified by that evidence; do not add source lookup or automatically veto flagged answers. Include revision_log for retained/changed/removed/added claims with reasons. Neither your log nor conformance is independent verification.\n'''
    payload={'question':question,'draft':draft,'selected_evidence':sources,'review_report':reviewed['normalized_report'] if reviewed else None}
    return {'messages':[{'role':'system','content':system},{'role':'user','content':canonical(payload)}],
            'response_schema':json.loads((ROOT/'revision-schema-v2.json').read_text()),'review_artifact':reviewed,
            'state':'offline candidate only; no provider, token budget or paid launch verified'}
