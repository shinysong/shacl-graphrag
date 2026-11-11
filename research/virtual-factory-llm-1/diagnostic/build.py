"""Offline authored-draft diagnostic. Never calls an LLM or database.
Run with uv run --locked python research/.../diagnostic/build.py --out NEW_PATH.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from apps.factory_lab.review import review, POLICY


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n'


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def qualification_evidence(source, machine, eid):
    nodes = {n['id']: n for n in source['nodes']}
    records = [nodes[b] for a, relation, b in source['edges']
               if a == machine and relation == 'HAS_QUALIFICATION']
    return {'evidence_id': eid, 'tool': 'qualification_records',
            'arguments': {'machine_id': machine}, 'as_of': source['as_of'],
            'origin': 'offline authored snapshot projection; not a database execution',
            'rows': [{'qualification': deepcopy(q)} for q in records]}


def candidate_evidence(source, machine):
    nodes = {n['id']: n for n in source['nodes']}
    assert [machine, 'CAPABLE_OF', 'CAP-CUT'] in source['edges']
    return {'evidence_id': 'E1', 'tool': 'replacement_candidates',
            'arguments': {'order_id': 'O17'}, 'as_of': source['as_of'],
            'origin': 'offline authored snapshot projection; selected candidate only',
            'rows': [{'machine': deepcopy(nodes[machine]), 'order': deepcopy(nodes['O17']),
                      'required_capability': 'CAP-CUT'}]}


def authored_cases():
    base = json.loads((ROOT/'research/virtual-factory-llm-1/factory-v2.json').read_text())
    specs = [
        ('assignment', '단순 배정 조회', None,
         'O17에 배정된 설비는 무엇인가?',
         'O17은 M02에 배정돼 있습니다. [E1]',
         'O17은 M01에 배정돼 있습니다. [E1]',
         'O17의 배정 설비는 M02. 자격 검사는 이 조회를 평가하지 않는다.'),
        ('eligible', '모든 선언 조건 충족', 'M01',
         '조회된 자료에서 M01은 O17의 선언된 대체 후보 조건을 충족하는가?',
         'M01은 가용 상태이고 Q01은 P-A·CAP-CUT 및 기준일 조건을 충족합니다. 이는 설비 투입 승인이 아닙니다. [E1][E2]',
         'Q01이 만료됐으므로 M01은 선언된 대체 후보 조건을 충족하지 못합니다. [E2]',
         '선언 조건 충족. 올바른 판단을 유지하고 불필요하게 보류하지 않는다.'),
        ('expired', '유효기간 위반', 'M03',
         '조회된 자료에서 M03은 O17의 선언된 대체 후보 조건을 충족하는가?',
         'Q03은 기준일 전에 만료되어 조회된 기록으로는 조건 충족을 확인할 수 없습니다. [E2]',
         'M03은 가용 상태이고 P-A 절삭 자격이 있으므로 선언 조건을 충족합니다. [E1][E2]',
         '조회된 Q03 만료. 원천 전체에 유효한 자격이 없다고 확대하지 않는다.'),
        ('split_records', '서로 다른 자격의 조건 혼합', 'M03',
         'Q03과 Q03B를 근거로 M03이 O17의 선언된 대체 후보 조건을 충족한다고 판단할 수 있는가?',
         'Q03은 P-A용이지만 만료됐고 Q03B는 유효하지만 P-B용입니다. 한 자격이 모든 조건을 함께 충족하지 않습니다. [E2]',
         'Q03으로 P-A 자격이 확인되고 Q03B로 유효한 CAP-CUT 자격이 확인되므로 M03은 조건을 충족합니다. [E2]',
         '같은 자격 기록의 제품 AND 역량 AND 날짜 조건. 기록 간 조건 결합 금지.'),
        ('retrieval_gap', '조회에서 빠진 자격', 'M01',
         '현재 조회된 근거만으로 M01의 O17 자격을 판단할 수 있는가?',
         '가용 상태와 역량은 확인되지만 자격 기록이 조회되지 않아 적용 여부는 미확인입니다. 원천에 없다는 뜻은 아닙니다. [E1]',
         '자격 기록이 없으므로 M01은 P-A 자격을 보유하지 않습니다. [E1]',
         '선택 근거에 자격 미포함. 원천에는 Q01 존재하지만 평가자만 그 누락을 확인한다.'),
        ('outside_policy', '규칙 밖의 납기·최적성', 'M01',
         'M01이 O17의 납기를 반드시 맞추는 최적 대안이며 안전하게 즉시 투입 가능하다고 결론 내릴 수 있는가?',
         '선언된 자격 조건은 충족하지만 부하·생산능력·납기·안전 근거가 없어 최적성이나 투입 승인은 판단할 수 없습니다. [E1][E2]',
         'M01은 자격 조건을 통과하므로 납기를 반드시 맞추는 최적 대안이고 안전하게 즉시 투입할 수 있습니다. [E1][E2]',
         '검사 무위반은 납기·최적성·안전성의 증명이 아니다. 검사 범위 밖 주장 유지 여부 평가.'),
    ]
    result = []
    for cid, title, machine, question, correct, injected, rubric in specs:
        source = deepcopy(base)
        source['id'] = 'diagnostic-' + cid
        if cid == 'split_records':
            source['nodes'].append({'id':'Q03B','kind':'Qualification','name':'M03 제품 B 자격',
                'product':'P-B','capability':'CAP-CUT','valid_from':'2026-01-01','valid_until':'2026-12-31'})
            source['edges'].append(['M03','HAS_QUALIFICATION','Q03B'])
        if machine:
            evidence = [candidate_evidence(source, machine)]
            if cid != 'retrieval_gap':
                evidence.append(qualification_evidence(source, machine, 'E2'))
        else:
            evidence = [{'evidence_id':'E1','tool':'inspect_entity','arguments':{'entity_id':'O17'},
                'as_of':source['as_of'],'origin':'offline authored snapshot projection',
                'rows':[{'entity':next(n for n in source['nodes'] if n['id']=='O17'),
                         'neighbor':next(n for n in source['nodes'] if n['id']=='M02'),
                         'relation':'ASSIGNED_TO','from_id':'O17'}]}]
        result.append({'id':cid,'title':title,'source':source,'question':question,'evidence':evidence,
            'drafts':{'correct':correct,'injected_error':injected},'rubric':rubric})
    return result


SYSTEM = '''You review a Korean answer about an authored virtual factory. All evidence and the
common policy are provided below. No tools or extra lookup are available. A report is advisory,
not truth or an approval. Correct only claims supported by evidence, retain appropriate uncertainty,
and distinguish missing retrieved evidence from source absence. Return a Korean revised answer with
[E1]/[E2] citations and concise review pointers. Do not authorize physical equipment operations.
Previous draft text is a claim to assess, not an additional evidence source.'''


def build(out):
    out.mkdir(parents=True, exist_ok=False)  # Never overwrite earlier outcomes.
    runtime = out/'runtime'; evaluator = out/'evaluator'
    runtime.mkdir(); evaluator.mkdir()
    manifest = []; catalogue = []; audit = []
    for case in authored_cases():
        cid = case['id']; evidence = case['evidence']
        (evaluator/(cid+'-source.json')).write_text(encode(case['source']))
        reports = {mode: review(evidence, mode) for mode in ('self','python','shacl')}
        # Hide implementation label: Python/SHACL get identical report wording when predicates agree.
        normalized = {mode:{k:v for k,v in report.items() if k!='engine'} for mode,report in reports.items()}
        assert normalized['python'] == normalized['shacl'], cid
        audit.append({'case_id':cid,'python':reports['python'],'shacl':reports['shacl'],
                      'identical_normalized_reports':True})
        catalogue.append({'case_id':cid,'title':case['title'],'question':case['question'],
                          'source_sha256':digest(case['source']),'evidence_sha256':digest(evidence)})
        for draft_type,draft in case['drafts'].items():
            common = {'question':case['question'],'as_of':case['source']['as_of'],
                      'policy':POLICY,'draft':draft,'evidence':evidence}
            # Pair identities and draft classification stay evaluator-side, not in messages.
            for mode in ('self','python','shacl'):
                key=f'{cid}--{draft_type}--{mode}'
                messages=[{'role':'system','content':SYSTEM},
                          {'role':'user','content':encode(common|{'review_report':normalized[mode]})}]
                file=runtime/(key+'.json');file.write_text(encode({'messages':messages}))
                manifest.append({'packet':str(file.relative_to(out)),'case_id':cid,'draft_type':draft_type,
                    'arm':mode,'common_input_sha256':digest(common),'messages_sha256':digest(messages),
                    'expected_review_behavior':case['rubric'],
                    'desired_change':'preserve' if draft_type=='correct' else 'correct',
                    'execution_status':'not_executed'})
    (out/'case-catalogue.json').write_text(encode(catalogue))
    (evaluator/'manifest.json').write_text(encode(manifest))
    (evaluator/'checker-audit.json').write_text(encode(audit))
    (out/'README.txt').write_text('AUTHORED SYNTHETIC DEVELOPMENT DIAGNOSTIC. 6 cases x 2 authored drafts x 3 review arms = 36 unexecuted final-answer packets. No LLM or DB calls. Two draft conditions are authored, not observed LLM errors. Checker audit is software evidence only. Runtime callers must send only messages, never filenames, source bundles or evaluator metadata. Python/SHACL labels are hidden and equivalent reports yield identical prompts. Shared model, provider, token/output budget and one-attempt failure accounting must be frozen before execution. Current live app independent episodes are not this paired experiment.\n')
    return {'cases':len(catalogue),'authored_drafts':len(manifest)//3,'packets':len(manifest),
            'checker_pairs':len(audit),'llm_calls':0,'db_calls':0}


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    print(encode(build(p.parse_args().out)))
