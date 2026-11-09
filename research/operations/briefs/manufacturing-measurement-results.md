# 실제 측정 파일을 추가한 최종 답변 비교

PP6 제조 자료의 한 질문에 6개 모델을 적용했다. 초안 6건, 같은 초안을 자체 검토한 답변 6건, 같은 초안에 SHACL 자문 보고서를 붙여 검토한 답변 6건으로 총 18건이다. 모두 완료됐으며, 사전에 고정한 네 필드의 판단은 세 조건 모두 6/6 일치했다. **초안부터 네 필드가 맞았으므로 이번 질문에서는 SHACL 보고서의 추가 개선 효과를 확인하지 못했다.**

이 결과는 한 제조 질문의 개발 진단이다. 모델 순위, 일반적인 답변 정확도, SHACL의 무용성을 뜻하지 않는다. 질문과 출처는 이미 살펴본 자료이며, 새 평가용 표본이 아니다.

## 질문과 공통 근거

질문은 “PP6 작업표 2행의 명목 Idc, 기록된 전류 채널의 존재, 해당 결함 구간에 대응한다고 검증된 평균 전류, 적용 검토 문서 버전을 각각 판단하고 사람이 확인할 연결 규약을 제시하라”였다.

| 구분 | 제공 근거 | 고정한 판단 기준 |
|---|---|---|
| 명목 전류 | 원본 작업표의 설정 코드 1과 코드북 C3 | 450 A |
| 기록 채널 | 원본 README와 HDF5 필드 검사 | 존재함 |
| 검증된 구간 평균 | 네 가지 인덱스 가정별 조건부 계산 | 연결 규약이 미검증이므로 미확인 |
| 적용 문서 버전 | 이번 조사 범위의 확인 상태 | 미확인 |

원본 HDF5에는 전류 채널이 있었다. 이전에 확보한 부분 자료에 없었다는 사실을 원본에도 없다는 뜻으로 해석하면 안 된다. 반대로 파일을 확보했다고 어노테이션의 표본 번호, 좌표계, 교정 상태까지 검증되는 것은 아니다. 조건부 평균 456.76~456.78 A는 검증된 결함 구간 평균과 구분했다. 자세한 원본 해시와 읽기 전용 검사는 [측정 자료의 경계](2026-11-07-welding-measurement-boundaries.md)에 남겼다.

## 비교 절차

```mermaid
flowchart TB
  S[동일 질문·S1~S6 근거·명시적 정책] --> A[모델별 원래 초안]
  A --> B[같은 초안 자체 검토]
  A --> V[두 제약의 실제 pySHACL 검사]
  A --> C[같은 초안 SHACL 검토]
  V --> C
  B --> E[답변 저장 후 별도 평가]
  C --> E
  A --> E
```

B와 C는 각각 원래 초안을 검토했다. 자체 검토 결과를 다시 SHACL 검토에 넣지 않았다. 두 조건의 질문·근거·정책·원래 초안은 같고, C에만 보고서를 추가했다. 저장된 요청 18건의 위치·모델·응답 연결과 6쌍의 입력 동일성을 확인했다. 추가 원본 조회나 정답을 이용한 답변 수정은 없었다.

검사는 “연결 규약을 모르는 상태에서 검증된 구간 평균을 단정하는가”, “문서 적용성을 모르는 상태에서 버전을 단정하는가” 두 가지였다. 실제 pySHACL 실행과 같은 정책의 Python 결과를 대조했다. 여섯 초안 모두 위반 플래그가 없었다. 명목값의 정확성, 문장별 인용, 자유 서술의 함의, 교정, 외부 사실은 검사 대상이 아니다. 보고서는 강제 거부 규칙이 아닌 검토 자료로 제공했다.

## 관측 결과와 인용의 한계

| 조건 | 계획 / 완료 | 네 필드 일치 | 근거 없는 검증 평균·버전 단정 | 명목값 보류·채널 부정 |
|---|---:|---:|---:|---:|
| 초안 | 6 / 6 | 6 | 0 | 0 |
| 자체 검토 | 6 / 6 | 6 | 0 | 0 |
| SHACL 검토 | 6 / 6 | 6 | 0 | 0 |

이는 네 필드에 한정한 결과다. 전체 답변의 사실 정확도를 100%로 표현하지 않는다. 정책은 사람이 명시했고, S6에도 확인되지 않은 연결 조건을 적었다. 모델이 자연어에서 정책을 스스로 발견한 실험이 아니다.

코디네이터가 18개 원문을 제공 근거와 대조한 별도 검토에서는 모든 답변에 파일·테이블 대응, 인덱스, 좌표 변환, 교정, 문서 적용성에 관한 확인 항목이 있었다. 그러나 실제 사용자가 그 항목으로 검토를 더 잘 수행했는지는 측정하지 않았다. 이 검토는 비맹검이며 도메인 전문가의 판정이 아니다.

인용 식별자가 유효하다고 문장 전체가 그 출처 하나로 뒷받침되지는 않았다. 예를 들어 Luna의 세 답변은 S1 작업표의 표본 번호와 S6의 ‘연결 규약 미검증’을 한 문장에 묶어 S1만 인용했다. Luna의 초안과 자체 검토에는 README 설명과 파일 검사 결과를 묶은 인용도 있었다. Fable 자체 검토의 같은 워크북 해시 비교에는 S1과 S2가 함께 필요하다. 다른 곳에 관련 근거를 인용했더라도 개별 인용의 범위는 별도로 살펴야 한다. 이를 사전에 정의한 인용 점수로 사후 변환하지 않았다.

## 모델·실행 비용

기존 비교의 여섯 모델 식별자를 유지했다. Google Gemini 3.8 Flash와 Gemini 4 Argon, OpenAI GPT-6 Luna와 GPT-6 Astra, Anthropic Claude Sonnet 5.5와 Claude Fable 5.1이다. 이는 최신 시장 모델 목록에 관한 주장이 아니다.

실행 전 엔드포인트 확인에서 Argon의 기존 경로를 사용할 수 없어 `google-vertex/global` 경로로 명시적으로 바꾸고 고정했다. 다른 경로로 자동 재시도하지 않았다. 이 경로 차이는 이전 실험과의 비교 한계다.

출력 한도는 공통 2,048 토큰, reasoning 설정은 medium이었다. 입력은 보수적인 바이트 기반 상한으로 점검했으며 실제 모델별 토크나이저를 측정하지 않았다. 따라서 공통 최대 예산이지 실제 토큰 수의 완전한 일치가 아니다.

추가 18회 보고 비용은 **$0.646692400**이다. 기존 원장을 합친 누적은 **180회 / 보고 비용 $3.368438350 / 실패 비용을 환급하지 않는 예약 원장 $4.146031030**이다. 미해결 예약은 없다. 승인된 180회에 도달했으므로 남은 달러를 이유로 추가 호출하지 않는다. AWS 비용은 이 원장과 별개다.

## 이번 결과의 의미

현재 자료에서 먼저 드러난 문제는 근거의 누락과 연결 규약이었다. 코드북 값을 검색 결과에 보존하고 실제 측정 파일을 확보하자, 명목값·채널 존재와 미확인 구간 값을 구분하는 답변이 가능했다. 다만 이전 입력과 달라진 결과를 SHACL 보고서만의 효과로 돌릴 수 없다.

이번 보고서는 정답 인증보다 **검사가 다루는 범위와 남은 확인 항목을 드러내는 자료**로 읽는 것이 맞다. 그 용도가 사람의 검토 시간이나 오류를 줄이는지는 아직 측정하지 않았다. 다음 확인 대상은 어노테이션과 측정 파일의 실제 연결 규약이며, 새로 알아낸 내용을 이번에 고정한 모델 입력과 답변에 소급 적용하지 않는다.

[실제 답변 비교 데모](../experiments/seminar/measurement-review.html)에서 여섯 모델의 초안과 두 검토 답변을 원문 그대로 볼 수 있다. 저장 자료는 `research/manufacturing-measurement-1/answer-001/`에 있다. 데모는 저장 결과 재생이며 API를 호출하지 않는다.

Review scope: saved result interpretation plus offline demo builder/template. Raw HDF and all raw model completions omitted: unverified here. Scorer and bindings were executed coordinator side; no reviewer may assume source truth from summary. All18complete, allfourfields18agree. No efficacy/modelranking claim. Review <=250words.

## research/manufacturing-measurement-1/demo-001/build.py
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
  if prefix.with_suffix('.request.json').exists():
   req=json.loads(prefix.with_suffix('.request.json').read_text())
   if req['model']!=slot['model']:raise ValueError('request_binding')
  if prefix.with_suffix('.result.json').exists():
   r=json.loads(prefix.with_suffix('.result.json').read_text());raw=json.loads(prefix.with_suffix('.raw.txt').read_text())
   if raw['model']!=slot['model'] or r['status']!=state['state']:raise ValueError('response_binding')
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

## research/manufacturing-measurement-1/demo-001/template.html
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
function paint(){const m=sel.value;document.getElementById('answers').replaceChildren();for(const arm of ['draft','self_review','shacl_review']){const r=D.rows.find(x=>x.model===m&&x.arm===arm);const card=document.createElement('article');card.className='card';const h=document.createElement('h3');h.textContent=names[arm];card.append(h);const s=document.createElement('p');s.className='badge';s.textContent=r.state;card.append(s);const pre=document.createElement('pre');pre.textContent=r.visible_text??'저장된 최종 출력 없음';card.append(pre);const info=document.createElement('p');info.className='muted';info.textContent=r.reported_usd==null?'비용 미확정 또는 미호출':`보고 비용 $${r.reported_usd}`;card.append(info);document.getElementById('answers').append(card)}const c=D.rows.find(x=>x.model===m&&x.arm==='shacl_review');document.getElementById('advisory').textContent=JSON.stringify(c.advisory??{status:'not_available'},null,2);document.getElementById('scope').textContent='선택한 모델의 원래 초안을 공유한 검토 결과. 최초 초안과 실패 기록은 덮어쓰지 않았다.'}sel.addEventListener('change',paint);paint();
</script></html>

```

## _workspace/manufacturing-continuation-20261107/measurement-score/binding_audit.py
```
import json,hashlib
from pathlib import Path
p=Path('_workspace/manufacturing-continuation-20261107/measurement-answer')
def read(path):return json.loads(path.read_text())
freeze=read(p/'freeze.json');assert all(hashlib.sha256(Path(k).read_bytes()).hexdigest()==v for k,v in freeze['hashes'].items())
plan=read(p/'plan.json');states=read(p/'states.json');inp=read(p/'input.json');drafts={};requests={};rows=[]
for i,(s,t) in enumerate(zip(plan,states)):
 assert all(s[k]==t[k] for k in ('id','model','arm'))
 prefix=p/'responses'/f'{i:03d}';req=read(prefix.with_suffix('.request.json'));raw=read(prefix.with_suffix('.raw.txt'));result=read(prefix.with_suffix('.result.json'))
 assert req['model']==raw['model']==s['model'] and result['status']==t['state']=='completed'
 assert json.loads(raw['choices'][0]['message']['content'])==result['contract']
 body=json.loads(req['messages'][1]['content']);assert all(body[k]==inp[k] for k in ('question_id','question','evidence'))
 if s['arm']=='draft':drafts[s['model']]={'completion_status':result['status'],'finish_reason':result['finish_reason'],'parsed_response':result['contract'],'visible_text':raw['choices'][0]['message']['content']}
 else:assert body['saved_draft']==drafts[s['model']]
 if s['arm']=='shacl_review':assert body.pop('advisory_report')==read(prefix.with_suffix('.advisory.json'))
 requests[s['model'],s['arm']]=[req['messages'][0],body]
 rows.append({'index':i,**s,'verified':True})
for m in drafts:assert requests[m,'self_review']==requests[m,'shacl_review']
assert len(rows)==18
out={'runtime_frozen_hashes_match':True,'all18_positional_request_raw_contract_state_bindings':True,'six_review_pairs_exact_same_source_policy_original_draft_except_advisory':True,'rows':rows,'limits':['Checks saved artifacts, not independently authenticated provider execution','Posthoc verification never changes answers']}
Path('_workspace/manufacturing-continuation-20261107/measurement-score/binding-audit.json').write_text(json.dumps(out,indent=2)+'\n');print('18 bindings and6paired inputs verified')

```
