'use strict';
/* Local-only workspace client. Uploaded text is always rendered as text nodes. */
const $ = id => document.getElementById(id);
const state = {csrf:'', current:null, tab:'library', busy:false, edited:false, edits:new Map(), policies:new Map(), detailOrder:[]};
function remember(key,value){try{if(value===null)localStorage.removeItem(key);else localStorage.setItem(key,value);}catch{}}
function recalled(key){try{return localStorage.getItem(key);}catch{return null;}}
const labels = {pending:'검토 대기',approved:'승인',excluded:'제외',insufficient:'정보 부족',completed:'완료',failed:'실패',running:'실행 중',interrupted:'중단',cancelled:'취소',pass:'통과',violation:'위반',unknown:'미확인',not_applicable:'해당 없음'};
function el(tag, text, cls) { const n=document.createElement(tag); if(text!==undefined)n.textContent=text; if(cls)n.className=cls; return n; }
function button(text, fn, cls='') { const b=el('button',text,cls); b.type='button'; b.onclick=()=>{if(!state.busy)fn();}; return b; }
function field(text,input){const l=el('label',text);l.append(input);return l;}
function input(value='',type='text'){const n=el('input');n.type=type;n.value=value;return n;}
function select(options,value){const n=el('select');for(const [v,t] of options){const o=el('option',t);o.value=v;n.append(o);}n.value=value;return n;}
function detail(title,value){const d=el('details');d.append(el('summary',title),el('pre',typeof value==='string'?value:JSON.stringify(value,null,2)));return d;}
function badge(status){return el('span',labels[status]||status,'badge '+status);}
function table(headers,rows){const wrap=el('div',undefined,'table-wrap');wrap.tabIndex=0;wrap.setAttribute('aria-label','표 · 가로 스크롤 가능');const t=el('table'),head=el('thead'),tr=el('tr');headers.forEach(h=>{const th=el('th',h);th.scope='col';tr.append(th);});head.append(tr);t.append(head);const b=el('tbody');rows.forEach(row=>{const r=el('tr');row.forEach(v=>r.append(el('td',v===null?'미확인':String(v??''))));b.append(r);});t.append(b);wrap.append(t);return wrap;}
function kv(obj){const dl=el('dl',undefined,'kv');Object.entries(obj).forEach(([k,v])=>{dl.append(el('dt',k),el('dd',String(v??'미확인')));});return dl;}
async function api(body){const r=await fetch('/api/workspace',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrf},body:JSON.stringify(body)});let data;try{data=await r.json();}catch{throw Error('서버 응답을 읽지 못했습니다. 연결을 확인한 뒤 현재 자료실을 다시 불러오세요.');}if(!r.ok){const error=Error(data.error||'요청을 처리하지 못했습니다.');error.httpStatus=r.status;throw error;}return data;}
async function task(fn){if(state.busy)return;state.busy=true;document.body.setAttribute('aria-busy','true');$('error').hidden=true;$('notice').textContent='처리 중입니다…';const controls=[...document.querySelectorAll('button,input,select,textarea')];const disabled=controls.map(n=>n.disabled);controls.forEach(n=>n.disabled=true);try{await fn();if($('notice').textContent==='처리 중입니다…')$('notice').textContent='저장된 상태를 불러왔습니다.';}catch(e){$('notice').textContent='';$('error').hidden=false;$('error').textContent=e.message;$('error').scrollIntoView({block:'nearest'});}finally{controls.forEach((n,i)=>n.disabled=disabled[i]);state.busy=false;document.body.setAttribute('aria-busy','false');}}
function mutable(){return state.current&&!state.current.archived&&state.current.revision===state.current.current_revision;}
function changed(){state.edited=true; $('notice').textContent='아직 저장하지 않은 검토 내용이 있습니다. 항목 저장 또는 선택 승인으로 저장하세요.';}
function canLeave(){return !state.edited||window.confirm('저장하지 않은 검토 내용이 있습니다. 저장된 상태로 이동할까요?');}
async function list(){const data=await api({action:'list',archived:$('archived').checked});const n=$('workspaces');n.replaceChildren();if(!data.workspaces.length)n.append(el('p','저장한 자료실이 없습니다.','muted'));for(const row of data.workspaces){const b=button(row.title,()=>{if(canLeave())task(async()=>show(await api({action:'get',id:row.id,revision:null})));},row.id===state.current?.id?'active':'');b.append(el('small',`버전 ${row.revision} · ${new Date(row.updated).toLocaleDateString('ko-KR')}`));n.append(b);}}
function retainOperation(full){
 const i=state.current.operations.findIndex(o=>o.id===full.id);
 if(i<0)state.current.operations.unshift(full);else state.current.operations[i]=full;
 state.detailOrder=state.detailOrder.filter(id=>id!==full.id);state.detailOrder.push(full.id);
 while(state.detailOrder.length>3){const id=state.detailOrder.shift(),j=state.current.operations.findIndex(o=>o.id===id);
  if(j>=0){const old=state.current.operations[j],summary={summary_only:true};for(const key of ['id','workspace','revision','kind','state','error','created','updated'])summary[key]=old[key];state.current.operations[j]=summary;}
 }
}
async function showExecution(operation){const row=await api({action:'get',id:state.current.id,revision:null});const index=row.operations.findIndex(o=>o.id===operation.id);if(index>=0)row.operations[index]=operation;else row.operations.unshift(operation);await show(row);retainOperation(operation);render();}
async function show(row,edits=new Map(),policies=new Map()){state.detailOrder=[];state.current=row;$('gateway-status').textContent=row.model_questions?.enabled?'외부 모델 질문 선택 가능':row.model_proposals?.enabled?'외부 모델 생성 선택 가능':'외부 모델 비활성';state.edits=edits;state.policies=policies;state.edited=edits.size>0||policies.size>0;remember('operations-workspace-id',row.id);$('welcome').hidden=true;$('workspace').hidden=false;render();await list();}
function render(){const w=state.current,d=w.draft;$('workspace-title').textContent=w.title;$('workspace-meta').textContent=`${d.adapter==='commerce-csv-1'?'쇼핑몰 운영':'제조 운영'} / 버전 ${w.revision}${w.archived?' / 보관됨':''}`;$('archive').textContent=w.archived?'자료실 복구':'보관하기';$('summary').replaceChildren();for(const [num,title] of [[d.sources.length,'저장한 파일'],[d.entries.filter(e=>e.status==='pending'||e.status==='insufficient').length,'검토할 항목'],[d.entries.filter(e=>e.status==='approved').length,'승인한 항목'],[w.operation_count??w.operations.length,'실행 기록']]){const n=el('div',undefined,'stat');n.append(el('strong',String(num)),el('span',title));$('summary').append(n);}document.querySelectorAll('[data-tab]').forEach(b=>b.setAttribute('aria-current',b.dataset.tab===state.tab?'page':'false'));const root=$('content');root.replaceChildren();if(!mutable())root.append(el('p','이전 버전 또는 보관 자료입니다. 편집과 새 실행은 현재 활성 버전에서 가능합니다.','callout'));({library:renderLibrary,review:renderReview,questions:renderQuestions,changes:renderChanges}[state.tab])(root);}
function heading(root,title,text){const n=el('div',undefined,'section-head');const h=el('div');h.append(el('h2',title),el('p',text,'muted'));n.append(h);root.append(n);return n;}
function currencyLabel(value){return ({unknown:'미확인',mixed:'여러 통화',not_applicable:'해당 없음',KRW:'원 (KRW)'})[value]||value;}
function renderLibrary(root){const w=state.current,d=w.draft;heading(root,'원본 자료','업로드한 원문을 그대로 보관합니다. 미리보기의 빈 셀은 미확인 값입니다.');const meta=el('article',undefined,'card');meta.append(kv({'자료 버전':d.metadata.snapshot_id,'자료 기준일':d.metadata.as_of,'통화':currencyLabel(d.metadata.currency)}));root.append(meta);for(const s of d.sources){const card=el('article',undefined,'card');card.append(el('h3',s.name),el('p',`${s.kind==='table'?`${s.rows.length}행 · ${s.headers.length}열`:`${s.paragraphs.length}문단`} · ${s.bytes.toLocaleString()} bytes`,'muted'));if(s.kind==='table'){card.append(table(s.headers,s.rows.slice(0,8).map(r=>s.headers.map(h=>r[h]))));card.append(el('p','첫 8행 미리보기 · 행 번호는 CSV 레코드 기준입니다.','muted'));const profiles=el('details');profiles.append(el('summary','열별 값과 누락 확인'),table(['열','관측 값 유형','빈 값','서로 다른 값','중복 값'],s.profiles.map(p=>[p.column,p.observed_types.join(', '),p.missing,p.distinct_nonempty,p.duplicate_nonempty])));card.append(profiles);}else{for(const p of s.paragraphs.slice(0,3))card.append(el('p',p.text,'source-quote'));if(s.paragraphs.length>3)card.append(el('p','앞의 3개 문단을 표시합니다. 전체 원문은 아래에서 확인하세요.','muted'));}card.append(detail('전체 원문',s.content),detail('원본 해시와 위치 정보',{name:s.name,sha256:s.sha256,bytes:s.bytes,locations:s.locations,paragraphs:s.kind==='document'?s.paragraphs:undefined}));root.append(card);}root.append(detail('고정 분류 규칙 · OWL 공리',d.ontology));}
function targetControl(entry){const d=state.current.draft;if(entry.kind==='policy'){return select([['','선택 필요'],...Object.keys(state.current.contracts).map(k=>[k,k]),['context','문맥만 보존'],['unsupported','지원하지 않는 정책']],entry.target);}if(entry.kind==='relation'){const options=[];for(const s of d.sources.filter(s=>s.kind==='table'))for(const c of s.headers)options.push([JSON.stringify({file:s.name,column:c,sha256:s.sha256}),`${s.name} → ${c}`]);return select(options,JSON.stringify({file:entry.target.file,column:entry.target.column,sha256:entry.target.sha256}));}const catalog=state.current.mapping_targets;if(Array.isArray(catalog))return select([['','선택 필요'],['source_only','원본 조회에만 사용 · 표준 연결 없음'],...catalog.map(x=>[x,x])],entry.target);const n=input(entry.target);n.placeholder='예: orders.id';return n;}
async function saveDecisions(decisions){const retained=new Map(state.edits);for(const d of decisions)retained.delete(d.entry_id);const row=await api({action:'change',id:state.current.id,revision:state.current.revision,decisions});await show(row,retained,state.policies);if(retained.size||state.policies.size)changed();}
function proposalEvidence(entry,draft=state.current.draft){const box=el('details');box.append(el('summary','모델이 참고한 원문 위치'),el('p','모델이 선택한 출처입니다. 위치가 원본과 일치하는지 확인하지만, 그 내용이 제안한 의미를 뒷받침하는지는 사람이 검토해야 합니다.','muted'));const refs=entry.extraction?.source_evidence||[];if(!refs.length)box.append(el('p','저장된 출처 선택이 없습니다. 제안 이유와 전체 원문을 비교하세요.','muted'));for(const ref of refs){const source=draft.sources.find(s=>s.name===ref.file&&s.sha256===ref.sha256);if(!source)continue;if(ref.column!==undefined){box.append(el('h4',ref.file+' · '+ref.column),el('p','처음 3개 레코드의 값입니다. 전체 원본은 자료실에서 확인하세요.','muted'),table(['원문 행','값'],source.rows.slice(0,3).map((r,i)=>[source.locations[i].line_start+'–'+source.locations[i].line_end,r[ref.column]])));}else{const para=source.paragraphs.find(p=>p.paragraph===ref.paragraph);if(para)box.append(el('h4',ref.file+' · 원문 '+ref.line_start+'–'+ref.line_end+'행'),el('p',para.text,'source-quote'));}}return box;}
function sourceMentions(entry){const box=el('details');const refs=state.current.column_references||{};const endpoints=entry.kind==='relation'?[entry.source,entry.target]:[entry.source];box.append(el('summary','열 이름이 등장하는 설명 문서'),el('p','열 이름의 정확한 문자열로 찾은 참고 문단입니다. 같은 이름의 다른 열에 관한 설명일 수 있으며, 관계를 부정하는 내용도 포함됩니다. 원문을 읽고 판단하세요.','muted'));for(const endpoint of endpoints){const result=refs[endpoint.file]?.[endpoint.column];box.append(el('h4',`${endpoint.file} · ${endpoint.column}`),el('p',result?.total?`${result.total}개 문단 중 ${result.matches.length}개 표시`:'같은 열 이름을 포함한 문단을 찾지 못했습니다. 설명이 없다는 뜻은 아닙니다.','muted'));for(const match of result?.matches||[])box.append(el('p',`${match.file} · ${match.line_start}–${match.line_end}행`,'muted'),el('p',state.current.draft.sources.find(s=>s.name===match.file&&s.sha256===match.sha256)?.paragraphs.find(p=>p.paragraph===match.paragraph)?.text||'원문을 찾을 수 없습니다.','source-quote'),detail('원본 해시',match.sha256));}return box;}
function relationEvidence(entry){
 const box=el('section');box.append(el('h4','선택한 두 열의 원본 값'),el('p','빈 문자열을 제외한 정확한 값 대조입니다. 값이 같아도 같은 주문이나 고객을 뜻한다고 확정할 수 없습니다. 설명 문서와 업무 의미를 함께 확인하세요.','muted'));
 const sides=[entry.source,entry.target].map(ref=>{
  const source=state.current.draft.sources.find(s=>s.kind==='table'&&s.name===ref.file&&s.sha256===ref.sha256&&s.headers.includes(ref.column));
  if(!source)return null;
  const records=source.rows.map((row,i)=>({value:row[ref.column],line:source.locations[i],record:i+1}));
  return {ref,records,values:new Set(records.filter(r=>r.value!=='').map(r=>r.value))};
 });
 if(sides.some(s=>!s)){box.append(el('p','선택한 열의 원본을 확인할 수 없습니다. 자료와 연결 대상을 다시 확인하세요.','callout'));return box;}
 const [left,right]=sides,matched=[...left.values].filter(v=>right.values.has(v));
 box.append(kv({'왼쪽 고유 값':left.values.size,'오른쪽 고유 값':right.values.size,'양쪽 일치 값':matched.length,'왼쪽에만 있는 값':left.values.size-matched.length,'오른쪽에만 있는 값':right.values.size-matched.length}));
 for(const side of sides){const nonempty=side.records.filter(r=>r.value!=='').length;box.append(el('h4',`${side.ref.file} · ${side.ref.column}`),el('p',`전체 ${side.records.length}행 · 빈 값 ${side.records.length-nonempty}행 · 중복된 비어 있지 않은 값 ${nonempty-side.values.size}행`,'muted'),table(['레코드','원문 행','처음 5개 원본 값'],side.records.slice(0,5).map(r=>[r.record,`${r.line.line_start}–${r.line.line_end}`,r.value])),detail('이 열의 원본 해시',side.ref.sha256));}
 box.append(el('p','표는 각 열의 처음 5개 레코드이며 전체 행끼리 연결한 결과가 아닙니다. 위 개수는 업로드한 전체 열을 기준으로 계산했습니다.','muted'));
 return box;
}
function relationOrigin(entry,showComparison=true){const model=typeof entry.extraction?.method==='string'&&entry.extraction.method.startsWith('model-proposal-1');const overlap=entry.overlap&&typeof entry.overlap==='object';const origin=entry.extraction?.method==='human-relation-1'?'사용자가 직접 추가한 관계 후보입니다.':model?(overlap?'모델 제안 · 값 겹침으로 찾은 기존 후보의 기록도 보관합니다.':'모델 제안 · 값 겹침으로 찾은 후보는 아닙니다.'):(overlap?'값 겹침으로 찾은 후보입니다.':'저장된 관계 제안입니다. 생성 방식은 상세 기록에서 확인하세요.');const labels={supported:'원문이 관계를 뒷받침한다고 판단',contradicted:'원문이 관계와 충돌한다고 판단',uncertain:'관계 판단에 정보가 부족함'};const assessment=entry.extraction?.assessment;const notice=Object.hasOwn(labels,assessment)?` 모델 검토: ${labels[assessment]}. 자동 승인·제외나 사실 검증 결과가 아닙니다.`:'';return origin+notice+' 제안 이유와 인용 원문은 생성 당시의 기록입니다. 연결할 열을 바꾸면 근거가 새 연결에도 맞는지 다시 확인하세요. '+(showComparison?'아래 값 대조는 현재 선택한 두 열을 기준으로 합니다. ':'')+'값이 같아도 업무상 같은 의미인지는 확인이 필요합니다.';}
function decisionEditor(entry,withSelection=false){const pending=state.edits.get(entry.id);if(pending)entry={...entry,...pending};const card=el('div',undefined,'entry');const title=el('div',undefined,'entry-title');let checked;if(withSelection){checked=input('','checkbox');checked.setAttribute('aria-label',`${entry.source.column} 선택`);title.append(checked);}title.append(el('label',entry.source.column||`${entry.source.file} · ${entry.kind==='policy'?'정책 문단 '+entry.source.paragraph:'관계 후보'}`),badge(entry.status));card.append(title);const source=state.current.draft.sources.find(s=>s.name===entry.source.file);if(entry.kind==='mapping'){card.append(el('p','원본 예시: '+source.rows.slice(0,3).map(r=>r[entry.source.column]||'(빈 값)').join(' / '),'muted'));}else if(entry.kind==='policy'){card.append(el('p',entry.source.text,'source-quote'),el('p',`${entry.source.file} · 원문 ${entry.source.line_start}–${entry.source.line_end}행`,'muted'),el('p','적용 대상, 금액 기준, 예외, 시행일이 아래 규칙과 일치하는지 확인하세요.','callout'));}else{card.append(el('p',`${entry.source.file}의 ${entry.source.column}의 연결 후보를 기록합니다. 승인만으로 자동 조회가 실행되지는 않습니다. 설명과 양쪽 열을 승인하면 질문하기에서 관계와 값을 직접 선택해 대조할 수 있습니다. 기존 업무 계산은 고정된 참조 규칙을 사용합니다.`,'muted'),el('p',relationOrigin(entry),'muted'));}for(const question of (Array.isArray(entry.extraction?.questions)?entry.extraction.questions:[]).filter(v=>typeof v==='string'))card.append(el('p',question,'callout'));for(const ref of (Array.isArray(entry.extraction?.related_policy_statements)?entry.extraction.related_policy_statements:[]).filter(v=>v&&typeof v==='object'&&typeof v.entry_id==='string')){const other=state.current.draft.entries.find(e=>e.id===ref.entry_id);card.append(el('p',`${ref.file} · ${ref.line_start}–${ref.line_end}행`,'muted'));if(other?.source.text)card.append(el('p',other.source.text,'source-quote'));}const relationPanel=el('div');if(entry.kind==='relation'){relationPanel.append(relationEvidence(entry));card.append(relationPanel);}const mentionPanel=el('div');if(entry.kind!=='policy'){mentionPanel.append(sourceMentions(entry));card.append(mentionPanel);}if(entry.extraction?.source_evidence)card.append(proposalEvidence(entry));const grid=el('div',undefined,'review-grid'),target=targetControl(entry),status=select(Object.entries(labels).filter(([k])=>['pending','approved','excluded','insufficient'].includes(k)),entry.status),note=el('textarea'),interpretation=el('textarea');if(entry.kind==='relation')target.addEventListener('change',()=>{const selected={...entry,target:JSON.parse(target.value)};mentionPanel.replaceChildren(sourceMentions(selected));relationPanel.replaceChildren(relationEvidence(selected));});status.setAttribute('aria-label','검토 상태');note.value=entry.note;interpretation.value=entry.interpretation;note.maxLength=interpretation.maxLength=4000;grid.append(field(entry.kind==='policy'?'적용할 규칙':entry.kind==='relation'?'검토할 연결 후보':'표준 필드',target),field('검토 상태',status));let meaning;if(entry.kind==='policy'){meaning=el('p',undefined,'source-quote');const inputs=el('div');const update=()=>{const c=state.current.contracts[target.value];meaning.textContent=c?c.meaning:'실행되는 규칙이 없습니다.';inputs.replaceChildren();const actual=state.current.policy_inputs?.[target.value];if(actual){inputs.append(el('p','아래는 승인된 필드에서 읽은 원본 값입니다. 정책 문장과 값·적용 대상이 일치하는지 확인하세요. 일치 여부를 자동 판정하거나 문장으로 계산 규칙을 바꾸지 않습니다.','callout'));for(const f of actual.fields){const block=el('details');block.append(el('summary',`${f.field} · ${f.state==='available'?'원본 값 확인':f.state==='ambiguous'?'승인 연결이 여러 개':'필드 연결 검토 필요'}`));if(f.source)block.append(el('p',`${f.source.file} · ${f.source.column}`,'muted'),table(['CSV 레코드','원문 행','원본 값'],f.records.map(v=>[v.record,`${v.line_start}–${v.line_end}`,v.value])),detail('필드 출처',f.source));inputs.append(block);}}};target.addEventListener('change',update);update();card.append(meaning,inputs);}const dateControls=[];if(entry.kind==='policy'){for(const [i,candidate] of (state.current.policy_date_candidates?.[entry.id]||[]).entries()){const saved=entry.temporal?.[i];const control=select([['unresolved','역할 확인 필요'],['start','적용 시작일 (당일 포함)'],['end','적용 종료일 (당일 포함)'],['context','참고 날짜 · 적용 기간 아님']],saved?.role||'unresolved');dateControls.push({candidate,control});grid.append(field(`${candidate.date} · 날짜 ${i+1}의 역할`,control));}if(dateControls.length)card.append(el('p','원문을 보고 각 날짜의 역할을 선택하세요. 참고 날짜로 분류해도 정책의 유효성이 자동 확인되는 것은 아닙니다. 적용 대상과 기간을 해석란에 기록하세요.','callout'));}if(entry.kind==='mapping'){interpretation.placeholder='예: 이 열은 주문의 고유 번호입니다. 환불 접수 번호와 구분합니다.';card.append(el('p','필드 설명은 승인한 열의 조회 목록과 근거에 함께 보관합니다. 모델에 전달될 수 있지만 새 계산 규칙이나 자동 연결을 만들지는 않습니다.','muted'));}grid.append(field(entry.kind==='mapping'?'이 필드의 업무 의미 · 적용 범위':'검토한 해석 · 적용 범위',interpretation),field('메모 · 제외한 이유',note));card.append(grid);for(const control of [target,status,note,interpretation,...dateControls.map(v=>v.control)]){control.disabled=!mutable();control.addEventListener('input',()=>{state.edits.set(entry.id,value());changed();});}const value=()=>({entry_id:entry.id,status:status.value,target:entry.kind==='relation'?JSON.parse(target.value):target.value,note:note.value,interpretation:interpretation.value,...(entry.kind==='policy'?{temporal:dateControls.map(v=>({...v.candidate,role:v.control.value}))}:{})});const save=button('이 항목 저장',()=>task(()=>saveDecisions([value()])));save.disabled=!mutable();card.append(save,detail('제안 근거 · 이전 검토 기록',{reason:entry.reason,source:entry.source,extraction:entry.extraction,overlap:entry.overlap,previous_decision:entry.previous_decision}));return {card,checked,value};}
async function generateSuggestions(requestKey,revision=state.current.revision){await task(async()=>{
 const storage='operations-generation-'+state.current.id,existing=recalled(storage);
 if(existing&&JSON.parse(existing).request_key!==requestKey)throw Error('먼저 원래 생성 요청의 결과를 확인하세요.');
 remember(storage,JSON.stringify({request_key:requestKey,revision}));
 const stopProgress=watchQuestionProgress(state.current.id,requestKey);
 try{
  const response=await api({action:'suggest',id:state.current.id,revision,request_key:requestKey});
  stopProgress();
  if(response.operation.state!=='running')remember(storage,null);
  await show(await api({action:'get',id:state.current.id,revision:null}));
  const messages={completed:'초안 생성 기록을 불러왔습니다. 제안을 확인한 뒤 적용하세요.',failed:'초안 생성에 실패했습니다. 저장된 오류 기록을 확인하세요.',interrupted:'초안 생성이 중단되었습니다. 저장된 기록을 확인하세요. 자동으로 다시 호출하지 않습니다.',cancelled:'접수 전에 철회된 초안 생성 요청입니다.'};
  $('notice').textContent=Object.hasOwn(messages,response.operation.state)?messages[response.operation.state]:'아직 실행 중인 요청입니다. 원래 생성 요청 확인으로 상태를 확인하세요. 새로 호출하지 않습니다.';
 }catch(error){stopProgress();render();$('notice').textContent='초안 생성 결과를 확인하지 못했습니다. 원래 요청 기록을 확인하세요. 자동으로 다시 호출하지 않습니다.';throw error;}
 finally{stopProgress();}
});}
function modelProposalPanel(root){
 const info=state.current.model_proposals||{};const box=el('article',undefined,'card');box.append(el('h3','의미 초안 생성'),el('p',info.enabled?`선택 가능한 모델: ${info.model} · 기존 예산 원장을 공유합니다.`:'현재는 로컬 사전·규칙으로 제안합니다. 외부 모델 생성은 서버에서 활성화하지 않았습니다.','muted'));
 const pending=recalled('operations-generation-'+state.current.id);
 if(pending){try{const request=JSON.parse(pending);box.append(button('원래 생성 요청 확인',()=>generateSuggestions(request.request_key,request.revision)),button('미접수 생성 요청 철회 · 상태 확인',()=>withdrawPending(request,true)));}catch{}}
 const run=button('모델로 새 초안 제안',()=>{if(canLeave()&&window.confirm('이 자료실의 원문 전체를 설정된 외부 모델에 보내고 공유 예산에서 유료 호출 1회를 시도합니다. 결과는 따로 저장되며 기존 승인을 바로 바꾸지 않습니다. 진행할까요?'))generateSuggestions(crypto.randomUUID());});run.disabled=!mutable()||!info.enabled||Boolean(pending)||state.current.draft.adapter!=='commerce-csv-1';box.append(run);root.append(box);
 for(const op of state.current.operations.filter(o=>o.kind==='model_suggestions'))root.append(operationCard(op));
 appendHistoryMore(root);
}
function appendHistoryMore(root){if(state.current.operations_next)root.append(button('이전 실행 기록 더 보기',()=>task(async()=>{const page=await api({action:'history',id:state.current.id,before:state.current.operations_next});const seen=new Set(state.current.operations.map(o=>o.id));state.current.operations.push(...page.operations.filter(o=>!seen.has(o.id)));state.current.operations_next=page.operations_next;state.current.operation_count=page.operation_count;render();})));}
function proposalResult(op){const card=el('article',undefined,'card');card.append(el('h3','모델 의미 초안'),badge(op.state),el('p',`요청 당시 버전 ${op.revision}`,'muted'));
 if(op.state==='interrupted')card.append(el('p','서버 중단 전에 생성이 완료됐는지 확인할 수 없습니다. 기존 자료와 승인은 유지됩니다. 기록 확인은 같은 요청을 다시 호출하지 않습니다. 새로 생성하기 전에는 외부 호출 원장에서 처리·비용 여부를 확인하세요.','callout'));
 if(op.result?.draft){card.append(el('p','자동 승인되지 않은 제안입니다. 적용하면 새 버전으로 저장되고 모든 항목을 다시 검토합니다. 이전 승인은 과거 버전에 남습니다.','callout'));
 const preview=el('details');preview.append(el('summary','제안 내용 확인'),table(['원문 위치','제안','이유'],op.result.draft.entries.filter(e=>e.kind!=='relation').map(e=>[`${e.source.file} · ${e.source.column||e.source.paragraph}`,e.target||'미정',e.reason])));for(const e of op.result.draft.entries.filter(e=>e.kind!=='relation'&&e.extraction?.source_evidence))preview.append(el('h4',e.source.file+' · '+(e.source.column||e.source.paragraph)),proposalEvidence(e,op.result.draft));for(const relation of op.result.draft.entries.filter(e=>e.kind==='relation')){
  const block=el('section',undefined,'card');
  block.append(el('h4',`${relation.source.file} · ${relation.source.column} → ${relation.target.file} · ${relation.target.column}`),badge(relation.status),el('p',relationOrigin(relation,false),'callout'),el('p',relation.reason,'source-quote'));
  const questions=relation.extraction?.questions||[];
  if(questions.length){block.append(el('h4','확인할 질문'));const list=el('ul');questions.forEach(q=>list.append(el('li',q)));block.append(list);}
  if(relation.extraction?.source_evidence)block.append(proposalEvidence(relation,op.result.draft));
  preview.append(block);
 }
 card.append(preview);
 const adopt=button('이 초안을 새 버전으로 적용',()=>{if(canLeave()&&window.confirm('현재 승인을 새 초안에 승계하지 않고 모두 다시 검토합니다. 새 버전으로 적용할까요?'))task(async()=>show(await api({action:'adopt_suggestions',id:state.current.id,revision:state.current.revision,operation_id:op.id})));});adopt.disabled=!mutable()||op.revision!==state.current.revision;card.append(adopt);
 }else if(op.error)card.append(operationError(op.error));else card.append(el('p','처리 결과가 확정되지 않았습니다. 같은 요청으로 확인하세요.','muted'));
 card.append(button('생성 요청 기록 확인',()=>generateSuggestions(op.request_key,op.revision)));return card;}
function policyResolutionPanel(root){
 for(const group of state.current.policy_groups||[]){
  const box=el('article',undefined,'card');box.append(el('h3','같은 규칙에 연결된 정책 문단'),el('p',group.meaning,'source-quote'),el('p','현재 실행기는 하나의 문단으로 적용 범위를 설명할 수 있는 경우만 지원합니다. 여러 문단을 함께 적용해야 한다면 선택하지 말고 정보 부족으로 남겨 주세요. 문단 선택은 정책의 진실성을 검증하거나 새 규칙을 생성하지 않습니다.','callout'));
  if(group.multiple_approved)box.append(el('p','여러 문단이 승인되어 판단 실행이 보류되었습니다.','callout'));
  for(const entry of group.entries){box.append(el('p',`${entry.source.file} · ${entry.source.line_start}–${entry.source.line_end}행 · ${labels[entry.status]}`,'muted'),el('p',entry.source.text,'source-quote'));}
  const chosen=select([['','문단을 선택하세요'],...group.entries.map(e=>[e.id,`${e.source.file} · 문단 ${e.source.paragraph}`])],''),reason=el('textarea');reason.maxLength=3500;const buffered=state.policies.get(group.target);if(buffered){chosen.value=buffered.selected_id;reason.value=buffered.rationale;}
  box.append(field('단독으로 적용할 문단',chosen),field('적용 대상·시점과 다른 문단을 제외하는 이유',reason));
  const preview=el('div');const review=button('정책 선택 미리보기',()=>{
   preview.replaceChildren();if(!chosen.value||!reason.value.trim()){preview.append(el('p','문단과 적용·제외 이유를 입력하세요.','callout'));return;}
   const selected=chosen.value,rationale=reason.value.trim(),revision=state.current.revision;
   preview.append(table(['원문','저장할 상태'],group.entries.map(e=>[`${e.source.file} · 문단 ${e.source.paragraph}`,e.id===selected?'승인':'제외'])),el('p',rationale));
   preview.append(button('이 선택으로 저장',()=>task(async()=>{
    if(state.edits.size)throw Error('편집 중인 다른 항목을 먼저 저장하세요.');
    const retainedPolicies=new Map(state.policies);retainedPolicies.delete(group.target);
    await show(await api({action:'resolve_policy',id:state.current.id,revision,target:group.target,selected_id:selected,rationale}),new Map(),retainedPolicies);
   }),'primary'));
  });chosen.disabled=reason.disabled=review.disabled=!mutable();
  for(const control of [chosen,reason])control.addEventListener('input',()=>{preview.replaceChildren();state.policies.set(group.target,{target:group.target,selected_id:chosen.value,rationale:reason.value});changed();});
  box.append(review,preview);root.append(box);
 }
}
function reviewBufferPanel(root){
 const box=el('article',undefined,'card'),saved=state.current.review_buffer;
 box.append(el('h3','검토 중인 입력 보관'),el('p','임시 저장은 승인이나 실행에 반영되지 않습니다. 저장한 입력은 서버 재시작 후에도 복원할 수 있습니다. 자료 버전이 바뀌면 자동 적용하지 않습니다.','muted'));
 const save=button('검토 입력 임시 저장',()=>task(async()=>{
  state.current.review_buffer=await api({action:'save_review_buffer',id:state.current.id,revision:state.current.revision,generation:state.current.review_buffer?.generation||0,content:{entries:[...state.edits.values()],policies:[...state.policies.values()],comparisons:state.current.review_buffer?.revision===state.current.revision?(state.current.review_buffer.content.comparisons||[]):[]}});
  state.edited=false;render();$('notice').textContent='검토 입력을 서버에 임시 저장했습니다. 승인 상태는 바뀌지 않았습니다.';
 }));save.disabled=!mutable();box.append(save);
 if(saved){box.append(el('p',`임시 저장: 자료 버전 ${saved.revision} · ${new Date(saved.updated).toLocaleString('ko-KR')}`,'muted'));
  const restore=button('임시 저장한 입력 복원',()=>{
   if(!canLeave())return;
   const latest=state.current.review_buffer;if(!latest||latest.revision!==state.current.revision){$('notice').textContent='자료 버전이 바뀌어 복원할 수 없습니다.';return;}
   state.edits=new Map(latest.content.entries.map(e=>[e.entry_id,e]));state.policies=new Map(latest.content.policies.map(e=>[e.target,e]));state.edited=false;render();
  });restore.disabled=!mutable()||saved.revision!==state.current.revision;box.append(restore);
  if(saved.revision!==state.current.revision)box.append(el('p','다른 자료 버전에서 작성한 입력입니다. 자동 적용할 수 없습니다. 아래 기록을 비교해 다시 검토하세요.','callout'));
  box.append(detail('보관한 입력 확인',saved));
 }
 root.append(box);
}
function policyAgreementPanel(root){
 const names={unreviewed:'대조 전',agrees:'일치 확인',discrepant:'불일치',unresolved:'확인 필요',stale:'자료 변경 · 재검토 필요'};
 const box=el('article',undefined,'card');box.append(el('h2','정책 문서와 표 대조'),el('p','문서의 조건과 표의 값·적용 대상을 비교하세요. 일치 확인은 사용자의 판단이며 자동 검증이 아닙니다. 불일치는 원본 자료나 필드 연결을 수정한 뒤 다시 확인해야 합니다.','callout'));
 for(const [id,current] of Object.entries(state.current.policy_agreements||{})){
  const entry=state.current.draft.entries.find(e=>e.id===id);const row=el('div',undefined,'entry');row.append(el('h3',`${entry.source.file} · 문단 ${entry.source.paragraph}`),el('p',names[current.state]));
  if(current.record)row.append(el('p',current.record.rationale,'source-quote'));
  const open=button('문서와 표 비교하기',()=>{
   if(state.edits.size||state.policies.size){$('error').hidden=false;$('error').textContent='편집 중인 항목과 정책 선택을 먼저 저장하세요. 저장된 값으로 대조합니다.';return;}
   const modal=el('dialog');modal.setAttribute('aria-label','정책 문서와 표 대조');modal.append(el('h2','정책 문서와 표 대조'),el('p',entry.source.text,'source-quote'),el('p',state.current.contracts[entry.target].meaning));
   for(const f of current.inputs.fields){modal.append(el('h3',f.field),el('p',f.source?`${f.source.file} · ${f.source.column}`:'승인한 필드 연결이 없습니다.'));if(!f.records.length)modal.append(el('p','이 표에는 현재 기록이 없습니다. 기록 부재가 정책상 어떤 의미인지 확인하세요.','callout'));modal.append(table(['레코드','원문 행','표의 값'],f.records.map(v=>[v.record,`${v.line_start}–${v.line_end}`,v.value])));}
   const scope=el('details');scope.append(el('summary','적용 대상을 정하는 필드 연결'),el('p','식별자와 참조를 포함한 현재 필드 연결입니다. 아래 원본 값을 함께 확인하세요. 이 목록은 표 사이의 연결이 올바른지 자동 판정하지 않습니다.','muted'));
   for(const m of current.inputs.scope_mappings||[]){const source=state.current.draft.sources.find(s=>s.name===m.source.file);const block=el('details');block.append(el('summary',`${m.source.file} · ${m.source.column} → ${m.target||'미정'} · ${labels[m.status]||m.status}`));if(source)block.append(table(['레코드','원본 값'],source.rows.map((r,i)=>[i+1,r[m.source.column]])));scope.append(block);}modal.append(scope);
   const decision=select([['unresolved','아직 확인할 수 없음'],['discrepant','문서와 표가 다름'],['agrees','값과 적용 범위가 일치함']],current.state==='stale'?'unresolved':current.record?.decision||'unresolved');
   const basis=select([['unresolved','계산 기준 확인 필요'],['before_discount','할인 전 금액'],['after_discount','할인 후 금액'],['not_applicable','금액 기준과 무관한 정책']],current.state==='stale'?'unresolved':current.record?.basis||'unresolved');
   const reason=el('textarea');reason.maxLength=3500;reason.value=current.record?.rationale||'';
   modal.append(field('대조 결과',decision),field('계산 기준',basis),field('비교한 값·적용 대상·남은 차이',reason),el('p','대조 입력 임시 저장으로 작성 중인 내용을 보관할 수 있습니다. 임시 저장은 판단 실행에 반영되지 않습니다. 할인 후 계산은 현재 지원하지 않습니다.','muted'));
   let dirty=false;for(const control of [decision,basis,reason])control.addEventListener('input',()=>dirty=true);
   const close=()=>{if(!dirty||window.confirm('저장하지 않은 대조 입력을 닫을까요?'))modal.close();};
   const protectUnload=event=>{if(dirty){event.preventDefault();event.returnValue='';}};window.addEventListener('beforeunload',protectUnload);
   modal.addEventListener('cancel',event=>{event.preventDefault();close();});modal.addEventListener('close',()=>{window.removeEventListener('beforeunload',protectUnload);modal.remove();});
   const feedback=el('p',undefined,'callout');feedback.setAttribute('role','alert');modal.append(feedback);
   const request={action:'compare_policy',id:state.current.id,revision:state.current.revision,entry_id:id,binding:current.binding};
   const recovery=el('div');modal.append(recovery);
   const latestComparison=()=>{const saved=state.current.review_buffer;return {saved,buffered:saved?.content.comparisons?.find(c=>c.entry_id===id)};};
   const canRestore=({saved,buffered})=>Boolean(buffered&&saved.revision===request.revision&&state.current.revision===request.revision&&state.current.id===request.id&&buffered.binding===current.binding);
   const refreshRecovery=()=>{
    recovery.replaceChildren();const latest=latestComparison();if(!latest.buffered)return;
    const restore=button('보관한 대조 입력 복원',()=>{
     const now=latestComparison();if(!canRestore(now)){feedback.textContent='자료 상태가 바뀌어 복원할 수 없습니다.';refreshRecovery();return;}
     if(dirty&&!window.confirm('현재 입력을 보관한 내용으로 바꿀까요?'))return;
     decision.value=now.buffered.decision;basis.value=now.buffered.basis;reason.value=now.buffered.rationale;dirty=false;feedback.textContent='임시 저장 입력을 복원했습니다. 대조 결과는 별도로 저장해야 합니다.';
    });
    restore.disabled=!canRestore(latest);recovery.append(restore);
    if(restore.disabled)recovery.append(el('p','다른 자료 상태에서 보관한 입력입니다. 자동 복원하지 않습니다.','callout'));
    recovery.append(detail('보관한 대조 입력',latest.buffered));
   };refreshRecovery();
   modal.append(button('대조 입력 임시 저장',()=>task(async()=>{
    try{const saved=state.current.review_buffer;
     const content=saved?.revision===state.current.revision?saved.content:{entries:[],policies:[]};
     const comparisons=(content.comparisons||[]).filter(c=>c.entry_id!==id);
     comparisons.push({entry_id:id,binding:current.binding,decision:decision.value,basis:basis.value,rationale:reason.value});
     state.current.review_buffer=await api({action:'save_review_buffer',id:request.id,revision:request.revision,generation:saved?.generation||0,content:{...content,comparisons}});
     dirty=false;refreshRecovery();feedback.textContent='대조 입력을 서버에 보관했습니다. 승인과 대조 결과는 바뀌지 않았습니다.';
    }catch(error){feedback.textContent=error.message;throw error;}
   })));

   modal.append(button('닫기',close),button('대조 결과 저장',()=>task(async()=>{
    try{const updated=await api({...request,decision:decision.value,basis:basis.value,rationale:reason.value});dirty=false;modal.close();await show(updated);}
    catch(error){feedback.textContent=error.message;throw error;}
   }),'primary'));
   document.body.append(modal);modal.showModal();
  });open.disabled=!mutable();row.append(open);box.append(row);
 }
 root.append(box);
}

function manualRelationPanel(root){
 const tables=state.current.draft.sources.filter(s=>s.kind==='table');if(tables.length<2)return;
 const card=el('details',undefined,'card');card.append(el('summary','관계 직접 추가'),el('p','자동 제안에 없는 연결을 두 파일의 열에서 선택하세요. 추가한 뒤 의미와 원본 값을 검토해야 하며, 자동 승인되거나 조회되지 않습니다.','muted'));
 const options=tables.flatMap(s=>s.headers.map(column=>[JSON.stringify({file:s.name,column}),`${s.name} · ${column}`]));
 const left=select(options,options[0][0]),right=select(options,options.find(([v])=>JSON.parse(v).file!==tables[0].name)[0]),reason=el('textarea');reason.maxLength=4000;
 card.append(field('기준 파일과 열',left),field('연결할 파일과 열',right),field('연결을 제안하는 이유',reason));
 const add=button('검토 대기로 추가',()=>task(async()=>{const edits=new Map(state.edits),policies=state.policies;const row=await api({action:'add_relation',id:state.current.id,revision:state.current.revision,source:JSON.parse(left.value),target:JSON.parse(right.value),reason:reason.value});await show(row,edits,policies);if(edits.size||policies.size)changed();}));
 for(const control of [left,right,reason,add])control.disabled=!mutable();card.append(add);root.append(card);
}
function renderReview(root){manualRelationPanel(root);policyAgreementPanel(root);reviewBufferPanel(root);modelProposalPanel(root);policyResolutionPanel(root);heading(root,'자료의 의미 검토','자동 제안은 승인되지 않은 초안입니다. 저장한 결정은 새 버전으로 남습니다.');const maps=state.current.draft.entries.filter(e=>e.kind==='mapping');for(const name of [...new Set(maps.map(e=>e.source.file))]){const card=el('article',undefined,'card');card.append(el('h3',name),el('p','열 이름과 실제 값을 확인한 항목만 선택해 승인하세요.','muted'));const editors=maps.filter(e=>e.source.file===name).map(e=>decisionEditor(e,true));const fields=el('details');fields.append(el('summary',`${editors.length}개 필드 연결 검토`));editors.forEach(e=>fields.append(e.card));card.append(fields);const approve=button('선택한 필드 승인 미리보기',()=>{const decisions=editors.filter(e=>e.checked.checked).map(e=>({...e.value(),status:'approved'}));if(!decisions.length){$('error').hidden=false;$('error').textContent='먼저 승인할 필드를 선택하세요.';return;}previewDecisions(decisions);},'primary');approve.disabled=!mutable();card.append(approve);root.append(card);}for(const [kind,title] of [['policy','정책의 적용 범위'],['relation','표 사이의 연결 후보 · 검토 기록']]){const entries=state.current.draft.entries.filter(e=>e.kind===kind);const card=el('article',undefined,'card');card.append(el('h2',title));if(!entries.length)card.append(el('p','이 자료에서 제안된 항목이 없습니다.','muted'));entries.forEach(e=>card.append(decisionEditor(e).card));root.append(card);}}
function previewDecisions(decisions){
 const modal=el('dialog',undefined,'approval-preview');modal.setAttribute('aria-labelledby','approval-title');
 const title=el('h2',`${decisions.length}개 필드 승인`);title.id='approval-title';
 modal.append(title,el('p',`현재 버전 ${state.current.revision}의 선택한 필드만 승인합니다. 아래 업무 의미와 연결을 확인하세요. 다른 항목의 편집 내용은 별도로 저장해야 합니다.`,'muted'));
 let invalid=false;
 for(const d of decisions){
  const entry=state.current.draft.entries.find(e=>e.id===d.entry_id),box=el('section',undefined,'card');
  if(!entry||entry.kind!=='mapping'){invalid=true;box.append(el('p','원본 필드를 확인할 수 없습니다. 검토 화면으로 돌아가세요.','callout'));modal.append(box);continue;}
  const source=state.current.draft.sources.find(s=>s.name===entry.source.file),control=targetControl({...entry,target:d.target});
  const targetLabel=control.selectedOptions?.[0]?.textContent||d.target||'선택 필요';
  box.append(el('h3',entry.source.file+' · '+entry.source.column),kv({'승인할 연결':targetLabel,'저장할 업무 의미':d.interpretation||'입력하지 않음','메모':d.note||'없음'}));
  if(!d.target||(d.target==='source_only'&&!d.interpretation.trim())){
   invalid=true;box.append(el('p',!d.target?'연결할 필드를 선택하거나 원본 조회 용도를 지정하세요.':'원본 조회에 사용할 필드의 업무 의미를 입력하세요.','callout'));
  }
  if(source)box.append(el('p','원본의 첫 3개 레코드 · 전체 값 검증은 아닙니다.','muted'),table(['원문 행','원본 값'],source.rows.slice(0,3).map((r,i)=>[source.locations[i].line_start+'–'+source.locations[i].line_end,r[entry.source.column]])));
  if(entry.extraction?.source_evidence)box.append(proposalEvidence(entry));
  modal.append(box);
 }
 const close=button('돌아가기',()=>modal.close());
 const apply=button('선택한 내용 승인',()=>{modal.close();task(()=>saveDecisions(decisions));},'primary');apply.disabled=invalid||!mutable();
 modal.append(close,document.createTextNode(' '),apply);
 modal.addEventListener('close',()=>modal.remove());document.body.append(modal);modal.showModal();
}
function savedCases(){if(Array.isArray(state.current.cases))return state.current.cases;const entries=state.current.draft.entries.filter(e=>e.kind==='mapping'&&e.status==='approved');const id=entries.find(e=>e.target==='cases.id'),question=entries.find(e=>e.target==='cases.question'),label=entries.find(e=>e.target==='cases.label');if(!id||!question||id.source.file!==question.source.file)return [];const source=state.current.draft.sources.find(s=>s.name===id.source.file);return source.rows.map(r=>({id:r[id.source.column],question:r[question.source.column],label:label&&label.source.file===source.name?r[label.source.column]:''}));}
function relationLookupForm(){const card=el('article',undefined,'card');card.append(el('h3','두 CSV의 같은 값 대조'),el('p','직접 선택한 관계의 두 열에서 같은 문자열을 찾습니다. 중복 행을 모두 표시하며 같은 업무 객체인지, 정책이 적용되는지는 판단하지 않습니다.','muted'));const catalog=state.current.relation_catalog||[];if(!catalog.length){card.append(el('p','설명을 적고 승인한 관계와 양쪽 열의 승인이 필요합니다. 데이터 정리에서 확인하세요.','muted'));return card;}const choice=select(catalog.map(r=>[r.relation_id,`${r.source.file} · ${r.source.column} ↔ ${r.target.file} · ${r.target.column}`]),catalog[0].relation_id);choice.setAttribute('aria-label','대조할 관계');const value=input();value.maxLength=2000;value.setAttribute('aria-label','양쪽 열에서 찾을 값');const run=button('두 CSV 대조 실행',()=>{if(!value.value.trim()){value.setCustomValidity('공백이 아닌 값을 입력하세요.');value.reportValidity();return;}execute(null,crypto.randomUUID(),state.current.revision,null,{relation_id:choice.value,value:value.value});});value.addEventListener('input',()=>value.setCustomValidity(''));run.disabled=!mutable();card.append(field('대조할 관계',choice),field('양쪽 열에서 찾을 값',value),run);return card;}
function relationResult(result){const box=el('div');box.append(el('p','선택한 두 열의 정확한 문자열 대조입니다. 같은 업무 객체라는 뜻은 아니며 정책·제약·추론 검사는 수행하지 않았습니다.','callout'),el('p',`찾은 값: ${result.value}`));for(const side of ['source','target']){const data=result.sides[side];box.append(el('h4',`${data.scope.file} · ${data.scope.column} · ${data.records.length}행`));if(!data.records.length)box.append(el('p','선택한 파일의 이 열에서는 일치하는 행을 찾지 못했습니다. 다른 자료에도 없다는 뜻은 아닙니다.','callout'));for(const row of data.records)box.append(table(['원본 열','값'],Object.entries(row.values)),el('p',`${row.source.file} · CSV 레코드 ${row.record} · 원문 ${row.source.line_start}–${row.source.line_end}행`,'muted'));}box.append(detail('검토한 관계 설명 · 원본 출처',result));return box;}
function documentLookupForm(){const card=el('article',undefined,'card');card.append(el('h3','승인한 문단 직접 읽기'),el('p','모델 호출 없이 원문을 확인하고 조회 기록을 저장합니다. 정책 적용 여부는 판단하지 않습니다.','muted'));const catalog=state.current.document_catalog||[];if(!catalog.length){card.append(el('p','데이터 정리에서 승인한 문단이 없습니다. 전체 원문은 자료실에서 확인할 수 있습니다.','muted'));return card;}const choice=select(catalog.map(e=>[e.entry_id,`${e.file} · 문단 ${e.paragraph} · ${e.preview.slice(0,60)}`]),catalog[0].entry_id);choice.setAttribute('aria-label','확인할 승인 문단');const run=button('선택한 문단 조회',()=>execute(null,crypto.randomUUID(),state.current.revision,null,{entry_id:choice.value}));run.disabled=!mutable();card.append(field('확인할 승인 문단',choice),run);return card;}
function rowLookupForm(){
 const card=el('article',undefined,'card');card.append(el('h3','원본 열로 행 찾기'),el('p','주문번호가 여러 행에 반복되어도 모두 표시합니다. 승인한 열만 사용하며 합계나 정책 판단은 하지 않습니다.','muted'));
 const choices=state.current.row_lookup_catalog||[];
 if(!choices.length){card.append(el('p','조회할 열을 데이터 정리에서 먼저 검토하고 승인하세요.','empty'));return card;}
 const column=select(choices.map(c=>[c.entry_id,`${c.file} · ${c.column}`]),choices[0].entry_id),value=input('');value.maxLength=2000;
 const run=button('일치하는 원본 행 조회',()=>execute(null,crypto.randomUUID(),state.current.revision,null,{entry_id:column.value,value:value.value}),'primary');run.disabled=!mutable();
 card.append(field('조건을 지정할 원본 열',column),field('정확히 일치할 값 (빈 값도 가능)',value),run);return card;
}
function lookupForm(){
 const card=el('article',undefined,'card');card.append(el('h3','승인한 필드로 원본 기록 확인'),el('p','정책 검토가 끝나지 않아도 확인한 필드의 원문은 조회할 수 있습니다. 처리 가능 여부를 판단하는 기능은 아닙니다.','muted'));
 const names={orders:'주문',items:'주문 항목',products:'상품',skus:'상품 옵션',coupons:'쿠폰',shipping_policies:'배송 정책',consents:'고객 동의',approvals:'승인 기록'};
 const choices=state.current.lookup_catalog||[];
 if(!choices.length){card.append(el('p','데이터 정리에서 조회할 자료의 ID 필드 연결을 승인하세요.','callout'));return card;}
 const tableSelect=select(choices.map(c=>[c.table,`${names[c.table]||c.table} · ${c.file}`]),choices[0].table),identifier=input();
 tableSelect.setAttribute('aria-label','조회할 자료');identifier.setAttribute('aria-label','조회할 식별자');identifier.maxLength=2000;
 const hint=el('p',undefined,'muted');const update=()=>{const c=choices.find(c=>c.table===tableSelect.value);hint.textContent='원본 식별자 예시: '+c.identifiers.slice(0,5).join(', ');};tableSelect.onchange=update;update();
 const run=button('원본 기록 조회',()=>execute(null,crypto.randomUUID(),state.current.revision,null,{table:tableSelect.value,identifier:identifier.value}),'primary');run.disabled=!mutable();
 card.append(field('조회할 자료',tableSelect),field('조회할 식별자',identifier),hint,run);return card;
}
function proposalForm(){
 const card=el('article',undefined,'card');card.append(el('h3','주문 항목 변경안 검토'),el('p','질문 파일 없이 변경안을 지정합니다. 승인 자료로 정해진 조회·계산·검토를 실행하며 실제 주문은 변경하지 않습니다.','muted'));
 const options=target=>{const matches=state.current.draft.entries.filter(e=>e.kind==='mapping'&&e.status==='approved'&&e.target===target);if(matches.length!==1)return [];const ref=matches[0].source;const src=state.current.draft.sources.find(s=>s.name===ref.file);return src.rows.map(r=>[r[ref.column],r[ref.column]]);};
 const items=options('items.id'),skus=options('skus.id'),item=select(items,''),replacement=select(skus,'');
 item.setAttribute('aria-label','변경할 주문 항목');replacement.setAttribute('aria-label','대체 상품 옵션');
 card.append(field('변경할 주문 항목',item),field('대체 상품 옵션',replacement));
 const flags={};for(const [key,label] of [['retain_discount','기존 할인 유지 요청'],['free_shipping','무료배송 요청'],['split','부분 출고 요청'],['promise_arrival','요청 도착일 약속 검토']]){flags[key]=input('','checkbox');card.append(field(label,flags[key]));}
 const run=button('변경안 검토 실행',()=>{const proposal={item:item.value,replacement:replacement.value};for(const [k,v] of Object.entries(flags))proposal[k]=v.checked;execute(null,crypto.randomUUID(),state.current.revision,proposal);},'primary');run.disabled=!mutable()||!items.length||!skus.length;card.append(run);
 if(!items.length||!skus.length)card.append(el('p','주문 항목 ID와 상품 옵션 ID 필드 연결을 먼저 승인하세요. 나머지 자료·정책의 실행 가능 여부는 서버에서 검사합니다.','callout'));
 return card;
}
function questionForm(){
 const box=el('article',undefined,'card'),info=state.current.model_questions||{};
 box.append(el('h2','내 자료에 질문하기'),el('p',info.enabled?`모델 ${info.model} · 현재 승인 자료 버전 ${state.current.revision}에 질문합니다.`:'현재 서버는 자유 질문 모델을 활성화하지 않았습니다. 아래 원본 조회와 고정 검토는 사용할 수 있습니다.','muted'));
 const question=el('textarea');question.maxLength=6000;question.rows=4;question.placeholder='예: O1 주문 내용을 확인하고 환불 가능 여부도 알려줘';question.setAttribute('aria-label','자료에 대한 질문');
 const draftKey='operations-question-draft-'+state.current.id;question.value=recalled(draftKey)||'';
 question.addEventListener('input',()=>remember(draftKey,question.value));
 const run=button('질문 보내기',()=>{
  if(!question.value.trim())return;
  if(window.confirm('질문과 조회에 필요한 식별자·근거를 외부 모델에 보냅니다. 공유 예산에서 최대 2회 호출하며 자동 재시도하지 않습니다. 진행할까요?'))askQuestion(question.value,crypto.randomUUID());
 },'primary');run.disabled=!mutable()||!info.enabled||Boolean(recalled('operations-request-'+state.current.id));question.disabled=!mutable();
 question.addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();if(!run.disabled)run.click();}});
 box.append(field('질문 · Enter 전송, Shift+Enter 줄바꿈',question),run,el('p','승인한 필드로 원본을 조회하거나 지원하는 고정 검토를 실행합니다. 주문·환불 등의 업무 처리는 수행하지 않습니다.','muted'));return box;
}
function operationProgressText(p){
 const terminal={completed:'실행 완료 · 저장된 결과 확인 중',failed:'실행 실패 · 저장된 기록 확인 중',cancelled:'실행 취소됨 · 저장된 기록 확인 중',interrupted:'서버 중단으로 실행이 끝났습니다. 저장된 기록을 확인하세요. 자동으로 다시 호출하지 않습니다.'};
 if(Object.hasOwn(terminal,p.state))return terminal[p.state];
 if(p.cancel_requested)return '취소 요청됨 · 진행 중인 응답을 기다립니다. 이미 시작한 호출은 과금될 수 있습니다.';
 if(p.state==='not_recorded')return '서버 접수 기록을 기다리는 중';
 if(p.kind==='model_suggestions')return '초안 생성 처리 중 · 완료 여부를 확인하고 있습니다. 승인 내용은 바뀌지 않습니다.';
 const phases={planning:'질문 해석 · 조회 선택 중',retrieving:'선택한 도구로 근거 조회 중',answering:'조회 근거로 답변 작성 중',completed:'답변 저장 중'};
 return `${Object.hasOwn(phases,p.phase)?phases[p.phase]:'실행 접수 · 자료 버전 준비 중'} · 조회 완료 ${p.tools_completed||0}개 / 실패 ${p.tools_failed||0}개`;
}
function watchQuestionProgress(id,requestKey){
 let stopped=false,timer;
 const cancel=button('실행 취소',async()=>{cancel.disabled=true;try{const p=await api({action:'cancel',id,request_key:requestKey});if(!stopped)$('notice').textContent=operationProgressText(p);}catch(e){if(!stopped){$('notice').textContent=e.message;cancel.disabled=false;}}});
 cancel.disabled=true;$('notice').insertAdjacentElement('afterend',cancel);
 const poll=async()=>{try{const p=await api({action:'progress',id,request_key:requestKey});if(stopped)return;cancel.disabled=p.state!=='running'||p.cancel_requested;$('notice').textContent=operationProgressText(p);}catch{if(!stopped)$('notice').textContent='진행 상태를 확인하지 못했습니다. 실행 결과를 기다리고 있으며 다시 요청하지 않습니다.';}finally{if(!stopped)timer=setTimeout(poll,800);}};
 timer=setTimeout(poll,200);return ()=>{stopped=true;clearTimeout(timer);cancel.remove();};
}
async function askQuestion(question,requestKey,revision=state.current.revision){
 await task(async()=>{
  const key='operations-request-'+state.current.id,pending=recalled(key);
  if(pending&&JSON.parse(pending).request_key!==requestKey)throw Error('먼저 원래 요청의 결과를 확인하세요.');
  remember(key,JSON.stringify({question,request_key:requestKey,revision}));
  $('notice').textContent='질문을 처리하고 있습니다. 완료 전에는 자동으로 다시 보내지 않습니다.';
  const stopProgress=watchQuestionProgress(state.current.id,requestKey);
  try{
   const result=await api({action:'ask',id:state.current.id,revision,request_key:requestKey,question});
   stopProgress();
   if(result.operation.state!=='running')remember(key,null);
   remember('operations-question-draft-'+state.current.id,null);
   await showExecution(result.operation);
   $('notice').textContent=result.operation.state==='completed'?'답변과 근거를 저장했습니다.':'현재 실행 상태와 남은 근거를 확인하세요.';
  }catch(error){render();throw error;}finally{stopProgress();}
 });
}
function reviewedFieldMeaning(result){const block=el('details');block.append(el('summary','사용자가 설명한 필드 의미'));const fields=(result.scope?.reviewed_columns||[]).filter(c=>c.reviewed_interpretation);if(fields.length)block.append(table(['원본 열','승인한 연결','사용자 설명'],fields.map(c=>[c.column,c.reviewed_target,c.reviewed_interpretation])));else block.append(el('p','이 실행에 저장된 필드 설명이 없습니다.'));block.append(el('p','사용자의 검토 설명이며 원본 사실이나 실행 가능한 규칙이 아닙니다.','muted'));return block;}
function questionBinding(evidence){
 const panel=el('section',undefined,'source-quote'),binding=evidence.binding;
 panel.append(el('h4','앞선 조회에서 가져온 값'));
 if(binding&&typeof binding.value==='string'){
  panel.append(kv({'앞선 근거':binding.from_evidence,'사용한 원본 열':binding.column,'다음 조회에 전달한 값':binding.value}),el('p','앞선 조회의 모든 행에서 같은 값이 확인되어 전달했습니다. 어떤 열을 연결할지는 모델이 선택했으며, 업무상 같은 의미인지 확인한 것은 아닙니다.','muted'));
  const locations=el('details');locations.append(el('summary','값을 가져온 원본 위치'));
  const records=Array.isArray(binding.records)?binding.records:[];
  locations.append(table(['파일','CSV 레코드','원문 행'],records.map(r=>[r.file,r.record,r.line_start===undefined?'기록 없음':`${r.line_start}–${r.line_end??r.line_start}`])));
  panel.append(locations,detail('실제로 전달한 조회 조건',evidence.resolved_arguments||{}));
 }else{
  const reasons={
   'Invalid evidence binding; select an earlier source_rows evidence and column':'연결할 조회와 열을 지정하는 형식이 올바르지 않습니다.',
   'Binding requires a successful earlier source_rows result':'앞선 원본 행 조회가 완료되지 않았거나 연결할 조회를 찾지 못했습니다.',
   'Binding source is not raw source rows':'이 조회 결과는 원본 행 연결에 사용할 수 없습니다.',
   'Binding source has no matching records':'앞선 조회에서 일치하는 행을 찾지 못했습니다.',
   'Binding column is unavailable, blank or exceeds the value limit':'연결할 열이 승인된 결과에 없거나, 값이 비어 있거나, 길이 한도를 넘었습니다.',
   'Binding source contains multiple distinct values; no row was selected':'앞선 조회에 서로 다른 값이 있어 하나를 임의로 선택하지 않았습니다.'};
  panel.append(el('p',Object.hasOwn(reasons,evidence.error)?reasons[evidence.error]:'앞선 조회의 값을 연결하지 못했습니다. 상세 오류를 확인하세요.','callout'),el('p','이 연결을 사용한 조회는 실행되지 않았습니다. 원본 기록과 연결할 열을 확인한 뒤 질문을 구체화하세요. 새 질문 실행에는 모델 호출이 사용될 수 있습니다.','muted'));
 }
 return panel;
}
function questionResult(op){
 const r=op.result||{},card=el('article',undefined,'card');card.append(el('h3',op.request.question),badge(op.state),el('p',`자료 버전 ${op.revision} · ${op.revision===state.current.revision?'현재 선택한 버전':'과거 버전의 결과'} · ${r.model||'모델 실행 정보 없음'}`,'muted'));
 if(r.answer)card.append(answerNode(r.answer));
 if(op.error)card.append(operationError(op.error));
 if(r.failure?.kind==='context_limit')card.append(el('p',`${r.failure.phase==='answering'?'조회 결과를 답변으로 작성':'질문에 사용할 조회를 선택'}하기 전에 입력 크기 한도를 넘었습니다 (${r.failure.message_bytes.toLocaleString()} / ${r.failure.limit_bytes.toLocaleString()}바이트). 이 단계의 모델 요청은 보내지 않았습니다. ${r.failure.phase==='answering'?'조회한 근거는 아래에서 확인할 수 있습니다. 조회 대상이 줄어들도록 질문을 구체화할 수 있지만 입력 한도 내 실행을 보장하지는 않습니다.':'조회 목록 자체가 큰 경우 질문을 짧게 바꿔도 해결되지 않습니다. 모델 조회는 시작하지 않았습니다. 질문 화면의 원본 열로 행 찾기를 이용해 필요한 기록을 직접 확인하세요.'} 새 질문 실행은 새 모델 호출을 사용할 수 있습니다. 동일 요청 기록 확인은 모델을 다시 호출하지 않습니다.`,'callout'));
 if(r.unresolved?.length){card.append(el('h4','아직 답하지 못한 요구'));const list=el('ul');r.unresolved.forEach(text=>list.append(el('li',text)));card.append(list);}
 card.append(el('p','모델의 해석과 답변은 별도 검토가 필요합니다. 근거 ID 일치나 제약 통과가 답변의 사실성을 보증하지 않습니다.','muted'));
 for(const evidence of r.evidence||[]){const block=el('details');block.append(el('summary',`${evidence.id} · ${evidence.tool} · ${labels[evidence.state]||evidence.state}${r.citations?.includes(evidence.id)?' · 답변에서 참조':''}`));
  block.append(el('p',evidence.parameter_origin==='model_selected_source_binding'?'모델이 앞선 조회의 열을 선택하고, 그 결과에서 확인한 값을 다음 조회에 전달했습니다.':evidence.parameter_origin==='model_interpretation'?'조회 조건은 모델이 질문을 해석해 선택했습니다. 사용자가 각 값을 확인한 것은 아닙니다.':'이 기록에는 조회 조건의 출처가 별도로 저장되지 않았습니다. 실행 요청을 확인하세요.','muted'),detail('사용한 조회 조건',evidence.arguments||{}));
  if(evidence.binding||evidence.failure_kind==='unresolved_binding')block.append(questionBinding(evidence));
  if(evidence.error)block.append(el('p',evidence.error,'callout'));
  const result=evidence.result;if(result?.mode==='source_document'){block.append(el('p','승인한 문서 원문 · 정책 적용 여부는 확인하지 않았습니다.','callout'),el('p',result.source.text,'source-quote'),el('p',`${result.source.file} · 원문 ${result.source.line_start}–${result.source.line_end}행`,'muted'),detail('검토한 해석 · 날짜 역할',result.review));}else if(result?.mode==='source_lookup'){block.append(el('p',result.notice),reviewedFieldMeaning(result));for(const record of result.records)block.append(table(['필드','원본 값'],Object.entries(record.values)),el('p',`${record.source.file} · CSV 레코드 ${record.record}`,'muted'));}
  else if(result?.mode==='reviewed_relation_rows'){block.append(relationResult(result));}
  else if(result?.mode==='recorded_stock_check'){
   const names={recorded_quantity_sufficient:'기록된 수량 충족',recorded_quantity_insufficient:'기록된 수량 부족',unknown:'수량 판단 보류'};
   const reasons={not_found_in_selected_source:'선택한 파일에 해당 SKU가 없습니다.',ambiguous_sku_records:'같은 SKU의 행이 여러 개라 합산하거나 하나를 선택하지 않았습니다.',available_quantity_missing:'가용 수량이 비어 있습니다.',available_quantity_format_unsupported:'가용 수량 형식을 정수로 해석할 수 없습니다.'};
   block.append(el('h4',names[result.status]||result.status),el('p','이 자료 버전의 기록 수량만 비교했습니다. 재고 예약·대체 상품 적합성·할인·배송·주문 변경 승인은 확인하지 않았습니다.','muted'));
   if(result.reason)block.append(el('p',reasons[result.reason]||result.reason,'callout'));
   if(result.comparison)block.append(kv({'기록된 가용 수량':result.comparison.available,'모델이 선택한 요청 수량':result.comparison.requested,'Python 비교':result.comparison.same_policy_python_pass?'충족':'부족','제약 검사':result.validation.shacl_conforms?'충족':'부족'}));
   for(const record of result.records)block.append(table(['필드','원본 값'],Object.entries(record.values)),el('p',`${record.source.file} · CSV 레코드 ${record.source.record}`,'muted'));
   block.append(detail('검사 범위와 원본 근거',result));
  }
  else if(result){block.append(detail('조회한 근거',result.facts||result.evidence||{}),detail('제약 검토',result.shacl||{}),detail('분류·추론',result.owl||{}));}
  block.append(detail('실행 요청과 원본 기록',evidence));card.append(block);
 }
 card.append(button('이 질문의 저장된 실행 확인',()=>askQuestion(op.request.question,op.request_key,op.revision)),detail('실행 단계·모델 응답·자료 연결',r));return card;
}
function questionPanel(key,title,description,defaultOpen=false){
 const panel=el('details',undefined,'card question-tools');
 const id=state.current.id+':'+key;
 state.questionPanels??={};
 panel.open=state.questionPanels[id]??defaultOpen;
 panel.append(el('summary',title),el('p',description,'muted'));
 panel.addEventListener('toggle',()=>{state.questionPanels[id]=panel.open;});
 return panel;
}
function reviewNavigation(){return button('데이터 정리로 이동',()=>{state.tab='review';render();document.querySelector('[data-tab="review"]')?.focus();});}
function operationError(error){
 const box=el('div',undefined,'callout');
 const messages={
  'Review the source column before querying its rows':'이 실행에서 선택한 열은 승인된 조회 대상이 아닙니다. 현재 자료의 열 의미와 승인 상태를 확인한 뒤 새로 조회하세요.',
  'Approve exactly one identifier field for this table first':'조회할 자료의 식별자 연결이 확정되지 않았습니다. 데이터 정리에서 해당 ID 필드 연결을 확인하세요.'
 };
 if(Object.hasOwn(messages,error))box.append(el('p',messages[error]),reviewNavigation(),detail('원래 오류 기록',error));
 else box.append(el('p',error));
 return box;
}
function taskReadinessPanel(){
 const report=state.current.task_readiness;if(!report)return el('div');
 const card=el('article',undefined,'card');card.dataset.testid='task-readiness';
 card.append(el('h3','현재 자료로 할 수 있는 일'));
 const labels={source_rows:'승인한 열로 원본 행 찾기',source_document:'승인한 문단 읽기',relation_rows:'승인한 관계의 양쪽 자료 대조',stock_check:'기록된 재고와 요청 수량 비교'};
 for(const [key,label] of Object.entries(labels)){const count=report.capabilities[key]||0;card.append(el('p',`${label} · ${count?`${count}개 조회 범위 준비됨`:'먼저 관련 자료를 승인하세요'}`));}
 card.append(el('p','조회 범위가 준비되어도 원하는 값이 없거나 모호할 수 있습니다. 문단 조회는 정책 적용 여부를 검사하지 않습니다.','muted'));
 if(report.replacement){const replacement=report.replacement,details=el('details');
 details.append(el('summary',replacement.issues.length?`대체 상품 검토 · 준비 항목 ${replacement.issues.length}건 확인`:'대체 상품 검토 · 실행 시 값과 참조 확인 필요'));
 details.append(el('p','대체 상품 검토는 정해진 주문·상품·재고·정책 구조를 요구합니다. 아래 안내만으로 변경안이 승인되거나 실행되지는 않습니다.','muted'));
 const codes={currency:'현재 변경안 계산은 KRW만 지원',pending:'승인 또는 제외할 항목',policy_missing:'해석·승인이 필요한 정책',policy_multiple:'적용할 원문을 선택할 정책',field_missing:'연결·승인이 필요한 필드',field_multiple:'중복 연결을 정리할 필드',collection_split:'한 CSV로 준비해야 하는 자료 묶음',policy_scope:'정책의 날짜·적용 범위 확인',policy_agreement:'정책과 계산 기준 대조'};
 const list=el('ul');for(const issue of replacement.issues){const title=Object.hasOwn(codes,issue.code)?codes[issue.code]:issue.code;list.append(el('li',`${title}: ${issue.subject}${issue.entry_ids.length?` (${issue.entry_ids.length}개 항목)`:''}`));}details.append(list,reviewNavigation());
 details.append(el('p','입력 값 형식, 식별자 중복, 자료 간 참조와 선택한 변경안은 실행할 때 다시 검사합니다. 원본의 진실성과 완전성은 보장하지 않습니다.','muted'));card.append(details);
 }
 return card;
}
function renderQuestions(root){
 root.append(questionForm(),taskReadinessPanel());
 const pendingRequest=recalled('operations-request-'+state.current.id);if(pendingRequest){try{const request=JSON.parse(pendingRequest);const recovery=el('article',undefined,'card');recovery.append(el('h3','응답 확인이 필요한 요청'),el('p',`질문 ${request.question||request.case_id||'원본 조회·변경안'} · 버전 ${request.revision}. 같은 요청 키로 원래 기록을 확인합니다. 서버가 받지 못한 요청이면 최초 실행이 진행됩니다.`,'muted'),button('원래 요청 확인',()=>request.question!==undefined?askQuestion(request.question,request.request_key,request.revision):execute(request.case_id,request.request_key,request.revision,request.proposal,request.selection)),button('미접수 요청 철회 · 상태 확인',()=>withdrawPending(request)));root.append(recovery);}catch{}}
 heading(root,'실행 기록','답변과 근거를 먼저 확인하세요. 이전 결과에는 실행 당시의 자료 버전이 표시됩니다.');
 if(!state.current.operations.length)root.append(el('div','아직 실행한 질문이 없습니다. 질문을 보내거나 아래 직접 조회 도구를 이용하세요.','empty'));
 state.current.operations.forEach(op=>root.append(operationCard(op)));
 appendHistoryMore(root);
 const tools=questionPanel('direct','직접 조회 · 변경안 검토','모델을 호출하지 않고 원본 행을 찾거나 정해진 조건으로 변경안을 검토합니다.',!state.current.model_questions?.enabled);
 const available=[['relation_catalog',relationLookupForm],['document_catalog',documentLookupForm],['row_lookup_catalog',rowLookupForm],['lookup_catalog',lookupForm]];
 for(const [key,form] of available)if(state.current[key]?.length)tools.append(form());
 const entries=state.current.draft.entries;
 const hasTarget=target=>entries.some(e=>e.kind==='mapping'&&e.target===target&&e.status!=='excluded');
 if(state.current.draft.adapter==='commerce-csv-1'&&hasTarget('items.id')&&hasTarget('skus.id'))tools.append(proposalForm());
 if(!available.some(([key])=>state.current[key]?.length))tools.append(el('p','아직 승인된 조회 항목이 없습니다. 데이터 정리에서 원본 열이나 문단의 의미를 확인하고 승인하세요.','empty'));
 const pending=entries.filter(e=>!['approved','excluded'].includes(e.status)).length;
 if(pending){const guide=el('div',undefined,'callout');guide.append(el('p',`검토 대기 ${pending}개 · 승인된 항목은 지금 조회할 수 있습니다. 나머지는 데이터 정리에서 확인하세요.`),reviewNavigation());tools.append(guide);}
 root.append(tools);
 const cases=savedCases();
 if(!cases.length)return;
 const templates=questionPanel('templates','저장된 예제 질문','CSV에 저장된 질문을 고정 규칙으로 실행합니다. 자유 질문과는 별도이며 모델을 호출하지 않습니다.');
 if(state.current.readiness?.ready===false)templates.append(el('p','예제 질문 실행 전 확인: '+state.current.readiness.reason,'callout'));
 if(pending)templates.append(el('p',`검토할 항목이 ${pending}개 남았습니다. 데이터 정리에서 승인 또는 제외한 뒤 실행하세요.`,'callout'));if(!cases.length)templates.append(el('div',state.current.draft.adapter==='commerce-csv-1'?'저장된 예제 질문이 없습니다. 직접 조회 · 변경안 검토에서 질문 파일 없이 조회하거나 변경안을 검토할 수 있습니다.':'저장된 예제 질문이 없습니다. 자료의 질문 항목을 확인하거나 직접 조회 도구를 이용하세요.','empty'));for(const c of cases){const card=el('article',undefined,'card');card.append(el('h3',c.label||c.id),el('p',c.question||'질문 내용 없음'),el('p',`질문 ID: ${c.id} · 자료 버전 ${state.current.revision}`,'muted'));const run=button('이 질문 실행',()=>execute(c.id,crypto.randomUUID()),'primary');run.disabled=!mutable()||pending>0||state.current.readiness?.ready===false;card.append(run);templates.append(card);}if(cases.length&&!Array.isArray(state.current.cases))templates.append(el('p','승인한 CSV 연결에서 읽은 질문 목록입니다. 전체 자료의 실행 가능 여부는 실행 시 서버가 검사합니다.','muted'));
 root.append(templates);
}
async function withdrawPending(request,generation=false){
 if(!window.confirm('아직 접수되지 않은 요청을 철회합니다. 이미 접수된 실행은 취소하지 않고 저장된 상태를 확인합니다.'))return;
 await task(async()=>{
  const kind=generation?'model_suggestions':request.question!==undefined?'question':request.selection?'source_lookup':request.proposal?'replacement_proposal':'fixed_case';
  const original=generation?await api({action:'get',id:state.current.id,revision:request.revision}):null;
  const payload=generation?{draft_digest:original.digest}:request.question!==undefined?{question:request.question}:request.selection?{selection:request.selection}:request.proposal?{proposal:request.proposal}:{case_id:request.case_id};
  const response=await api({action:'withdraw_pending',id:state.current.id,revision:request.revision,request_key:request.request_key,kind,request:payload});
  if(response.operation.state==='running')throw Error('이미 실행 중입니다. 원래 요청 확인으로 완료 상태를 확인하세요.');
  remember((generation?'operations-generation-':'operations-request-')+state.current.id,null);
  await show(await api({action:'get',id:state.current.id,revision:null}));
 });
}
async function execute(caseId,requestKey,revision=state.current.revision,proposal=null,selection=null){await task(async()=>{try{const key='operations-request-'+state.current.id;const pending=recalled(key);if(pending&&JSON.parse(pending).request_key!==requestKey)throw Error('응답이 확인되지 않은 원래 요청을 먼저 확인하세요.');remember(key,JSON.stringify({revision,request_key:requestKey,case_id:caseId,proposal,selection}));const response=await api(selection?{action:'lookup',id:state.current.id,revision,request_key:requestKey,selection}:proposal?{action:'propose',id:state.current.id,revision,request_key:requestKey,proposal}:{action:'execute',id:state.current.id,revision,request_key:requestKey,case_id:caseId});remember(key,null);await showExecution(response.operation);$('notice').textContent=response.reused?'동일한 요청의 기존 실행 기록을 불러왔습니다.':'실행 기록을 저장했습니다.';}catch(error){/* An error does not establish whether an earlier same-key request committed. */render();throw error;}});}
function answerNode(value){
 const source=String(value??'');const target=el('div',undefined,'answer');
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
 return target;
}
function operationCard(op){if(op.summary_only){const card=el('article',undefined,'card');const names={question:'자유 질문',source_lookup:'원본 조회',model_suggestions:'자료 해석 제안',replacement_proposal:'주문 변경안',fixed_case:'예제 질문'};card.append(badge(op.state),el('h3',names[op.kind]||op.kind),el('p',`버전 ${op.revision} · ${new Date(op.created).toLocaleString('ko-KR')}`,'muted'));if(op.error)card.append(operationError(op.error));card.append(button('결과와 근거 열기',()=>task(async()=>{const full=await api({action:'operation',id:state.current.id,operation_id:op.id});retainOperation(full);render();})));return card;}if(op.kind==='question')return questionResult(op);if(op.kind==='model_suggestions')return proposalResult(op);const card=el('article',undefined,'card');card.append(badge(op.state),el('h3',op.result?.question||op.request.case_id||(op.request.selection?.relation_id?'두 CSV의 같은 값 대조':null)||(op.request.selection&&Object.keys(op.request.selection).length===1&&'entry_id' in op.request.selection?'승인한 문단 조회':'주문 변경안 검토')),el('p',`버전 ${op.revision} · ${new Date(op.created).toLocaleString('ko-KR')}`,'muted'));if(op.state==='completed'&&op.result){const r=op.result;if(r.mode==='reviewed_relation_rows'){card.append(relationResult(r),button('동일 요청 기록 확인',()=>execute(null,op.request_key,op.revision,null,op.request.selection)));return card;}if(r.mode==='source_document'){card.append(el('p','승인한 문서 원문 · 정책 적용 여부는 확인하지 않았습니다.','callout'),el('p',r.source.text,'source-quote'),el('p',`${r.source.file} · 원문 ${r.source.line_start}–${r.source.line_end}행`,'muted'),detail('검토한 해석 · 날짜 역할',r.review),detail('조회 범위 · 출처',r),button('동일 요청 기록 확인',()=>execute(null,op.request_key,op.revision,null,op.request.selection)));return card;}if(r.mode==='source_lookup'){card.append(el('p',r.answer),el('p',r.notice,'callout'),el('p',`기준일 ${r.metadata.as_of} · 미검토 필드: ${r.unreviewed_fields.join(', ')||'없음'}`,'muted'));for(const record of r.records){card.append(table(['필드','원본 값'],Object.entries(record.values)),el('p',`${record.source.file} · CSV 논리 레코드 ${record.record}${record.source.line_start?' · 원문 '+record.source.line_start+'–'+record.source.line_end+'행':''}`,'muted'));}card.append(reviewedFieldMeaning(r),detail('조회 범위 · 출처',r),button('동일 요청 기록 확인',()=>execute(null,op.request_key,op.revision,null,op.request.selection)));return card;}card.append(answerNode(r.answer||'실행 완료'));if(r.calculations)card.append(kv({'변경 전 상품 금액':r.calculations.before_subtotal,'변경 후 상품 금액':r.calculations.after_subtotal,'할인':r.calculations.discount,'배송비':r.calculations.shipping_fee,'합계':r.calculations.total}));card.append(el('h3','1. 조회한 근거'));if(r.facts){for(const [name,fact] of Object.entries(r.facts)){const block=el('details');block.append(el('summary',name));if(Array.isArray(fact)){if(fact.length){const columns=Object.keys(fact[0]);block.append(table(columns,fact.map(row=>columns.map(k=>row[k]))));}else block.append(el('p','이 조회 범위에서 일치하는 기록이 없습니다.','muted'));}else block.append(kv(fact));card.append(block);}}if(r.evidence){for(const evidence of r.evidence){const rows=evidence.rows||[];card.append(el('p',`${evidence.tool||evidence.query_id||'선택 근거'} · ${rows.length}행`,'muted'));if(rows.length){const columns=Object.keys(rows[0]);card.append(table(columns,rows.map(row=>columns.map(k=>row[k]))));}}}card.append(el('h3','2. 제약 점검'));const checks=r.shacl?.checks;if(checks)card.append(table(['점검 항목','결과','관측 값 또는 제약 수'],checks.map(c=>[c.label||c.candidate||c.shape||'선택 근거 점검',labels[c.status]||c.status,Object.hasOwn(c,'value')?(c.value===null?'미확인':c.value):`${c.constraints?.length??0}개 제약 · ${c.results?.length??0}개 위반`])));if(r.owl){card.append(el('h3','3. OWL 분류'),el('p',`추가된 규칙 적용 결과 ${r.owl.inferred_count??0}개 · 직접 상위 분류 근거 ${r.owl.witnesses?.length??0}개`,'muted'));if(r.owl.witnesses?.length)card.append(table(['전제','적용 공리','결론'],r.owl.witnesses.map(w=>[w.premise.join(' '),w.axiom.join(' '),w.conclusion.join(' ')])));}card.append(el('p','자료 조회, 제약 점검, OWL 분류는 서로 다른 단계입니다. 제약 통과나 분류 결과가 원본의 사실성을 보증하지 않습니다.','muted'),detail('조회한 근거 · 원본 기록',r.facts||r.evidence||r.query),detail('제약 점검 · SHACL',r.shacl),detail('분류 결과 · OWL',r.owl),detail('자료 버전 · 실행 상세',r));}else if(op.error){card.append(operationError(op.error));}else card.append(el('p','서버의 실행 완료 여부를 확인하세요. 자동 재시도하지 않습니다.','muted'));const actions=el('div',undefined,'actions');actions.append(button('동일 요청 기록 확인',()=>execute(op.request.case_id,op.request_key,op.revision,op.request.proposal,op.request.selection)));if(['failed','interrupted','cancelled'].includes(op.state)){const retry=button('새 요청으로 다시 실행',()=>{if(window.confirm('실패 기록을 보존하고 현재 버전으로 새 요청을 실행할까요?'))execute(op.request.case_id,crypto.randomUUID(),state.current.revision,op.request.proposal,op.request.selection);});retry.disabled=!mutable();actions.append(retry);}card.append(actions,detail('요청 식별 정보',{id:op.id,request_key:op.request_key,revision:op.revision,request:op.request}));return card;}
function decisionDiff(changes){
 const box=el('section');box.append(el('h3','검토 내용 변경'));
 if(!changes.length){box.append(el('p','필드 연결·검토 상태·해석·메모 변경이 없습니다.','muted'));return box;}
 const fieldNames={target:'연결 또는 규칙',status:'검토 상태',interpretation:'해석·적용 범위',note:'메모',temporal:'날짜 역할'};
 const value=(d,f)=>{if(d===null)return '항목 없음';const v=d[f];return f==='status'?(labels[v]||v):typeof v==='object'?`${v.file} · ${v.column}`:v||'(없음)';};
 for(const c of changes){const card=el('article',undefined,'card');card.append(el('h4',`${c.source.file} · ${c.source.column||'문단 '+c.source.paragraph}`));
 if(c.kind==='relation')card.append(el('p','연결 후보에 대한 검토 기록입니다. 실행되는 조회 연결의 변경을 뜻하지 않습니다.','muted'));
 card.append(table(['항목','변경 전','변경 후'],c.changed_fields.map(f=>[fieldNames[f]||f,value(c.before,f),value(c.after,f)])));box.append(card);}
 return box;
}
function renderChanges(root){const w=state.current;heading(root,'자료 변경과 재검토','변경 전후 버전을 비교하고, 새로 확인할 항목을 살펴보세요.');const card=el('article',undefined,'card');card.append(el('h3','자료 묶음 교체'),el('p','파일을 교체하려면 새 버전에 포함할 전체 묶음을 선택하세요. 묶음에서 빠진 파일은 새 버전에서 제거됩니다. 파일을 선택하지 않으면 기존 원문을 유지하고 기준 정보만 바꿉니다. 이전 원본과 실행 기록은 보존됩니다.','callout'));const files=input('','file');files.multiple=true;files.accept='.csv,.txt,.md';const snapshot=input(w.draft.metadata.snapshot_id),asof=input(w.draft.metadata.as_of,'date');snapshot.maxLength=80;const currency=input(w.draft.metadata.currency);currency.maxLength=14;currency.disabled=w.draft.adapter!=='commerce-csv-1';card.append(field('자료의 통화 · 3자리 코드 또는 unknown / mixed / not_applicable',currency));card.append(field('새 버전의 전체 파일 · 선택하지 않으면 기존 파일 유지',files),field('자료 버전 이름',snapshot),field('자료 기준일',asof));const refresh=button('교체 내용 확인',()=>task(async()=>{const selected=files.files.length?await readFiles(files):w.draft.sources.map(s=>({name:s.name,content:s.content}));previewRefresh(selected,{...w.draft.metadata,snapshot_id:snapshot.value,as_of:asof.value,currency:currency.value.trim()});}));refresh.disabled=!mutable();card.append(refresh);root.append(card);const compare=el('article',undefined,'card');compare.append(el('h3','버전 비교'));const options=w.versions.map(v=>[String(v.number),`버전 ${v.number} · ${new Date(v.created).toLocaleString('ko-KR')}`]);const before=select(options,String(w.versions[1]?.number||w.revision)),after=select(options,String(w.revision));const controls=el('div',undefined,'form-grid');controls.append(field('변경 전',before),field('변경 후',after));const output=el('div');compare.append(controls,button('차이 확인',()=>task(async()=>{const diff=await api({action:'diff',id:w.id,before:Number(before.value),after:Number(after.value)});output.replaceChildren(table(['구분','파일 또는 항목'],[['추가',diff.added.join(', ')||'없음'],['변경',diff.changed.join(', ')||'없음'],['제거',diff.removed.join(', ')||'없음'],['기준일',diff.metadata_before.as_of+' → '+diff.metadata_after.as_of],['자료 버전 이름',diff.metadata_before.snapshot_id+' → '+diff.metadata_after.snapshot_id],['통화',currencyLabel(diff.metadata_before.currency)+' → '+currencyLabel(diff.metadata_after.currency)],['재검토 필요',`${diff.review_required.length}개`]]),el('p','자료 변경에 따른 검토 범위를 보수적으로 잡습니다. 모든 원본 변경은 재검토 대상입니다.','muted'),decisionDiff(diff.decision_changes||[]),detail('재검토 항목과 과거 실행',diff));})),output);root.append(compare);const history=el('article',undefined,'card');history.append(el('h3','저장된 버전'));w.versions.forEach(v=>history.append(button(`버전 ${v.number} 열기 · ${new Date(v.created).toLocaleString('ko-KR')}`,()=>{if(canLeave())task(async()=>show(await api({action:'get',id:w.id,revision:v.number})));})));history.append(button('현재 버전으로 돌아가기',()=>{if(canLeave())task(async()=>show(await api({action:'get',id:w.id,revision:null})));}));root.append(history,detail('검토 결정 이력',w.draft.review_history||[]));}
function previewRefresh(files,metadata){const existing=state.current.draft.sources;const incoming=new Map(files.map(f=>[f.name,f]));const removed=existing.filter(s=>!incoming.has(s.name)).map(s=>s.name);const changed=existing.filter(s=>incoming.has(s.name)&&incoming.get(s.name).content!==s.content).map(s=>s.name);const added=files.filter(f=>!existing.some(s=>s.name===f.name)).map(s=>s.name);const dialog=el('dialog');dialog.append(el('h2','자료 교체 미리보기'),table(['구분','파일'],[['추가',added.join(', ')||'없음'],['변경',changed.join(', ')||'없음'],['제거',removed.join(', ')||'없음'],['자료 버전 이름',state.current.draft.metadata.snapshot_id+' → '+metadata.snapshot_id],['자료 기준일',state.current.draft.metadata.as_of+' → '+metadata.as_of],['통화',currencyLabel(state.current.draft.metadata.currency)+' → '+currencyLabel(metadata.currency)]]),el('p','원문이나 자료 버전 이름·기준일이 변경되면 검토 상태가 초기화됩니다. 원문과 기준 정보가 모두 같으면 기존 버전을 유지합니다.','callout'));dialog.append(button('취소',()=>dialog.close()),document.createTextNode(' '),button('전체 묶음 교체',()=>{dialog.close();task(async()=>show(await api({action:'refresh',id:state.current.id,revision:state.current.revision,files,metadata})));},'primary'));dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal();}
async function readFiles(control){const files=[...control.files];if(files.length<1||files.length>24)throw Error('파일을 1~24개 선택하세요.');if(files.some(f=>f.size>1000000)||files.reduce((n,f)=>n+f.size,0)>4000000)throw Error('파일당 1 MB, 전체 4 MB까지 업로드할 수 있습니다.');if(new Set(files.map(f=>f.name)).size!==files.length)throw Error('같은 이름의 파일이 있습니다. 파일 이름을 확인하세요.');if(files.some(f=>!/[.](csv|txt|md)$/i.test(f.name)))throw Error('CSV, TXT, MD 파일만 선택하세요.');return Promise.all(files.map(async f=>({name:f.name,content:new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(await f.arrayBuffer())})));}
function download(value){const u=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const a=el('a');a.href=u;a.download=`workspace-v${state.current.revision}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}
function openImport(){
 const dialog=el('dialog');dialog.setAttribute('aria-labelledby','import-title');
 const title=el('h2','저장한 초안 가져오기');title.id='import-title';
 const form=el('form'),name=input('가져온 자료실'),file=input('','file');name.required=true;name.maxLength=120;file.required=true;file.accept='.json,application/json';
 const error=el('p',undefined,'callout');error.hidden=true;error.setAttribute('role','alert');
 const preview=el('div'),actions=el('div',undefined,'actions');
 const inspect=el('button','내용 미리보기');inspect.type='submit';
 actions.append(button('닫기',()=>dialog.close()),inspect);
 form.append(field('새 자료실 이름',name),field('내려받은 초안 JSON 파일',file),el('p','workspace-draft-1 형식 · UTF-8 JSON · 최대 24 MiB','muted'),actions);
 dialog.append(title,el('p','원본과 검토 결정을 새 자료실로 가져옵니다. 기존 자료실을 덮어쓰지 않으며 실행 기록은 가져오지 않습니다.','muted'),form,error,preview);
 let bundle=null;
 const clear=()=>{bundle=null;preview.replaceChildren();error.hidden=true;};file.addEventListener('change',clear);name.addEventListener('input',clear);
 form.onsubmit=async event=>{
  event.preventDefault();if(state.busy)return;clear();inspect.disabled=true;file.disabled=true;name.disabled=true;dialog.setAttribute('aria-busy','true');
  try{
   const f=file.files[0];if(!f||f.size>24*1024*1024)throw Error('24 MiB 이하의 초안 JSON 파일을 선택하세요.');
   let parsed;try{parsed=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(await f.arrayBuffer()));}catch{throw Error('UTF-8 JSON을 읽지 못했습니다. 파일이 손상되지 않았는지 확인하세요.');}
   if(!parsed||parsed.format!=='workspace-draft-1'||!parsed.draft||!Array.isArray(parsed.draft.sources)||!Array.isArray(parsed.draft.entries))throw Error('운영 자료실에서 내려받은 workspace-draft-1 초안이 아닙니다.');
   if(parsed.draft.sources.length>24||parsed.draft.sources.some(source=>!source||typeof source.name!=='string'))throw Error('초안의 원본 목록이 올바르지 않습니다.');
   const newTitle=name.value.trim();if(!newTitle)throw Error('새 자료실 이름을 입력하세요.');
   bundle=parsed;const approved=parsed.draft.entries.filter(entry=>entry?.status==='approved').length;
   preview.append(el('h3','가져오기 미리보기'),kv({'새 자료실 이름':newTitle,'원본 파일':parsed.draft.sources.length+'개','저장된 승인':approved+'개','이전 자료 버전':parsed.revision??'미확인'}),table(['원본 파일'],parsed.draft.sources.map(source=>[source.name])),el('p','승인 결정도 함께 가져옵니다. 해시는 내용 일치 확인용이며 작성자의 신뢰나 자료의 사실성을 보증하지 않습니다. 서버가 원본·제안·검토 결정을 다시 확인한 뒤 새 자료실을 만듭니다. 자동으로 질문을 실행하지 않습니다.','callout'));
   const confirm=button('새 자료실로 가져오기',()=>{
    if(!canLeave())return;const submitted=bundle;if(!submitted)return;
    task(async()=>{try{const row=await api({action:'import',title:newTitle,bundle:submitted});dialog.close();state.tab='library';await show(row);$('notice').textContent='초안을 새 자료실로 가져왔습니다. 실행 기록은 포함하지 않았습니다.';}catch(err){error.textContent=err.message;error.hidden=false;throw err;}});
   },'primary');preview.append(confirm);
  }catch(err){error.textContent=err.message;error.hidden=false;}
  finally{inspect.disabled=false;file.disabled=false;name.disabled=false;dialog.setAttribute('aria-busy','false');}
 };
 dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal();name.focus();
}
$('import-draft').onclick=()=>{if(!state.busy)openImport();};
$('new').onclick=()=>{if(state.busy||!canLeave())return;state.edited=false;state.current=null;remember('operations-workspace-id',null);$('welcome').hidden=false;$('workspace').hidden=true;$('notice').textContent='';};
$('reload').onclick=()=>task(list);$('archived').onchange=()=>task(list);
for(const domain of ['commerce','factory'])$(domain+'-example').onclick=()=>task(async()=>{state.tab='library';await show(await api({action:'example',domain}));});
$('create').onsubmit=e=>{e.preventDefault();task(async()=>{const domain=$('domain').value;state.tab='library';await show(await api({action:'create',title:$('title').value,domain,files:await readFiles($('files')),metadata:{snapshot_id:$('snapshot').value,as_of:$('asof').value,currency:domain==='commerce'?$('currency').value.trim():'not_applicable'}}));});};
$('export').onclick=()=>task(async()=>download(await api({action:'export',id:state.current.id,revision:state.current.revision})));
$('archive').onclick=()=>{if(!canLeave())return;task(async()=>{const archived=!Boolean(state.current.archived);await show(await api({action:'archive',id:state.current.id,archived}));$('archived').checked=archived;await list();});};
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{if(state.busy)return;state.tab=b.dataset.tab;render();});
window.addEventListener('beforeunload',e=>{if(state.edited){e.preventDefault();e.returnValue='';}});
task(async()=>{const r=await fetch('/api/config');if(!r.ok)throw Error('서버에 연결할 수 없습니다. 페이지를 다시 열어 주세요.');state.csrf=(await r.json()).csrf;await list();let id;try{id=localStorage.getItem('operations-workspace-id');}catch{}if(id)await show(await api({action:'get',id,revision:null}));});
