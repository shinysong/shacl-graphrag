'use strict';
const $=id=>document.getElementById(id);
let cfg, active=null, timer=null, cy=null, shown=null, localPending=false;
const labels={queued:'실행 접수',snapshot_fixed:'자료 버전 고정',llm_request:'LLM 요청',llm_response:'LLM 응답',requirements:'질문 요구 분해',catalog_retrieved:'쿼리 후보 검색',plan_checked:'조회 연결 점검',query_started:'그래프 조회 시작',query_completed:'그래프 조회 완료',review_completed:'근거 검토 완료',completed:'최종 답변 완료',failed:'실행 실패',cancelled:'실행 중지',cancel_requested:'중지 요청',llm_failed:'LLM 요청 실패'};
async function api(path,body){const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':cfg.csrf},body:JSON.stringify(body)});const v=await r.json();if(!r.ok)throw Error(v.error||'요청 실패');return v;}
function text(tag,value,cls){const e=document.createElement(tag);e.textContent=value;if(cls)e.className=cls;return e;}
function detail(title,value,id){const li=document.createElement('li'),d=document.createElement('details');if(id)d.id=id;d.append(text('summary',title),text('pre',JSON.stringify(value,null,2)));li.append(d);return li;}
function setBusy(b){$('domain').disabled=b||localPending;$('send').disabled=b||!cfg.live_enabled;$('cancel').disabled=!b;$('progress').hidden=!b;}
// Render presentation only; saved answers and comparison strings remain unchanged.
function renderAnswer(value){
 const source=String(value??'');const target=$('answer');target.className='answer';
 try{
  const escapeHTML=value=>value.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const parser=new marked.Marked({gfm:true,breaks:true,renderer:{html:token=>escapeHTML(token.text)}});
  const fragment=DOMPurify.sanitize(parser.parse(source),{
   RETURN_DOM_FRAGMENT:true,
   ALLOWED_TAGS:['p','br','h1','h2','h3','h4','h5','h6','strong','em','del','ul','ol','li','blockquote','pre','code','hr','table','thead','tbody','tr','th','td','a'],
   ALLOWED_ATTR:['href','title','start'],ALLOW_DATA_ATTR:false,ALLOW_ARIA_ATTR:false
  });
  for(const link of fragment.querySelectorAll('a')){
   const href=link.getAttribute('href')||'';
   if(!/^(https?:\/\/|mailto:)/i.test(href))link.removeAttribute('href');
   else{link.target='_blank';link.rel='noopener noreferrer';}
  }
  for(const table of fragment.querySelectorAll('table')){
   const wrap=document.createElement('div');wrap.className='answer-table';wrap.tabIndex=0;
   wrap.setAttribute('role','region');wrap.setAttribute('aria-label','답변 표');table.replaceWith(wrap);wrap.append(table);
  }
  target.replaceChildren(fragment);
 }catch(error){target.textContent=source;}
}
function reset(){if(cy){cy.destroy();cy=null;}$('graph-panel').open=false;for(const id of ['coverage-panel','graph-panel','plan-panel','review-panel','explanation-panel'])$(id).hidden=true;$('coverage').replaceChildren();$('timeline').replaceChildren();$('error').textContent='';}
function graph(execution){const nodes=new Map(),edges=new Map();const add=n=>{if(n&&n.id&&n.kind)nodes.set(n.id,{data:{id:n.id,label:n.id+' · '+(n.name||n.kind),kind:n.kind,...n}});};const edge=(a,r,b)=>{if(a&&b&&nodes.has(a)&&nodes.has(b))edges.set(a+'|'+r+'|'+b,{data:{id:a+'|'+r+'|'+b,source:a,target:b,label:r}});};for(const c of execution.calls||[]){if(c.error)continue;for(const row of c.result?.rows||[]){for(const k of ['order','machine','qualification'])add(row[k]);if(c.tool==='impacted_orders'||c.tool==='assigned_machines')edge(row.order?.id,'ASSIGNED_TO',row.machine?.id);if(c.tool==='qualification_records'||c.tool==='current_qualification_records'||c.tool==='expired_qualification_records')edge(row.machine?.id,'HAS_QUALIFICATION',row.qualification?.id);if(c.tool==='replacement_candidates'&&row.required_capability){add({id:row.required_capability,kind:'Capability'});edge(row.order?.id,'REQUIRES',row.required_capability);edge(row.machine?.id,'CAPABLE_OF',row.required_capability);}}}return [...nodes.values(),...edges.values()];}
function drawGraph(){if(!shown?.execution)return;if(cy)cy.destroy();cy=cytoscape({container:$('graph-canvas'),elements:shown.graph||graph(shown.execution),layout:{name:'breadthfirst',directed:true,padding:20},style:[{selector:'node',style:{label:'data(label)','background-color':'#168c81',color:'#607577','font-size':11,width:24,height:24,'text-valign':'bottom','text-margin-y':6}},{selector:'node[kind="Order"]',style:{'background-color':'#4f7ed8'}},{selector:'node[kind="Qualification"]',style:{'background-color':'#ac7d29'}},{selector:'edge',style:{label:'data(label)',width:1.5,'line-color':'#809b93','target-arrow-color':'#809b93','target-arrow-shape':'triangle','curve-style':'bezier','font-size':8,color:'#607577','text-rotation':'autorotate'}}]});cy.on('tap','node,edge',e=>$('graph-selection').textContent=JSON.stringify(e.target.data(),null,2));}
$('graph-panel').addEventListener('toggle',()=>{if($('graph-panel').open)drawGraph();});
function render(result,replay=false,events=[]){reset();shown=result;$('mode').textContent=replay?'저장 기록 · API 호출 없음':'새 LLM 실행';$('trace-help').textContent=replay?'과거 저장된 계획과 조회 근거입니다. 지금 실행한 이벤트가 아닙니다.':'서버가 기록한 실행 이벤트입니다. 세부 입력·결과를 열어볼 수 있습니다.';$('question-display').textContent=result.question;$('answer').className='answer';renderAnswer(result.answer?.answer||'실행 중이거나 최종 답변이 없습니다.');
if(result.plan){$('plan-panel').hidden=false;$('plan').textContent=JSON.stringify({requirements:result.requirements,plan:result.plan},null,2);}
if(result.review?.explanation||result.owl)renderExplanation(result.review?.explanation||{assessment:'not_executed',selected_candidates:[],checks:[],data_turtle:'',shapes_turtle:'',reason:'SHACL not selected; not executed.'},result.owl,null,result);
if(result.review){$('review-panel').hidden=false;$('review-output').textContent=JSON.stringify(result.review,null,2);}
if(result.execution){$('graph-panel').hidden=false;}
if(replay){$('timeline').append(detail('저장 기록 출처',result.provenance),detail('LLM이 작성한 조회 계획',result.plan));}
else for(const e of events)$('timeline').append(detail(labels[e.kind]||e.kind,e.payload));
for(const c of result.execution?.calls||[])$('timeline').append(detail(c.id+' · '+c.tool,c,'evidence-'+c.id));
if(result.answer){$('coverage-panel').hidden=false;for(const item of result.answer.coverage){const row=text('div','',`coverage-row status-${item.status}`);const need=result.requirements.find(r=>r.id===item.id)?.text||item.id;row.append(text('strong',({answered:'답변',partial:'부분 답변',unresolved:'미해결'})[item.status]+' · '+need),text('p',item.explanation));for(const id of item.evidence){const b=text('button',id);b.type='button';b.onclick=()=>{const el=$('evidence-'+id);if(el){el.open=true;el.scrollIntoView({behavior:'smooth',block:'center'});}};row.append(b);}$('coverage').append(row);}for(const unresolved of result.answer.additional_unresolved)$('coverage').append(text('p','추가 미해결: '+unresolved));if(result.answer.citation_reference_errors?.length)$('coverage').append(text('p','확인할 수 없는 인용이 있습니다. 저장된 답변 오류를 보존합니다.'));}
if(result.error)$('error').textContent=result.error.message;}
async function history(){const rows=await api('/api/runs');$('history').replaceChildren();for(const r of rows){const b=text('button',r.config.question+' · '+r.status);b.onclick=()=>{if(active)return;loadRun(r.id);};$('history').append(b);}const conf=await api('/api/config');$('budget').textContent=`누적 호출 ${conf.budget.attempts}회 · 보고 USD ${conf.budget.reported_usd} · 반환 없는 예약 USD ${conf.budget.reserved_nonrefunded_usd}`;}
async function loadRun(id){try{const d=await api('/api/runs/'+id),running=['queued','running'].includes(d.run.status);if(running){$('progress-label').textContent=labels[d.events.at(-1)?.kind]||'실행 중';$('timeline').replaceChildren(...d.events.map(e=>detail(labels[e.kind]||e.kind,e.payload)));timer=setTimeout(()=>loadRun(id),700);}else{active=null;setBusy(false);const result=d.run.answer?JSON.parse(d.run.answer):{question:d.run.config.question};render(result,false,d.events);await history();}}catch(e){$('error').textContent=e.message;if(active)timer=setTimeout(()=>loadRun(id),1500);}}
$('form').addEventListener('submit',async e=>{e.preventDefault();const question=$('question').value.trim();if(!question||active||!cfg.live_enabled)return;try{reset();setBusy(true);$('progress-label').textContent='실행 접수 중';const r=await api('/api/runs',{question,review:$('review').value,owl:$('owl').checked});active=r.id;$('question').value='';$('question-display').textContent=question;$('answer').textContent='';$('mode').textContent='새 LLM 실행';await loadRun(active);}catch(err){setBusy(false);$('error').textContent=err.message;}});
$('question').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('form').requestSubmit();}});
$('cancel').onclick=async()=>{if(active)try{await api('/api/runs/'+active+'/cancel',{});}catch(e){$('error').textContent=e.message;}};
(async()=>{try{cfg=await api('/api/config');$('connection').textContent=cfg.live_enabled?'내 API 키로 실행 가능':'저장 예제 모드';$('live-help').textContent=cfg.live_enabled?`${cfg.model} · 자료 버전 factory-v3 고정. 선택한 검토는 새 실행에만 적용됩니다.`:'새 질문은 서버에서 BYOK 설정 후 실행할 수 있습니다. API 키를 브라우저에 입력하지 마세요.';setBusy(false);for(const x of cfg.examples){const b=text('button',x.question);b.onclick=async()=>{if(active||localPending)return;localPending=true;$('domain').disabled=true;try{render(await api('/api/examples/'+x.id),true);}catch(e){$('error').textContent=e.message;}finally{localPending=false;$('domain').disabled=Boolean(active);}};$('examples').append(b);}await history();}catch(e){$('error').textContent=e.message;$('connection').textContent='연결 실패';}})();

function expandable(title,value){const d=document.createElement('details');d.append(text('summary',title),text('pre',typeof value==='string'?value:JSON.stringify(value,null,2)));return d;}
function renderExplanation(trace,owl=null,effect=null,artifact=null){
 $('explanation-panel').hidden=false;const out=$('explanation-output');out.replaceChildren();
 out.append(text('h3','SHACL · 선택한 근거에 대한 제약 검사'));
 out.append(text('p',trace.assessment==='not_executed'?'SHACL 미선택 · 실행하지 않았습니다.':trace.assessment==='not_assessed'?'검토 대상 없음 · 통과가 아닙니다.':`검토 후보 ${trace.selected_candidates.length}개 · ${trace.conforms?'선택한 제약 통과':'위반 발견'}`));
 out.append(text('p','자료의 진실성·전체 검색·설비 사용 승인은 검증하지 않습니다. 자격 기록이 없다는 결과만으로 원자료 부재와 검색 누락을 구분할 수 없습니다.'));
 out.append(expandable('검토한 사실과 출처',{candidates:trace.selected_candidates,evidence:trace.evidence,data_sha256:trace.data_sha256}));
 const checks=document.createElement('details');checks.append(text('summary',`개별 제약 ${trace.checks.length}건 · 위반 ${trace.checks.filter(c=>c.status==='violation').length}건`));out.append(checks);
 const shapeNames={Status:'설비 상태가 available인지',Capability:'조회된 역량과 요구 역량의 일치',Missing:'선택 근거에 자격 기록이 있는지',Applicable:'한 자격 기록에서 제품·역량·기간을 함께 충족하는지'};
 for(const c of trace.checks){const card=text('div','', 'coverage-row');card.append(text('strong',`${c.candidate} · ${c.status==='pass'?'통과':'위반'}`),text('p',shapeNames[c.shape.split(':').at(-1).replace('>','')]||c.shape));card.append(expandable('적용한 조건과 원본 결과',c));checks.append(card);}
 out.append(expandable('검토 입력으로 투영한 RDF',trace.data_turtle),expandable('적용한 SHACL shapes',trace.shapes_turtle),expandable('원본 검증 보고서',trace.raw_report_turtle||trace.reason),expandable('동일 정책 Python 결과',trace.same_policy_python_flags||[]));
 out.append(text('p','SPARQL 제약의 원본 보고서에 경로나 값이 없으면 null로 표시합니다. 임의로 채우지 않습니다.'));
 if(owl){out.append(text('p',owl.assessment==='not_assessed'?'OWL 검토 대상 없음 · 이번 조회에서 CAP-CUT을 확인하지 못했습니다.':`OWL 직접 분류 도출 ${owl.witnesses.length}건`));out.append(text('h3','OWL-RL · 선언된 분류 관계로 도출한 사실'),text('p','별도로 작성한 공리 예제입니다. 자격 검토 입력에 합치지 않으며 설비 사용 가능성을 뜻하지 않습니다.'),expandable('명시된 사실',owl.asserted_turtle),expandable('적용한 공리',owl.ontology_turtle));for(const w of owl.witnesses)out.append(expandable('도출 사실과 재구성한 근거 연결',w));out.append(text('p','근거 연결은 직접 하위 클래스 규칙으로 재구성했습니다. 추론기가 제공한 내부 증명 trace가 아닙니다.'),expandable('전체 추가 트리플',owl.inferred_ntriples));}
 out.append(text('p','역량 검사는 후보 조회가 반환한 투영을 사용합니다. 원자료의 역량 관계를 독립적으로 재검증하는 검사는 아닙니다.'));
 const download=text('button','이 근거 설명 JSON 저장');download.type='button';download.onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(artifact||{shacl:trace,owl,answer_effect:effect},null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download='factory-explanation.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};out.append(download);
 out.append(text('h3','답변 반영 상태'),text('p',effect?.status==='historical'?'아래 과거 실제 초안·최종 답변과 인용 부분을 확인하세요. 현재 trace를 모델에 새로 제공한 실험은 아닙니다.':effect?'이 진단에서는 LLM 초안·최종 답변을 생성하지 않았습니다. 답변 개선·변화 없음 모두 미측정입니다.':'이 실행은 검토 전 초안을 생성하지 않습니다. 보고서는 최종 답변 입력에 포함되지만, 수정 효과는 별도로 측정하지 않았습니다.'));
}
for(const button of document.querySelectorAll('#diagnostics button'))button.onclick=async()=>{
 if(active||localPending)return;localPending=true;$('domain').disabled=true;button.disabled=true;
 try{const d=await api('/api/diagnostics',{case_id:button.dataset.case});if(d.mode==='historical_actual_model_comparison'){renderHistorical(d);return;}reset();shown={execution:{calls:d.evidence.map((result,i)=>({id:'D'+(i+1),tool:result.tool,result}))}};$('graph-panel').hidden=false;$('mode').textContent='작성 사례 · 실제 로컬 엔진 · LLM 호출 없음';$('question-display').textContent=d.question;$('answer').textContent='아래 판단 근거를 펼쳐 실제 제약 검사와 추론 결과를 확인하세요. 이것은 새 LLM 답변이 아닙니다.';$('trace-help').textContent=d.execution_notice;renderExplanation(d.shacl,d.owl,d.answer_effect,d);$('explanation-panel').open=true;if(d.intervention)$('explanation-output').append(text('h3','주입한 자료 오류 · 검사기에는 제공하지 않은 비교 정보'),expandable('원자료와 바꾼 값',d.intervention));$('timeline').append(detail('작성한 후보 선택 범위',d.projection));for(const e of d.evidence)$('timeline').append(detail(e.tool,e));}
 catch(e){$('error').textContent=e.message;}finally{button.disabled=false;localPending=false;$('domain').disabled=Boolean(active);}
};

function renderHistorical(d){
 reset();shown={execution:{calls:d.evidence.map((result,i)=>({id:result.evidence_id||'E'+(i+1),tool:result.tool,result}))}};
 $('graph-panel').hidden=false;$('question-display').textContent=d.question;$('mode').textContent='과거 실제 LLM 답변 · 새 호출 없음';$('trace-help').textContent='과거 보고서와 실제 답변은 그대로 보존합니다. 상세 SHACL trace만 저장 근거에 대해 지금 재실행합니다.';
 renderAnswer(d.finals.shacl);
 renderExplanation(d.shacl,null,{status:'historical'},d);
 const out=$('explanation-output');out.append(text('h3','과거 실제 초안과 최종 답변'));
 out.append(text('p','초안·자체 검토·Python·SHACL 답변을 같은 화면에서 전환할 수 있습니다. 문구 차이는 정확도 향상을 뜻하지 않습니다. 아래 상세 trace는 과거 모델이 받은 원본 보고서와 구분됩니다.'));
 const select=document.createElement('select');select.setAttribute('aria-label','과거 답변 선택');
 for(const [id,label] of [['draft','검토 전 초안'],['self','자체 검토 후'],['python','Python 검토 후'],['shacl','SHACL 검토 후']]){const o=text('option',label);o.value=id;select.append(o);}select.value='shacl';
 const state=text('p','');const diff=expandable('초안과 선택한 답변의 줄 단위 차이 · 품질 점수 아님','');
 const update=()=>{const answer=select.value==='draft'?d.draft:d.finals[select.value];renderAnswer(answer);diff.querySelector('pre').textContent=select.value==='draft'?'초안 선택':(d.line_diffs[select.value]||'문자열 변화 없음');state.textContent=select.value==='draft'?'검토 전 실제 초안입니다.':(answer===d.draft?'초안과 문자열이 완전히 같습니다.':'초안과 문구가 다릅니다. 차이만으로 개선을 판정하지 않습니다.');};select.onchange=update;update();out.append(select,state,diff);out.append(text('h3',d.observation.title),text('p',d.observation.note),expandable('초안의 해당 구절',d.observation.draft_quote),expandable('SHACL 최종 답변의 해당 구절',d.observation.shacl_quote));
 out.append(expandable('검토 전 초안 원문',d.draft),expandable('과거 모델에 제공한 원본 검토 보고서',d.reports),expandable('답변 비교 출처와 해시',d.provenance));
 $('explanation-panel').open=true;$('timeline').append(detail('과거 실행 출처',d.provenance));for(const e of d.evidence)$('timeline').append(detail(e.evidence_id+' · '+e.tool,e));
}

$('domain').onchange=()=>{
 if(active||localPending)return;
 const shop=$('domain').value==='commerce';reset();shown=null;
 $('factory-menu').hidden=shop;$('commerce-menu').hidden=!shop;$('form').hidden=shop;
 $('question-display').textContent='';renderAnswer('왼쪽 제조 사례를 선택해주세요.');
 if(shop)renderAnswer('왼쪽 관리자 처리안 사례를 선택해주세요. 고객 문의에 대한 처리 가능 범위와 추가 확인 사항을 검토합니다.');
 $('mode').textContent=shop?'관리자 검토 · 새 LLM 호출 없음':'제조 사례';
};
function commerceRender(d){
 reset();shown={execution:{calls:[]},graph:d.graph};$('graph-panel').hidden=false;
 $('question-display').textContent=d.question;$('mode').textContent='작성 처리안 · 실제 로컬 검토 · LLM 아님';renderAnswer(d.answer);
 $('trace-help').textContent='이번 요청에서 실행한 조회·계산·검토입니다. 주문을 변경하거나 고객에게 메시지를 보내지 않습니다.';
 for(const [label,value] of [['자료와 정책 버전 확인',d.source],['관리자가 작성한 처리안',d.plan],['주문 항목 RDF 조회',d.query],['변경 금액·혜택 계산',d.calculations],['도착 근거와 확약 여부',d.delivery_assessment],['선언된 조건 검토',d.shacl.checks],['분류 공리로 도출한 사실',d.owl.witnesses],['남은 확인 사항',d.unresolved]])$('timeline').append(detail(label,value));
 $('explanation-panel').hidden=false;const out=$('explanation-output');out.replaceChildren();
 out.append(text('h3','관리자 처리안의 조건 검토'),text('p',d.shacl.conforms?'선택한 제약 위반 없음. 미확인 항목과 실행 승인은 별도로 확인합니다.':'선언된 조건 위반 발견. 아래 항목을 확인하세요.'));
 for(const c of d.shacl.checks){const card=text('div','', 'coverage-row');card.append(text('strong',({pass:'충족',violation:'확인 필요',unknown:'근거 부족',not_applicable:'이번 처리안에 적용하지 않음'})[c.status]+' · '+c.label),expandable('검토 값과 식별자',c));out.append(card);}
 out.append(expandable('선택한 원자료와 출처',{source:d.source,facts:d.facts}),expandable('변경 금액 계산',d.calculations),text('p','Python과 SHACL은 같은 계산 결과를 검사합니다. 이 결과는 SHACL만의 이점이나 원자료의 진실성을 증명하지 않습니다.'),expandable('동일 정책 Python 결과',d.shacl.same_policy_python_flags),expandable('원자료 RDF',d.source_rdf),expandable('검토 입력 RDF',d.shacl.data_turtle),expandable('실제 SHACL shapes',d.shacl.shapes_turtle),expandable('원본 검증 보고서',d.shacl.raw_report_turtle),expandable('위반 대상·shape·원본 경로와 값',d.shacl.results));
 out.append(text('h3','OWL · 상품 분류'),text('p','선언된 상품 분류에서 상위 분류를 도출합니다. 쿠폰 적용이나 주문 변경 승인은 도출하지 않습니다. 아래 연결은 직접 하위 클래스 규칙으로 재구성한 설명이며 추론기 내부 trace가 아닙니다.'),expandable('명시된 사실',d.owl.asserted_turtle),expandable('작성한 공리',d.owl.ontology_turtle),expandable('도출 사실과 근거',d.owl.witnesses),expandable('전체 추가 트리플',d.owl.inferred_ntriples),expandable('미확인 항목',d.unresolved),expandable('범위와 한계',d.limitations));
 const save=text('button','이커머스 검토 JSON 저장');save.type='button';save.onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(d,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='commerce-review.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};out.append(save);
}
(async()=>{try{const c=await api('/api/commerce');for(const item of c.cases){const b=text('button',item.label);b.dataset.commerce=item.id;b.type='button';b.onclick=async()=>{if(active||localPending)return;localPending=true;$('domain').disabled=true;b.disabled=true;try{commerceRender(await api('/api/commerce',{case_id:item.id}));}catch(e){$('error').textContent=e.message;}finally{b.disabled=false;localPending=false;$('domain').disabled=Boolean(active);}};$('commerce-cases').append(b);}}catch(e){$('commerce-cases').append(text('p','이커머스 데이터 읽기 실패: '+e.message));}})();
