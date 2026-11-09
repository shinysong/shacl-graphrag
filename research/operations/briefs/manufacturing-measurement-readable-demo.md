Offline UI v2: preserve priorv1; requirecompleted artifacts andparsedcontract binding, readable exactbasis/pointers/4fields withnull/booleanlabel,rawtexttoggle,citationsnotcertified. No answerchanges/DB/API. Rawrunomittedunverified. Review<=200words.

## check.py
```
import tempfile,shutil,json
from pathlib import Path
import build
root=Path('research/manufacturing-measurement-1/answer-001')
x=build.bundle(root);assert len(x['rows'])==18 and x['summary']['reported_cost_usd']=='0.646692400'
with tempfile.TemporaryDirectory() as td:
 p=Path(td)/'run';shutil.copytree(root,p)
 (p/'responses/000.request.json').unlink()
 try:build.bundle(p)
 except ValueError as e:assert str(e)=='completed_artifacts_missing'
 else:raise AssertionError('missing artifact allowed')
 shutil.copy2(root/'responses/000.request.json',p/'responses/000.request.json')
 q=p/'responses/000.result.json';r=json.loads(q.read_text());r['contract']['nominal_idc_a']=999;q.write_text(json.dumps(r))
 try:build.bundle(p)
 except ValueError as e:assert str(e)=='contract_binding'
 else:raise AssertionError('changed contract allowed')
print('saved18 and missingcompleted artifact/changedcontract controls passed')

```

## build.py
```
"""Offline replay builder; reads saved artifacts only, never calls a model or DB."""
import json,hashlib
from pathlib import Path
from decimal import Decimal
ARMS={'draft','self_review','shacl_review'}
def bundle(run):
 run=Path(run);plan=json.loads((run/'plan.json').read_text());states=json.loads((run/'states.json').read_text());providers=json.loads((run/'providers.json').read_text());models=[p['model'] for p in providers]
 expected={(m,a) for m in models for a in ARMS}
 if len(models)!=6 or len(set(models))!=6 or len(plan)!=18 or len(states)!=18 or {(r['model'],r['arm']) for r in plan}!=expected:raise ValueError('plan_universe')
 rows=[]
 for i,(slot,state) in enumerate(zip(plan,states)):
  if any(slot[k]!=state.get(k) for k in ('id','model','arm')):raise ValueError('state_binding')
  row={k:state[k] for k in ('id','model','arm','state')};prefix=run/'responses'/f'{i:03d}'
  if state['state']=='completed' and not all(prefix.with_suffix(suffix).is_file() for suffix in ('.request.json','.raw.txt','.result.json')):raise ValueError('completed_artifacts_missing')
  if prefix.with_suffix('.request.json').exists():
   req=json.loads(prefix.with_suffix('.request.json').read_text())
   if req['model']!=slot['model']:raise ValueError('request_binding')
  if prefix.with_suffix('.result.json').exists():
   r=json.loads(prefix.with_suffix('.result.json').read_text());raw=json.loads(prefix.with_suffix('.raw.txt').read_text())
   if raw['model']!=slot['model'] or r['status']!=state['state']:raise ValueError('response_binding')
   if r['status']=='completed' and json.loads(raw['choices'][0]['message']['content'])!=r['contract']:raise ValueError('contract_binding')
   row.update(visible_text=raw['choices'][0]['message'].get('content'),reported_usd=r['reported_usd'],finish_reason=r['finish_reason'])
  if prefix.with_suffix('.advisory.json').exists():row['advisory']=json.loads(prefix.with_suffix('.advisory.json').read_text())
  rows.append(row)
 diagnosis=json.loads(Path('research/manufacturing-measurement-1/diagnostic-001/diagnostic.json').read_text())
 return {'models':models,'rows':rows,'diagnostic':diagnosis,'summary':{'planned':18,'states':{s:sum(r['state']==s for r in rows) for s in sorted({r['state'] for r in rows})},'reported_cost_usd':str(sum((Decimal(r.get('reported_usd','0')) for r in rows),Decimal(0))),'source_run':str(run),'source_plan_sha256':hashlib.sha256((run/'plan.json').read_bytes()).hexdigest(),'native_tokenizer_measured':False,'four_field_score_is_not_whole_answer_truth':True}}
def build(run,out):
 data=bundle(run);template=Path(__file__).with_name('template.html').read_text()
 if template.count('__BUNDLE__')!=1:raise ValueError('template_marker')
 encoded=json.dumps(data,ensure_ascii=False).replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e')
 out=Path(out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(template.replace('__BUNDLE__',encoded));return data
if __name__=='__main__':
 import sys
 print(build(sys.argv[1],sys.argv[2])['summary'])

```

## template.html
```
<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>제조 측정 근거와 답변 검토</title>
<style>:root{color-scheme:light dark;--bg:#f3f6fa;--card:#fff;--ink:#17283e;--line:#c6d3df;--accent:#175481}@media(prefers-color-scheme:dark){:root{--bg:#121a24;--card:#1c2939;--ink:#edf3fa;--line:#4a6178;--accent:#94cefa}}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 system-ui,sans-serif}main{max-width:1200px;margin:auto;padding:24px}h1{font-size:clamp(24px,4vw,36px);line-height:1.3}h2{font-size:21px}h3{font-size:18px}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px;margin:16px 0}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.grid .card{margin:0}.flow{display:grid;grid-template-columns:1fr auto 1fr auto 1fr;gap:8px;align-items:center}.flow b{border:1px solid var(--line);padding:14px;border-radius:8px;text-align:center}.flow span{text-align:center}select,button{font:inherit;max-width:100%;padding:8px;background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:6px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.6 ui-monospace,monospace;max-height:480px;overflow:auto}p,li,td{overflow-wrap:anywhere}a{color:var(--accent)}.badge{display:inline-block;border:1px solid var(--line);padding:2px 10px;border-radius:20px;font-size:14px}.metric{font-size:26px;font-weight:700}.muted{font-size:14px}dt{font-weight:700;margin-top:10px}dd{margin-left:0}.note{border-left:4px solid var(--accent);padding-left:14px}table{width:100%;border-collapse:collapse}td,th{text-align:left;border-bottom:1px solid var(--line);padding:7px;font-size:14px}@media(max-width:750px){main{padding:16px}.grid{grid-template-columns:1fr}.flow{grid-template-columns:1fr}.flow span{transform:rotate(90deg)}}
</style><main>
<p class="badge">제조 사례 · 저장된 결과 재생 · DB/LLM 호출 없음</p>
<h1>측정 채널이 있어도<br>결함 구간의 값으로 확정할 수는 없다</h1>
<p>PP6 작업표 2행의 명목값, 측정 채널, 검증된 구간 평균, 적용 문서 버전을 나눠 판단한다. 원자료를 추가한 효과와 동일 근거에 검토 보고서를 더한 효과는 별도다.</p>
<section class="card"><h2>원자료와 연결 규약</h2><div class="flow"><b>작업표·코드북<br>명목 Idc 450 A</b><span>→</span><b>좌표·인덱스·파일 대응<br>현재 미검증</b><span>←</span><b>HDF5 측정 채널<br>current_a · 530,304행</b></div><p class="note">조건부 구간 계산값 약 456.76–456.78 A는 어느 가정도 선택하지 않은 산술 결과다. 이를 검증된 결함 구간 전류나 결함 원인으로 읽지 않는다.</p><details><summary>6개 진단과 원자료 출처</summary><pre id="diagnostic"></pre></details></section>
<section class="card"><h2>같은 초안의 두 검토</h2><p>모델별 최초 초안을 그대로 두고 자체 검토와 SHACL 보고서 검토를 각각 실행한다. 두 검토의 원자료·운영 정책은 같다. SHACL은 검증된 구간 평균 주장과 문서 버전 주장에 관한 두 조건만 검사하며, 답을 강제로 바꾸지 않는다.</p><label for="model">모델 </label><select id="model"></select><p id="scope" class="muted"></p></section>
<div class="grid" id="answers"></div>
<section class="card"><h2>검토 보고서와 평가 범위</h2><p class="note">보고서에 표시가 없어도 답 전체가 맞다는 뜻은 아니다. 명목값, 인용 내용, 자유 서술과 물리적 진실은 이 두 조건의 검사 대상이 아니다. 같은 정책의 Python 검사와 SHACL 표시도 대조했다.</p><pre id="advisory"></pre><details><summary>실행 상태·비용·평가 기록</summary><pre id="run"></pre></details></section>
<section class="card"><h2>이 사례로 말할 수 있는 범위</h2><p>사전에 살펴본 개발 질문 하나를 6개 모델에서 한 번씩 실행한 진단이다. 18회는 독립적인 질문 표본 18개가 아니다. 모델 순위나 일반적인 SHACL 개선 효과로 해석하지 않는다. 구조화된 4개 필드의 일치와 실제 설명·인용의 검토는 구분한다.</p><p><a href="../../journal/2026-11-07-welding-measurement-boundaries/">측정 자료의 연결 조건</a> · <a href="https://doi.org/10.5281/zenodo.15083865">원자료: Tapia Suárez 등, CC BY 4.0</a></p></section>
</main><script id="data" type="application/json">__BUNDLE__</script><script>
'use strict';const D=JSON.parse(document.getElementById('data').textContent);const names={draft:'최초 초안',self_review:'자체 검토',shacl_review:'SHACL 보고서 검토'};const sel=document.getElementById('model');D.models.forEach(m=>{const o=document.createElement('option');o.value=m;o.textContent=m;sel.append(o)});document.getElementById('diagnostic').textContent=JSON.stringify(D.diagnostic,null,2);document.getElementById('run').textContent=JSON.stringify(D.summary,null,2);
function node(tag,text){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n}
function paint(){
 const m=sel.value;document.getElementById('answers').replaceChildren();
 for(const arm of ['draft','self_review','shacl_review']){
  const r=D.rows.find(x=>x.model===m&&x.arm===arm),card=node('article');card.className='card';card.append(node('h3',names[arm]));const badge=node('p',r.state);badge.className='badge';card.append(badge);
  if(r.state==='completed'){
   try{
    const answer=JSON.parse(r.visible_text),fields=node('dl');
    for(const [key,label] of [['nominal_idc_a','명목 Idc (A)'],['recorded_current_channel','기록된 전류 채널'],['verified_defect_interval_mean_a','검증된 구간 평균 (A)'],['applicable_document_version','적용 검토 문서 버전']]){
     const v=answer[key];fields.append(node('dt',label),node('dd',v===null?'미확인 (null)':typeof v==='boolean'?(v?'있음 (true)':'없음 (false)'):String(v)));
    }
    card.append(fields,node('h4','답변의 설명'));const basis=node('p',answer.basis);basis.className='answer-basis';card.append(basis,node('h4','확인할 항목'));const pointers=node('ul');pointers.className='answer-pointers';for(const p of answer.review_pointers)pointers.append(node('li',p));card.append(pointers);
    const cites=node('details');cites.append(node('summary','모델이 붙인 인용'));const list=node('ul');for(const c of answer.citations)list.append(node('li',c.source_id+' — '+c.claim));cites.append(list);card.append(cites);
   }catch(error){card.append(node('p','읽기용 표시를 만들지 못했습니다. 저장된 원문을 확인하세요.'));}
  }
  const raw=node('details');raw.append(node('summary','저장된 원문 전체'));const pre=node('pre',r.visible_text??'저장된 최종 출력 없음');raw.append(pre);card.append(raw);const info=node('p',r.reported_usd==null?'비용 미확정 또는 미호출':`보고 비용 $${r.reported_usd}`);info.className='muted';card.append(info);document.getElementById('answers').append(card);
 }
 const c=D.rows.find(x=>x.model===m&&x.arm==='shacl_review');document.getElementById('advisory').textContent=JSON.stringify(c.advisory??{status:'not_available'},null,2);document.getElementById('scope').textContent='선택한 모델의 원래 초안을 공유한 검토 결과. 최초 초안과 실패 기록은 덮어쓰지 않았다.';
}
sel.addEventListener('change',paint);paint();
</script></html>

```
