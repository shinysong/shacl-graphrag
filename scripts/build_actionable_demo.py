"""Export verified saved records; no runtime, inference or experimental API calls."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT/'research/actionable-evidence-1'
DEST = ROOT/'docs/experiments/actionable-evidence-demo'
ARMS = [('direct_local_candidate','한 단계 참조'),
        ('matched_Python_relation_candidate','관계 조회 Python'),
        ('SHACL_AF_relation_candidate','SHACL-AF 규칙')]
POST = [('no_postcheck','검사 결과를 보류에 미반영'),('shadow_revalidation','검사 위반 시 보류')]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def build():
    run=STUDY/'runs/run-001'
    freeze, completion=load(run/'freeze.json'),load(run/'completion.json')
    assert completion['rows']==completion['expected_rows']==192
    assert completion['failures']==0 and not completion['changed_inputs']
    with zipfile.ZipFile(run/'frozen-inputs.zip') as archive:
        for relative, expected in freeze['hashes'].items():
            assert digest(ROOT/relative)==expected, f'Changed frozen input: {relative}'
            assert hashlib.sha256(archive.read(relative)).hexdigest()==expected
    rows=[json.loads(s) for s in (run/'outputs.jsonl').read_text().splitlines()]
    expected={(f'c{i:03d}',a,p) for i in range(32) for a,_ in ARMS for p,_ in POST}
    keys=[(r['case_id'],r['arm'],r['postcheck']) for r in rows]
    assert len(keys)==192 and len(set(keys))==192 and set(keys)==expected
    indexed={k:r for k,r in zip(keys,rows)}
    for (cid,arm,post),row in indexed.items():
        assert row['status']=='ok' and row['exit_code']==0
        result=row['result']; data=load(STUDY/f'fixtures/runtime/{cid}.json')
        raw_hash=digest(STUDY/f'fixtures/runtime/{cid}.json')
        canonical=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        assert row['input_sha256']==result['input_file_sha256']==raw_hash
        assert result['input_sha256']==canonical
        assert result['arm']==arm and result['postcheck']==post and result['status']=='ok'
        assert result['original_unchanged'] is True
        assert result['disposition'] in ('propose_patch','request_evidence','request_reconciliation')
        for field in ('candidate_reference_ids','candidate_citations','diff'):
            assert type(result[field]) is list
        assert len(result['candidate_reference_ids'])==len(result['candidate_citations'])
        if result['candidate_patch'] is not None:
            assert set(result['candidate_patch'])=={'target','field','old','new'}
            assert result['candidate_patch']['target']==data['target']['id']
            assert result['candidate_patch']['field']==data['target']['field']
            assert result['candidate_patch']['old']==data['target']['value']
        for field in ('before_report','after_report'):
            if result[field] is not None:
                assert type(result[field]['shacl']['conforms']) is bool
                assert type(result[field]['shacl']['results']) is list
        assert load(run/f'{cid}-{arm}-{post}.stdout.txt')==result
    source_path=STUDY/'source/penelope-annotations.json'
    source=load(source_path)
    selected={r['id']:r for r in source['rows'] if r['id'] in ('PP5:25','PP7:10')}
    assert len(source['rows'])==243 and len(selected)==2
    assert selected['PP5:25']['values']['x_init_mm']==177
    assert selected['PP5:25']['values']['x_end_mm']==160
    assert selected['PP7:10']['values']['welding_setting']==1
    assert selected['PP7:10']['design_expected_setting_code']==2
    cases=[]
    for cid,label,question,request in [
        ('PP5:25','실제 자료 · 구간 방향 확인','PP5의 주석 구간을 그대로 사용해도 될까요?',
         dict(title='구간 방향과 원래 주석 확인',reason='시작점이 끝점 이하라는 계약에서는 위치·샘플 구간이 확인 대상입니다. 역순이라는 사실만으로 오타를 확정할 수 없습니다.',
              items=['PP5!D25:E25의 177→160 mm 방향을 확인합니다.','PP5!F25:G25의 73717→66637 샘플 구간과 원래 주석을 확인합니다.'],
              forbidden=['두 끝점을 임의로 바꾸지 않습니다.','용접 결함의 원인이나 재작업 방법을 단정하지 않습니다.'])),
        ('PP7:10','실제 자료 · 설정 문서 대조','PP7 비드 2의 설정을 어느 기록으로 확인해야 할까요?',
         dict(title='실제 적용 설정과 설계 적용 범위 확인',reason='주석은 설정 1을 가리키며 해당 설계 문서의 비드 2는 설정 2에 대응합니다. 어느 기록이 맞는지는 이 자료만으로 확정할 수 없습니다.',
              items=['실제 적용 설정과 예외 승인 기록을 요청합니다.','설계 문서의 적용 시점과 버전을 확인합니다.','주석 코드의 명목 설정은 450 A, 설계 대응 설정은 550 A입니다. 실제 측정 전류를 확인한 것은 아닙니다.'],
              forbidden=['주석을 설계값으로 자동 덮어쓰지 않습니다.','전류를 550 A로 바꾸라는 공정 명령을 내리지 않습니다.']))]:
        row=selected[cid]; file=next(f for f in source['files'] if f['coupon']==row['coupon'])
        relations=[dict(from_=cid,relation='주석의 비드',to=str(row['values']['bead'])),
                   dict(from_=cid,relation='기록된 설정 코드',to=str(row['values']['welding_setting']))]
        relations=[{'from':r.pop('from_'),**r} for r in relations]
        if cid=='PP7:10':
            relations.append({'from':'설계 PDF · 비드 2','relation':'명목 설정의 대응','to':'설정 코드 2'})
        provenance=[dict(label='원본 Excel',locator=f"{row['archive_path']} · {row['sheet']}!{row['cell_range']}",sha256=file['sha256'],url=source['source']['url'])]
        if cid=='PP7:10':
            pdf=next(f for f in source['design_files'] if '/PP7/' in f['archive_path'])
            provenance.append(dict(label='설계 문서',locator=row['design_provenance'],sha256=pdf['sha256'],url=source['source']['url']))
        cases.append(dict(id=cid,kind='real_audit',label=label,question=question,
             note='실제 자료의 기술적 점검입니다. 아래 요청은 연구자가 작성했으며 SHACL 실행 결과나 공식 수정 지침이 아닙니다.',
             input=row,relations=relations,provenance=provenance,request=request))
    scorer={r['case_id']:r for r in load(STUDY/'fixtures/scorer.json')}
    labels={'c008':'합성 사례 · 근거가 있는 복원','c015':'합성 사례 · 의존 조건 위반',
            'c014':'합성 사례 · 검사를 통과한 거짓 근거','c009':'합성 사례 · 근거 부족'}
    for cid,label in labels.items():
        data=load(STUDY/f'fixtures/runtime/{cid}.json')
        outputs={a+'|'+p:indexed[(cid,a,p)]['result'] for a,_ in ARMS for p,_ in POST}
        refs={n['id']:n for n in data['nodes']}
        relations=[{'from':e['from'],'relation':'참조 관계','to':e['to']} for e in data['edges']]
        for n in refs.values():
            if n['type']=='Reference':
                relations.append({'from':n['id'],'relation':'참조값 · 출처','to':f"{n['value']} · {n['citation']}"})
        case=dict(id=cid,kind='synthetic_replay',label=label,
            question='누락된 추출 필드에 참조값을 제안해도 될까요?',
            note='연구자가 작성한 개발 사례의 저장된 실행입니다. setting은 합성 설정 코드이며 실제 공정 변경값이 아닙니다.',
            input=data,runtime=data,outputs=outputs,evaluation=scorer[cid],relations=relations,
            provenance=[dict(label='합성 입력',locator=f'fixtures/runtime/{cid}.json',sha256=digest(STUDY/f'fixtures/runtime/{cid}.json')),
                        dict(label='저장된 전체 실행 출력',locator='runs/run-001/outputs.jsonl',sha256=digest(run/'outputs.jsonl'))])
        if cid=='c009':
            assert (STUDY/'fixtures/runtime/c009.json').read_bytes()==(STUDY/'fixtures/runtime/c010.json').read_bytes()
            case['paired_missing_case']=dict(id='c010',same_runtime_bytes=True,
                note='원천 누락과 검색 누락의 평가 라벨은 다르지만 보이는 입력은 같습니다. 실행기는 두 원인을 구분하지 않습니다.')
        cases.append(case)
    inputs=[source_path,run/'outputs.jsonl',run/'evaluation.json',run/'freeze.json',STUDY/'fixtures/scorer.json',STUDY/'demo-contract.md',Path(__file__)]
    data=dict(study='actionable-evidence-1',mode='offline_saved_execution_replay',
              source_attribution=source['source'],arms=[dict(id=a,label=b) for a,b in ARMS],
              postchecks=[dict(id=a,label=b) for a,b in POST],cases=cases,
              provenance={str(p.relative_to(ROOT)):digest(p) for p in inputs},
              verification=dict(full_grid_rows=192,selected_real_cases=2,selected_synthetic_cases=4,selected_saved_outputs=24,live_execution=False,api_calls=0))
    DEST.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(data,ensure_ascii=False,indent=2)+'\n'
    (DEST/'demo.json').write_text(raw)
    (DEST/'data.js').write_text('window.ACTIONABLE_DEMO = '+raw.rstrip()+';\n')
    for f in ('Pretendard-Regular.woff2','OFL.txt'):
        shutil.copyfile(ROOT/'docs/experiments/seminar'/f,DEST/f)
    # Derivative display manifest, not a claim of original cryptographic authentication.
    artifacts=['demo.json','data.js','Pretendard-Regular.woff2','OFL.txt']
    artifacts += [f for f in ('index.html','style.css','app.js') if (DEST/f).exists()]
    (DEST/'build-manifest.json').write_text(json.dumps(dict(inputs=data['provenance'],
         outputs={f:digest(DEST/f) for f in artifacts},
         verification=data['verification']),indent=2)+'\n')
    print(json.dumps(data['verification']))


if __name__=='__main__':
    build()
