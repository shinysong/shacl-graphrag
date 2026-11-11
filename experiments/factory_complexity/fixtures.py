"""Author reproducible development cells; evaluator metadata never enters prompts."""
import copy
import hashlib
import json
from pathlib import Path
from apps.factory_lab.graph import snapshot
from apps.factory_lab.evidence import canonical

QUESTIONS = {
 'Q1': 'M02가 멈춰 O17의 대체 설비를 찾고 있어. M01과 M03을 제품·작업·자격 기간까지 비교해줘. 현장에서는 M01 일정이 비었다고 하지만 확인된 건 아니야. 지금 판단 가능한 것과 담당자가 추가 확인할 것을 나눠줘. 실제 배정은 바꾸지 마.',
 'Q2': 'M03 자격이 갱신됐다는 말을 들었어. 현재 기록으로 O17과 O18을 모두 대신 맡길 수 있는지 각각 검토하고, 기존 자격과 갱신 자격을 구분해줘. 납기나 승인까지 확인된 것처럼 말하지 말고 누가 무엇을 확인해야 하는지 알려줘. 실제 배정은 바꾸지 마.',
 'Q3': 'M02 중단의 영향 주문 목록을 이전 버전과 현재 버전에서 비교해줘. O20도 새로 연결됐다는 얘기가 있는데 확인해주고, 기존 주문의 근거가 같아도 재검토가 필요한지 설명해줘. 일정과 납기는 별도 확인이 필요해. 확인 가능한 범위를 밝히고 실제 배정은 바꾸지 마.',
 'Q4': 'M01에 여러 자격 기록이 있으니 합치면 O18도 가능하다는 얘기를 들었어. O17과 O18에 각각 쓸 수 있는지 제품·작업·기간이 한 기록에서 함께 충족되는지 확인하고 M03과 비교해줘. 일정과 승인에 관한 추측은 구분하고 담당자 확인 사항을 알려줘. 실제 배정은 바꾸지 마.'}


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def drop(source, ident):
    result=copy.deepcopy(source)
    result['nodes']=[n for n in result['nodes'] if n['id']!=ident]
    result['edges']=[e for e in result['edges'] if ident not in (e[0],e[2])]
    return result


def base(version):
    data=copy.deepcopy(snapshot(version)[0])
    # Uniform metadata; do not leak the authored target through event descriptions.
    data.pop('event',None)
    data['source_scope']='Authored synthetic snapshot, not the physical factory.'
    return data


def make_case(family,state):
    if family not in QUESTIONS or state not in ('C','A','O'):raise ValueError('Unknown cell')
    before=base('factory-v2');current=base('factory-v3')
    target={'Q1':'Q01','Q2':'Q03R','Q3':'O20','Q4':'Q01B'}[family]
    if family=='Q3':
        current['nodes'].append({'id':'O20','kind':'Order','name':'제품 A 추가 주문','product':'P-A'})
        current['edges'] += [['O20','ASSIGNED_TO','M02'],['O20','REQUIRES','CAP-CUT']]
    if family=='Q4':
        for ident,product,capability,until in (
            ('Q01X','P-B','CAP-INSPECT','2026-12-31'),
            ('Q01Y','P-B','CAP-CUT','2026-10-31'),
            ('Q01B','P-B','CAP-CUT','2026-12-31')):
            current['nodes'].append({'id':ident,'kind':'Qualification','name':ident+' 자격 기록',
                'product':product,'capability':capability,'valid_from':'2026-01-01','valid_until':until})
            current['edges'].append(['M01','HAS_QUALIFICATION',ident])
    if state=='A':current=drop(current,target)
    view=drop(current,target) if state=='O' else copy.deepcopy(current)
    return {'question':QUESTIONS[family],'sources':{'factory-v2':before,'factory-v3':current},
            'views':{'factory-v2':copy.deepcopy(before),'factory-v3':view},
            'evaluation':{'family':family,'state':state,'target':target,
                'source_target_present':state!='A','view_target_present':state=='C',
                'cohort':'authored consumed-development-informed; not fresh held-out'}}


def write_cases(directory):
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=False)
    catalog=[]
    for index,(family,state) in enumerate((f,s) for f in QUESTIONS for s in ('C','A','O')):
        case=make_case(family,state);opaque=f'case-{index+1:02d}'
        runtime=directory/'runtime'/opaque;runtime.mkdir(parents=True)
        evaluator=directory/'evaluation'/opaque;evaluator.mkdir(parents=True)
        manifest={'current':'factory-v3','question':case['question'],'versions':{}}
        for version in case['sources']:
            source,view=case['sources'][version],case['views'][version]
            (runtime/(version+'.json')).write_text(canonical(view)+'\n')
            (evaluator/(version+'.json')).write_text(canonical(source)+'\n')
            manifest['versions'][version]={'source_sha256':digest(source),'view_sha256':digest(view)}
        (runtime/'manifest.json').write_text(canonical(manifest)+'\n')
        (evaluator/'labels.json').write_text(canonical(case['evaluation'])+'\n')
        catalog.append({'id':opaque,**case['evaluation']})
    (directory/'evaluation'/'catalog.json').write_text(canonical(catalog)+'\n')
    return catalog
