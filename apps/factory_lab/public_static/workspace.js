'use strict';
/* Local-only workspace client. Uploaded text is always rendered as text nodes. */
const $ = id => document.getElementById(id);
const state = {csrf:'', current:null, tab:'library', busy:false, edited:false, edits:new Map(), policies:new Map(), detailOrder:[], area:'repositories', repositoryCatalog:[]};
const recoveries=new Map();
const cancellableExecutionKinds=new Set(['local_reasoning','database_reasoning_execute','database_query_execute']);
const terminalStates=new Set(['completed','failed','cancelled','interrupted']);
function collectRecovery(id){
 if(!id)return [];
 const records=[];
 for(const generation of [true,false]){
  const storage=(generation?'operations-generation-':'operations-request-')+id,raw=recalled(storage);
  if(raw===null)continue;
  let request,malformed=false;
  try{request=JSON.parse(raw);if(!request||typeof request.request_key!=='string'||!request.request_key.length||request.request_key.length>120||!Number.isInteger(request.revision)||request.revision<1)throw Error();
   if(!generation){if(request.action!==undefined){if(!reviewedActions.has(request.action)||request.workspace_id!==id||!validReviewedPayload(request.action,request.payload))throw Error();}
    else if(request.question!==undefined){if(typeof request.question!=='string'||!request.question.trim())throw Error();}
    else if(request.selection){if(typeof request.selection!=='object'||Array.isArray(request.selection))throw Error();}
    else if(request.proposal){if(typeof request.proposal!=='object'||Array.isArray(request.proposal))throw Error();}
    else if(typeof request.case_id!=='string'||!request.case_id.length)throw Error();}
  }catch{malformed=true;request=null;}
  const key=JSON.stringify([id,storage,request?.request_key??raw]);
  let record=recoveries.get(key);
  if(!record){record={key,id,storage,raw,request,generation,malformed,status:{state:'unknown'},opened:false};recoveries.set(key,record);}
  records.push(record);
 }
 return records;
}
function hasPending(){
 collectRecovery(state.current?.id);
 return Boolean(state.current&&recalled('operations-extension-'+state.current.id))||[...recoveries.values()].some(r=>!r.resolved&&recalled(r.storage)===r.raw);
}
function pendingReadBlocked(){return [...recoveries.values()].some(r=>!r.resolved&&recalled(r.storage)===r.raw&&(r.malformed||['unknown','running'].includes(r.status.state)));}
function submissionControl(node,disabled){node.dataset.requestSubmit='true';node.submissionDisabled=Boolean(disabled);node.disabled=Boolean(disabled)||hasPending();return node;}
function syncSubmissionControls(){document.querySelectorAll('[data-request-submit]').forEach(n=>{n.disabled=state.busy||n.submissionDisabled||hasPending();});}
function clearRecovery(record){
 if(recalled(record.storage)===record.raw)remember(record.storage,null);
 record.resolved=recalled(record.storage)!==record.raw;
}
function recoveryKind(record){const r=record.request;return r?.action|| (record.generation?'model_suggestions':r?.question!==undefined?'question':r?.selection?'source_lookup':r?.proposal?'replacement_proposal':'fixed_case');}
function announceRecovery(record){
 const type=record.generation?'의미 초안 생성':record.request.question!==undefined?'자유 질문':'직접 실행';
 const status=record.status;
 $('notice').textContent=`${type} · ${record.statusError?'상태 미확인. 요청은 보내지 않았습니다.':status.cancel_requested?operationProgressText({...status,kind:status.kind||recoveryKind(record)}):status.state==='not_recorded'?'접수 기록 없음. 요청은 보내지 않았습니다.':status.state==='running'?operationProgressText(status):`${labels[status.state]||status.state}. 저장된 실행을 열 수 있습니다.`}`;
}
function recoveryPayload(record){const r=record.request;return r.action?r.payload:record.generation?{draft_digest:record.originalDigest||r.draft_digest}:r.question!==undefined?{question:r.question}:r.selection?{selection:r.selection}:r.proposal?{proposal:r.proposal}:{case_id:r.case_id};}
function acceptRecoveryStatus(record,status){
 if(!status||!['unknown','not_recorded','running',...terminalStates].includes(status.state))throw Error('서버 상태 형식을 확인할 수 없습니다.');
 if(terminalStates.has(status.state)&&typeof status.id!=='string')throw Error('저장된 실행의 식별자가 없습니다.');
 record.status=status;record.statusError='';
 if(terminalStates.has(status.state))clearRecovery(record);
}
function recoveryEligibility(record){
 const w=state.current;
 if(!w||w.id!==record.id)return '원래 자료실을 먼저 불러오세요.';
 if(!mutable()||w.revision!==record.request.revision)return '원래 버전에서 새 실행을 시작할 수 없습니다. 현재 활성 버전과 요청 당시 버전이 같아야 합니다.';
 if(record.generation&&(!w.model_proposals?.enabled||w.draft.adapter!=='commerce-csv-1')||record.request.question!==undefined&&!w.model_questions?.enabled)return '외부 모델이 비활성화되어 원래 요청을 보낼 수 없습니다.';
 if([...recoveries.values()].some(other=>other!==record&&!other.resolved&&recalled(other.storage)===other.raw&&(other.malformed||['unknown','running'].includes(other.status.state))))return '다른 원래 요청의 서버 상태를 먼저 확인하세요. 실행 중이면 완료 후에 보낼 수 있습니다.';
 return '';
}
function renderRecovery(){
 const root=$('request-recovery');if(!root)return;
 collectRecovery(state.current?.id);
 const blocked=!state.current&&pendingReadBlocked();
 if(!state.current)$('gateway-status').textContent='모델 연결 확인 전';
 for(const id of ['new','import-draft','reload','archived'])$(id).disabled=state.busy||blocked;
 const focused=document.activeElement?.closest('[data-recovery-key]')?.dataset.recoveryKey;
 const historyOpen=root.querySelector('.recovery-history')?.open||false;
 root.replaceChildren();
 const records=[...recoveries.values()].filter(r=>!r.opened).sort((a,b)=>Number(b.status.state==='running')-Number(a.status.state==='running')||Number(b.generation)-Number(a.generation));
 root.hidden=!records.length;
 if(!records.length)return;
 const isForegroundChat=record=>state.area==='chat'&&state.chatPending?.workspace===record.id&&state.chatPending?.requestKey===record.request?.request_key;
 const foregroundOnly=records.every(record=>terminalStates.has(record.status.state)||isForegroundChat(record));
 const needsRecovery=records.some(record=>record.malformed||!['completed','failed','interrupted','cancelled'].includes(record.status.state));
 // Unresolved recovery remains prominent; terminal history follows the active workspace.
 if((needsRecovery&&!foregroundOnly)||!state.current)$('welcome').before(root);else $('workspace').after(root);
 if(needsRecovery&&!foregroundOnly)root.append(el('h2',state.current?'요청 복구':'자료실 요청 복구'));
 const history=el('details',undefined,'recovery-history');history.open=historyOpen;
 history.append(el('summary','저장된 요청 기록'));root.append(history);
 for(const record of records){
  if(record.generation&&state.current?.id===record.id&&state.current.revision===record.request?.revision)record.originalDigest=state.current.digest;
  const r=record.request,s=record.status,terminal=!record.malformed&&['completed','failed','interrupted','cancelled'].includes(s.state),card=el(terminal||isForegroundChat(record)?'details':'article',undefined,'card recovery-card'),title=el(terminal||isForegroundChat(record)?'summary':'h3',terminal?(s.state==='completed'?'완료된 요청 · 저장된 결과':'종료된 요청 · 결과와 오류 기록'):'응답 확인이 필요한 요청');title.tabIndex=-1;
  card.dataset.recoveryKind=record.generation?'generation':'request';card.dataset.recoveryState=s.state;card.dataset.recoveryKey=record.key;
  card.append(title,el('span',({unknown:'상태 미확인',not_recorded:'접수 기록 없음'})[s.state]||labels[s.state]||s.state,'badge'));
  if(record.malformed){card.append(el('p','이 기기에 저장된 요청 정보를 읽을 수 없습니다. 원래 요청을 확인할 수 없어 새 실행을 막고 있습니다. 저장 기록을 지우거나 요청을 보내지 않았습니다.','callout'),detail('읽지 못한 요청 기록',{workspace:record.id,storage:record.storage,raw:record.raw}));}
  else{
   const kinds={database_question_scope:'미해결 질문 · 운영자 판단',model_suggestions:'의미 초안 생성',question:'자유 질문',source_lookup:'원본 조회',replacement_proposal:'주문 변경안 검토',fixed_case:'예제 질문'};
   card.append(el('p',`${kinds[recoveryKind(record)]||recoveryKind(record)} · 요청 당시 버전 ${r.revision}`,'muted'));
   if(state.current&&state.current.id===record.id&&state.current.revision!==r.revision)card.append(el('p',`화면의 자료 버전 ${state.current.revision}과 요청 당시 버전이 다릅니다.`,'muted'));
   if(r.question!==undefined)card.append(detail('원래 질문',r.question));
   const actions=el('div',undefined,'actions');
   const statusButton=()=>button('서버 상태만 확인',()=>task(()=>readRecovery(record)));
   if(s.state==='unknown'){
    card.append(el('p',record.statusError?'서버 상태를 확인하지 못했습니다. 요청은 다시 보내지 않았습니다.':'이 기기에 남은 요청의 서버 접수 여부를 확인하세요.','callout'));actions.append(statusButton());
   }else if(s.state==='not_recorded'){
    card.append(el('p','현재 서버에서 이 요청의 접수 기록을 찾지 못했습니다. 보내려면 아래에서 직접 선택하세요.','callout'));
    const reason=recoveryEligibility(record),send=button('원래 요청 보내기',()=>sendRecovery(record),'primary');send.disabled=Boolean(reason)||state.busy;actions.append(send);
    if(reason)card.append(el('p',reason,'muted'));
    if(!state.current||state.current.id!==record.id||record.generation&&!recoveryPayload(record).draft_digest){const load=button('원래 자료실 불러오기',()=>loadRecoveryWorkspace(record));load.disabled=state.busy||pendingReadBlocked();actions.append(load);if(pendingReadBlocked())card.append(el('p','실행 중이거나 상태가 확인되지 않은 요청을 먼저 확인하세요. 그 후 자료실을 불러올 수 있습니다.','muted'));}
    const withdraw=button('미접수 요청 철회',()=>withdrawPending(record));withdraw.disabled=state.busy||record.generation&&!recoveryPayload(record).draft_digest;actions.append(withdraw,statusButton());
    if(record.generation&&!recoveryPayload(record).draft_digest)card.append(el('p','철회하려면 원래 버전의 자료 정보를 먼저 불러와야 합니다.','muted'));
   }else if(s.state==='running'){
    card.append(el('p',operationProgressText(s),'callout'),el('p',cancellableExecutionKinds.has(s.kind||recoveryKind(record))?'중지는 서버의 확인이 필요합니다. 이미 남은 실행 기록은 보존합니다.':'진행 중인 응답은 과금될 수 있습니다. 완료된 기록은 남습니다.','muted'));
    if(!state.current)card.append(el('p','실행이 끝나면 자료실을 불러올 수 있습니다.','muted'));
    actions.append(statusButton());
    if(!state.foregroundRequest&&(['question','model_suggestions'].includes(s.kind||recoveryKind(record))||cancellableExecutionKinds.has(s.kind||recoveryKind(record)))){const cancel=button(s.cancel_requested?'취소 요청됨':'실행 취소 요청',()=>task(async()=>{try{acceptRecoveryStatus(record,await api({action:'cancel',id:record.id,request_key:r.request_key}));announceRecovery(record);}catch(e){record.statusError=e.message;throw e;}finally{renderRecovery();}}));cancel.disabled=Boolean(s.cancel_requested)||state.busy;actions.append(cancel);}
   }else{
    card.append(el('p','저장된 결과와 오류 기록을 열 수 있습니다. 새 요청은 보내지 않습니다.','callout'));
    actions.append(button('저장된 실행 열기',()=>openRecovery(record),'primary'));
   }
   card.append(actions,el('p','상태 확인은 요청을 보내거나 모델을 호출하지 않습니다.','muted'),detail('요청 상세',{workspace:record.id,request:r,operation_id:s.id}));
   if(record.statusError)card.append(detail('상태 확인 오류',record.statusError));
  }
  card.querySelectorAll('button').forEach(b=>{if(state.busy)b.disabled=true;});if(terminal)history.append(card);else root.insertBefore(card,history);
  if(focused===record.key){if(terminal)history.open=true;title.focus({preventScroll:true});}
 }
 history.hidden=history.children.length===1;
 syncSubmissionControls();
}
async function readRecovery(record){
 try{acceptRecoveryStatus(record,await api({action:'progress',id:record.id,request_key:record.request.request_key}));}
 catch(e){record.status={state:'unknown'};record.statusError=e.message;}
 announceRecovery(record);
 renderRecovery();
}
async function loadRecoveryWorkspace(record){
 if(pendingReadBlocked()){$('notice').textContent='다른 요청의 상태를 확인하거나 실행이 끝난 뒤 자료실을 불러오세요.';return;}
 if(!canLeave())return;
 await task(async()=>{await show(await api({action:'get',id:record.id,revision:null}));await prepareRecoveryDigest(record);renderRecovery();});
}
async function prepareRecoveryDigest(record){
 if(!record.generation||record.malformed||record.status.state!=='not_recorded')return;
 const original=state.current?.id===record.id&&state.current.revision===record.request.revision?state.current:await api({action:'get',id:record.id,revision:record.request.revision});
 record.originalDigest=original.digest;
}
async function openSavedOperation(id,operationId){
 if(!canLeave())return false;
 const full=await api({action:'operation',id,operation_id:operationId});
 if(!state.current||state.current.id!==id||(full.kind==='extension_review'&&full.state==='completed'))await show(await api({action:'get',id,revision:null}));
 if(full.kind==='model_suggestions'){state.tab='review';state.preparationToolsOpen??=new Map();state.preparationToolsOpen.set(id,true);}
 else if(reviewedActions.has(full.kind)&&!['database_query_execute','database_question_scope'].includes(full.kind)){state.tab='review';}
 else if(['extension_import','extension_review','extension_invocation_association','local_reasoning','database_shapes_propose','database_shapes_validate','extension_localize'].includes(full.kind)){state.tab='review';extensionUI.open.set(id,true);}
 else{state.tab='questions';setHistoryOpen(true);}
 if(full.kind==='question')includeChatTurn(id,full.id);
 retainOperation(full);state.edits=new Map();state.policies=new Map();state.edited=extensionDirty();render();focusOperation(full.id);return true;
}
async function openRecovery(record){await task(async()=>{if(await openSavedOperation(record.id,record.status.id)){record.opened=true;renderRecovery();}});}
async function sendRecovery(record){
 if(record.status.state!=='not_recorded'||recoveryEligibility(record)||record.generation&&!canLeave())return;
 const kind=recoveryKind(record),r=record.request;
 const notice=kind==='model_suggestions'?'원래 버전의 원문 전체를 외부 모델에 보내며 유료 호출 1회를 시도합니다. 기존 승인은 자동으로 바뀌지 않습니다.':kind==='question'?'원래 질문과 조회 근거를 외부 모델에 보내며 질문에 따라 최대 4회 유료 호출합니다.':'원래 자료 버전과 조회 조건으로 실행합니다. 모델을 호출하지 않습니다.';
 if(!window.confirm(notice+' 이 원래 요청을 지금 보낼까요?'))return;
 state.explicitRecovery=record.key;record.status={state:'unknown'};renderRecovery();
 try{if(r.action)await task(()=>reviewedSubmit(r.action,r.payload,r.request_key,r.revision));else if(record.generation)await generateSuggestions(r.request_key,r.revision);else if(r.question!==undefined)await askQuestion(r.question,r.request_key,r.revision);else await execute(r.case_id,r.request_key,r.revision,r.proposal,r.selection);}
 finally{state.explicitRecovery=null;renderRecovery();}
}
function assertRequestAllowed(storage,requestKey){
 collectRecovery(state.current?.id);
 const original=recoveries.get(state.explicitRecovery);
 if(original&&original.storage===storage&&original.request?.request_key===requestKey&&recalled(storage)===original.raw)return;
 if(hasPending())throw Error('공유 요청 복구에서 원래 요청의 상태를 먼저 확인하세요.');
}
function resolveSubmitted(storage,requestKey,operation){
 const record=[...recoveries.values()].find(r=>r.storage===storage&&r.request?.request_key===requestKey);
 if(record){acceptRecoveryStatus(record,operation);renderRecovery();}
}
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
async function task(fn){if(state.busy)return;state.busy=true;document.body.setAttribute('aria-busy','true');$('error').hidden=true;$('notice').textContent='처리 중입니다…';const controls=[...document.querySelectorAll('button,input,select,textarea')];const disabled=controls.map(n=>n.disabled);controls.forEach(n=>n.disabled=true);try{await fn();if($('notice').textContent==='처리 중입니다…')$('notice').textContent='';}catch(e){$('notice').textContent='';$('error').hidden=false;$('error').textContent=e.message;$('error').scrollIntoView({block:'nearest'});}finally{controls.forEach((n,i)=>n.disabled=disabled[i]);state.busy=false;document.body.setAttribute('aria-busy','false');renderRecovery();syncSubmissionControls();if($('chat-review-repository'))$('chat-review-repository').disabled=!state.current;}}
function mutable(){return state.current&&!state.current.archived&&state.current.revision===state.current.current_revision;}
function changed(){state.edited=true; $('notice').textContent='아직 저장하지 않은 검토 내용이 있습니다. 항목 저장 또는 선택 승인으로 저장하세요.';}
function canLeave(){return !(state.edited||extensionVolatile()||(state.current&&reviewedDirty()))||window.confirm('저장하지 않은 검토 내용이 있습니다. 저장된 상태로 이동할까요?');}
function applyArea(){
 document.body.dataset.chatSending=state.chatPending?'true':'false';
 const chat=state.area==='chat';document.body.dataset.area=state.area;
 $('area-repositories').setAttribute('aria-current',chat?'false':'page');$('area-chat').setAttribute('aria-current',chat?'page':'false');
 $('chat-context').hidden=!chat;$('new').hidden=chat;$('workspace-navigation').hidden=chat;
 $('welcome').hidden=chat||Boolean(state.current);$('workspace').hidden=!state.current;
 document.querySelector('.workspace-head').hidden=chat;document.querySelector('#workspace>.tabs').hidden=chat;$('summary').hidden=chat;
 $('chat-review-repository').disabled=!state.current;
 if(chat&&state.current){const entries=state.current.draft.entries||[],approved=entries.filter(e=>e.status==='approved').length;const pending=entries.filter(e=>['pending','insufficient'].includes(e.status)).length;$('chat-repository-status').textContent=`${state.current.title} · 버전 ${state.current.revision} · 승인 ${approved}개 · 미승인 ${pending}개${state.current.archived?' · 보관된 저장소: 새 질문 불가':''} · 자료 구조·샘플은 탐색할 수 있고, 업무 조회는 승인 범위에서 실행합니다.`;}
 else if(chat)$('chat-repository-status').textContent='저장소를 선택하세요. 승인할 자료가 남았다면 저장소의 검토·승인에서 먼저 확인할 수 있습니다.';
 renderChatPicker();remember('operations-area',state.area);
}
function renderChatPicker(){
 const picker=$('chat-repository-select');if(!picker)return;
 const id=state.area==='chat'?state.current?.id:recalled('operations-chat-repository');
 const rows=(state.repositoryCatalog||[]).slice();if(state.current&&!rows.some(r=>r.id===state.current.id))rows.push({id:state.current.id,title:state.current.title,revision:state.current.revision});
 picker.replaceChildren();const blank=el('option','답변할 저장소 선택');blank.value='';picker.append(blank);
 for(const row of rows){const option=el('option',`${row.title} · 버전 ${row.revision}`);option.value=row.id;picker.append(option);}picker.value=id||'';
}
async function navigateArea(area,forceId=null){
 if(!canLeave())return;
 const prior=state.area;if(state.current){if(prior==='chat')remember('operations-chat-repository',state.current.id);else{remember('operations-library-repository',state.current.id);remember('operations-library-tab',state.tab);}}
 const id=forceId||(area==='chat'?(recalled('operations-chat-repository')||state.current?.id):recalled('operations-library-repository'));
 // Resolve the requested repository before changing any visible/active area.
 const row=id?await api({action:'get',id,revision:null}):null;
 state.area=area;state.tab=area==='chat'?'questions':(recalled('operations-library-tab')||'library');
 if(!['library','review','changes','questions'].includes(state.tab)||area!=='chat'&&state.tab==='questions')state.tab='library';
 if(row){await show(row);}
 else{state.current=null;state.edited=false;state.edits=new Map();$('content').replaceChildren();applyArea();await list();}
}

const repositorySelection=new Set();let repositoryManaging=false;
function renderRepositoryList(){
 const rows=state.repositoryCatalog||[],query=$('repository-search').value.trim().toLocaleLowerCase(),visible=rows.filter(r=>r.title.toLocaleLowerCase().includes(query));
 const ids=new Set(rows.map(r=>r.id));for(const id of repositorySelection)if(!ids.has(id))repositorySelection.delete(id);
 const n=$('workspaces');n.replaceChildren();if(!visible.length)n.append(el('p',rows.length?'검색 결과가 없습니다.':'저장한 자료실이 없습니다.','muted'));
 $('manage-workspaces').textContent=repositoryManaging?'목록 정리 마치기':'목록 정리 · 여러 개 선택';const tools=$('repository-bulk');tools.hidden=!repositoryManaging;tools.replaceChildren();
 if(repositoryManaging){
  tools.append(el('p',`전체 ${rows.length}개 · 검색 ${visible.length}개 · 선택 ${repositorySelection.size}개`,'muted'));
  tools.append(button('검색 결과 전체 선택',()=>{for(const r of visible)repositorySelection.add(r.id);renderRepositoryList();}),button('선택 해제',()=>{repositorySelection.clear();renderRepositoryList();}));
  const archive=button($('archived').checked?'선택한 저장소 복구':'선택한 저장소 보관 · 목록에서 숨기기',()=>task(async()=>{
   if(!canLeave())return;const chosen=rows.filter(r=>repositorySelection.has(r.id)),archived=!$('archived').checked;
   if(!chosen.length||!window.confirm(`${chosen.length}개 저장소를 ${archived?'보관해 목록에서 숨길까요? 원본·승인·실행 기록은 보존하며 복구할 수 있습니다.':'다시 목록에 표시할까요?'}\n\n`+chosen.map(r=>`${r.title} · ${r.id.slice(0,8)}`).join('\n')))return;
   let done=0;const failed=[];for(const r of chosen){try{await api({action:'archive',id:r.id,archived});repositorySelection.delete(r.id);done++;}catch{failed.push(r.title);}}
   if(state.current&&chosen.some(r=>r.id===state.current.id)){await show(await api({action:'get',id:state.current.id,revision:null}));}else await list();
   $('notice').textContent=`${done}개 ${archived?'보관':'복구'} 완료. 원본·승인·실행 기록은 남아 있습니다.`+(failed.length?` 실패 ${failed.length}개: ${failed.join(', ')}. 자동 재시도하지 않습니다.`:'');
  }),'primary');archive.dataset.testid='repository-bulk-archive';archive.disabled=!repositorySelection.size;tools.append(archive,el('p','보관은 삭제가 아닙니다. 보관한 자료실 보기에서 선택해 복구할 수 있습니다.','muted'));
 }
 for(const row of visible){const item=el('div',undefined,'repository-list-row');if(repositoryManaging){const check=input('','checkbox');check.setAttribute('aria-label',row.title+' · '+row.id.slice(0,8)+' 선택');check.checked=repositorySelection.has(row.id);check.onchange=()=>{if(check.checked)repositorySelection.add(row.id);else repositorySelection.delete(row.id);renderRepositoryList();};item.append(check);}
  const b=button(row.title,()=>{if(canLeave())task(async()=>{const selected=await api({action:'get',id:row.id,revision:null});state.area='repositories';if(state.tab==='questions')state.tab='library';await show(selected);});},row.id===state.current?.id?'active':'');b.append(el('small',`버전 ${row.revision} · ${new Date(row.updated).toLocaleDateString('ko-KR')} · ${row.id.slice(0,8)}`));item.append(b);n.append(item);
 }
}
async function list(){const data=await api({action:'list',archived:$('archived').checked});state.repositoryCatalog=data.workspaces;renderChatPicker();renderRepositoryList();}

function retainOperation(full){
 const i=state.current.operations.findIndex(o=>o.id===full.id);
 if(i<0)state.current.operations.unshift(full);else state.current.operations[i]=full;
 state.detailOrder=state.detailOrder.filter(id=>id!==full.id);state.detailOrder.push(full.id);
 while(state.detailOrder.length>3){const id=state.detailOrder.shift(),j=state.current.operations.findIndex(o=>o.id===id);
  if(j>=0){const old=state.current.operations[j],summary={summary_only:true};for(const key of ['id','workspace','revision','kind','state','error','created','updated'])summary[key]=old[key];state.current.operations[j]=summary;}
 }
}
async function showExecution(operation){if(operation.kind==='question')includeChatTurn(state.current.id,operation.id);const row=await api({action:'get',id:state.current.id,revision:null});const index=row.operations.findIndex(o=>o.id===operation.id);if(index>=0)row.operations[index]=operation;else row.operations.unshift(operation);await show(row);retainOperation(operation);render();}
async function show(row,edits=new Map(),policies=new Map()){if(state.current&&(state.current.id!==row.id||state.current.revision!==row.revision)){const prefix=state.current.id+':';for(const store of [extensionUI.staged,extensionUI.drafts])for(const key of store.keys())if(key.startsWith(prefix))store.delete(key);}state.detailOrder=[];if(state.area==='chat')await hydrateChatTurns(row);state.current=row;$('gateway-status').textContent=row.model_questions?.enabled?'외부 모델 질문 선택 가능':row.model_proposals?.enabled?'외부 모델 생성 선택 가능':'외부 모델 비활성';state.edits=edits;state.policies=policies;state.edited=extensionDirty();remember('operations-workspace-id',row.id);remember(state.area==='chat'?'operations-chat-repository':'operations-library-repository',row.id);$('welcome').hidden=true;$('workspace').hidden=false;collectRecovery(row.id);render();renderRecovery();await list();}
function render(){stashQuestionCursor();renderRecovery();if(state.tab==='questions')state.area='chat';else state.area='repositories';applyArea();const w=state.current,d=w.draft;$('workspace-title').textContent=w.title;$('workspace-meta').textContent=`${isDatabaseWorkspace()?d.domain+' · 등록 스냅샷':d.adapter==='commerce-csv-1'?'쇼핑몰 운영':'제조 운영'} / 버전 ${w.revision}${w.archived?' / 보관됨':''}`;$('archive').textContent=w.archived?'자료실 복구':'보관하기';$('summary').replaceChildren();for(const [num,title] of [[d.sources.length,isDatabaseWorkspace()?'등록된 표':'저장한 파일'],[d.entries.filter(e=>e.status==='pending'||e.status==='insufficient').length,'검토할 항목'],[d.entries.filter(e=>e.status==='approved').length,'승인한 항목'],[w.operation_count??w.operations.length,'실행 기록']]){const n=el('div',undefined,'stat');n.append(el('strong',String(num)),el('span',title));$('summary').append(n);}document.querySelectorAll('[data-tab]').forEach(b=>b.setAttribute('aria-current',b.dataset.tab===state.tab?'page':'false'));const root=$('content');$('workspace').dataset.view=state.tab;root.replaceChildren();if(!mutable())root.append(el('p','이전 버전 또는 보관 자료입니다. 편집과 새 실행은 현재 활성 버전에서 가능합니다.','callout'));document.querySelector('[data-tab=questions]').textContent=isDatabaseWorkspace()?'원본 조회':'질문하기';document.querySelector('main>footer').textContent=isDatabaseWorkspace()?'고정 스냅샷과 승인한 열의 범위에서 조회합니다. 현재 원본의 최신성·업무상 완전성은 확인하지 않습니다.':'검토 결과는 저장된 자료와 정해진 규칙의 범위에 한정됩니다. 실제 주문·결제·재고는 변경하지 않습니다.';(isDatabaseWorkspace()?{library:renderDatabaseLibrary,review:renderDatabaseReview,questions:renderDatabaseQuestions,changes:renderDatabaseChanges}:{library:renderLibrary,review:renderReview,questions:renderQuestions,changes:renderChanges})[state.tab](root);}
function heading(root,title,text){const n=el('div',undefined,'section-head');const h=el('div');h.append(el('h2',title),el('p',text,'muted'));n.append(h);root.append(n);return n;}
function currencyLabel(value){return ({unknown:'미확인',mixed:'여러 통화',not_applicable:'해당 없음',KRW:'원 (KRW)'})[value]||value;}
function sourcePreview(source){
 const card=el('article',undefined,'card source-preview');
 card.append(el('h3',source.name),el('p',`${source.kind==='table'?`${source.rows.length}행 · ${source.headers.length}열`:`${source.paragraphs.length}문단`} · ${source.bytes.toLocaleString()} bytes`,'muted'));
 if(source.kind==='table'){
  card.append(table(source.headers,source.rows.slice(0,8).map(row=>source.headers.map(column=>row[column]))),el('p','첫 8행 미리보기 · 행 번호는 CSV 레코드 기준입니다.','muted'));
  const profiles=el('details');profiles.append(el('summary','열별 값과 누락 확인'),table(['열','관측 값 유형','빈 값','서로 다른 값','중복 값'],source.profiles.map(profile=>[profile.column,profile.observed_types.join(', '),profile.missing,profile.distinct_nonempty,profile.duplicate_nonempty])));card.append(profiles);
 }else{
  for(const paragraph of source.paragraphs.slice(0,3))card.append(el('p',paragraph.text,'source-quote'));
  if(source.paragraphs.length>3)card.append(el('p','앞의 3개 문단을 표시합니다. 전체 원문은 아래에서 확인하세요.','muted'));
 }
 card.append(detail('전체 원문',source.content),detail('원본 해시와 위치 정보',{name:source.name,sha256:source.sha256,bytes:source.bytes,locations:source.locations,paragraphs:source.kind==='document'?source.paragraphs:undefined}));
 return card;
}
function isDatabaseWorkspace(){return state.current?.draft.adapter==='registered-database-1';}
const databaseUI={tables:new Map(),review:new Map()};
function databaseValue(value){return value===null?'NULL':typeof value==='object'?JSON.stringify(value):String(value??'미확인');}
function registeredDatabaseStart(){
 const card=el('article',undefined,'card database-create');card.append(el('h2','DB 연결하기'),el('p','예시 SQLite DB를 연결하거나 운영자가 등록한 원본을 선택하세요. 연결하면 실제 스키마·표본을 읽습니다. 이 단계는 LLM 호출이나 의미 승인이 아닙니다.','muted'));
 const example=button('예시 SQLite DB 연결 · 모델 호출 없음',()=>{if(!canLeave())return;task(async()=>{state.area='repositories';state.tab='library';await show(await api({action:'example_database'}));});},'primary');example.dataset.testid='connect-example-db';card.append(el('p','쇼핑몰 주문·상품 · 실제 SQLite · 3개 표 · 11행 · 작성한 가상 자료','muted'),example);
 const content=el('div');card.append(button('등록된 원본 목록 보기',()=>task(async()=>{
  const response=await api({action:'database_sources'});content.replaceChildren();
  if(!response.enabled){content.append(el('p','이 서버에는 등록 원본 조회 기능이 설정되지 않았습니다.','callout'));return;}
  if(!response.sources.length){content.append(el('p','선택 가능한 등록 원본이 없습니다. 운영자의 등록이 필요합니다.','muted'));return;}
  if(response.truncated)content.append(el('p','등록 원본 목록의 일부만 표시합니다. 현재 선택 가능한 항목의 범위입니다.','callout'));
  const form=el('form'),name=input(),domain=input('generic'),source=select([['','등록 원본 선택'],...response.sources.map(s=>[s.source_id,`${s.label} · ${s.table_count}개 표 · ${s.total_rows}행`])],''),summary=el('div');name.required=true;name.maxLength=120;domain.required=true;domain.maxLength=80;source.required=true;
  source.addEventListener('change',()=>{summary.replaceChildren();const selected=response.sources.find(s=>s.source_id===source.value);if(selected)summary.append(kv({'원본 이름':selected.label,'표 수':selected.table_count,'전체 행 수':selected.total_rows}),detail('등록 식별자·스냅샷 해시',{source_id:selected.source_id,snapshot_sha256:selected.snapshot_sha256}));});
  form.append(field('새 자료실 이름',name),field('분야 이름 · 표시용',domain),field('운영자가 등록한 원본',source),summary,el('p','분야 이름은 표시용입니다. 새로운 업무 계산 규칙을 만들지 않습니다. 임의 열을 검토하고 승인한 열로 전체 스냅샷을 조회합니다.','muted'));
  const create=el('button','선택한 등록 원본으로 자료실 만들기','primary');create.type='submit';form.append(create);
  form.addEventListener('submit',e=>{e.preventDefault();if(state.busy||hasPending()||!form.reportValidity()||!canLeave())return;task(async()=>{state.tab='library';await show(await api({action:'create_database',title:name.value.trim(),domain:domain.value.trim(),source_id:source.value,metadata:{}}));});});
  content.append(form);
 })),content);document.querySelector('.start-grid').insertBefore(card,document.querySelector('.start-grid>form'));
}
function databaseOnboarding(root){
 const d=state.current.draft;if(state.current.database_example?.id!=='shop-sqlite-v1')return;
 const card=el('article',undefined,'card database-onboarding');card.dataset.testid='database-onboarding';
 const fields=d.entries.filter(e=>e.source.file==='products'&&['sku','name','available'].includes(e.source.column));
 const approved=fields.filter(e=>e.status==='approved').length;
 card.append(el('h2','DB 연결에서 질문까지'),el('p','전체 10개 열을 모두 승인할 필요는 없습니다. 먼저 상품의 식별자·이름·재고 3개 열만 확인해 원본 조회를 시작해 보세요.','callout'));
 const steps=el('ol');steps.append(el('li','연결 완료: 실제 SQLite의 3개 표와 선언된 외래키, 표본을 읽었습니다. 의미를 추론하거나 모델을 호출하지 않았습니다.'),el('li','의미 초안 선택: 아래에서 직접 의미를 검토하거나 NVIDIA auto-ontology의 LLM 제안을 요청할 수 있습니다. 생성 결과는 승인 대기로 저장됩니다.'),el('li',`필요한 열 검토: products의 sku·name·available 중 ${approved}/3개 승인됨. 예시 값과 의미를 확인하고 필요한 열만 저장하세요.`),el('li','조회와 질문: 승인한 열로 원본을 조회합니다. 채팅에서 DB 값을 찾으려면 조회 정의도 검토·승인합니다. 재고 기록만으로 주문 변경을 허가하지 않습니다.'));card.append(steps);
 const review=button('상품 3개 열 검토하기',()=>{if(!canLeave())return;state.tab='review';render();const inventory=document.querySelector('.review-inventory');const select=inventory?.querySelector('select[id$="-source"]');if(select){select.value='products';select.dispatchEvent(new Event('change'));}inventory?.scrollIntoView({block:'start'});});review.dataset.testid='review-example-fields';review.disabled=!mutable();
 const native=button('LLM으로 의미 초안 제안받기 · 실행 창 열기',()=>document.dispatchEvent(new CustomEvent('factory-native-open',{detail:{workspaceId:state.current.id}})));native.disabled=!mutable()||!$('shared-bar');native.dataset.testid='example-native-open';
 const query=button('상품 조회 정의 초안 만들기 · 모델 호출 없음',()=>{if(!canLeave())return;task(async()=>{const byName=Object.fromEntries(fields.map(e=>[e.source.column,e.id]));const field=name=>({entry_id:byName[name],alias:'p'});const spec={id:'example_product_lookup',title:'상품번호로 기록된 이름과 재고 조회',question_scope:'상품번호가 정확히 일치하는 상품의 이름과 기록된 가용 수량 조회',root:field('sku'),joins:[],parameters:{sku:'text'},filters:[{field:field('sku'),op:'eq',parameter:'sku'}],projection:['sku','name','available'].map(name=>({field:field(name),name})),group_by:[],aggregates:[],distinct:false,output_kind:'recorded_facts',limitations:['가상 예시의 고정 스냅샷입니다. 현재 재고·예약·주문 변경 가능 여부를 검증하지 않습니다.'],policy_references:[],null_policy:'exclude_from_aggregates_preserve_projection',empty_groups:'absent',measure_grain:'p'};await reviewedSubmit('database_query_propose',{spec,origin:{kind:'packaged_example_template',example_id:'shop-sqlite-v1',model_called:false},relation_operation_ids:[]});});});query.disabled=!mutable()||approved!==3;query.dataset.testid='example-query-template';
 card.append(review,native,el('p','상품 열의 의미 예시: sku는 상품번호, name은 상품명, available은 기록된 가용 수량입니다. 연결만으로 이 설명이 자동 승인되지는 않습니다.','muted'),query,el('p','조회 정의 초안은 제공된 예제 템플릿입니다. LLM이 만든 쿼리가 아닙니다. 초안을 열어 조건과 출력을 확인하고 승인한 뒤 채팅에서 “P-102 상품의 이름과 기록된 재고를 알려줘”라고 질문하세요.','muted'));
 if(!$('shared-bar'))card.append(el('p','이 서버에는 화면에서 NVIDIA 실행기를 여는 기능이 없습니다. 직접 필드를 검토하거나 외부 결과 파일을 가져올 수 있습니다.','muted'));
 root.append(card);
}
function databaseSourceSummary(root){
 const d=state.current.draft;root.append(kv({'분야 이름':d.domain,'등록 원본':d.database.label,'표 수':d.sources.length,'전체 등록 행 수':d.sources.reduce((n,s)=>n+s.row_count,0)}),detail('고정 원본 버전과 식별자',d.database),el('p','표 미리보기는 제한된 샘플입니다. 승인한 열의 조회는 샘플 밖을 포함한 전체 고정 스냅샷을 사용합니다. 원본의 현재 상태나 업무상 완전성을 보증하지 않습니다.','muted'));
}
// Reviewed contracts are saved separately from the editable field draft.
const reviewedActions=new Set(['database_question_scope','database_external_relation_propose','database_external_relation_reject','database_relation_propose','database_relation_approve','database_query_propose','database_query_approve','database_query_execute','database_document_review','database_document_read']);
const reviewedUI={forms:new Map(),dirty:new Set(),catalogs:new Map(),questionPanels:new Map()};
const sourceReasoningActions=new Set(['database_reasoning_propose','database_reasoning_approve','database_reasoning_execute','database_reasoning_advisory_use']);
for(const action of sourceReasoningActions)reviewedActions.add(action);
function validReviewedPayload(action,payload){
 if(action==='database_question_scope'){
  const fields=['question','unresolved_requirements','reason_kind','assessment_note','evidence_operation_ids','human_confirmed'];
  return payload&&typeof payload==='object'&&!Array.isArray(payload)&&Object.keys(payload).length===fields.length&&fields.every(k=>Object.hasOwn(payload,k))&&typeof payload.question==='string'&&payload.question.trim().length>0&&payload.question.length<=4000&&typeof payload.assessment_note==='string'&&payload.assessment_note.trim().length>0&&payload.assessment_note.length<=4000&&Object.hasOwn(questionScopeReasons,payload.reason_kind)&&Array.isArray(payload.unresolved_requirements)&&payload.unresolved_requirements.length>0&&payload.unresolved_requirements.length<=20&&payload.unresolved_requirements.every(v=>typeof v==='string'&&v.trim().length>0&&v.length<=1000)&&Array.isArray(payload.evidence_operation_ids)&&payload.evidence_operation_ids.length<=20&&payload.evidence_operation_ids.every(v=>typeof v==='string'&&v.trim().length>0)&&new Set(payload.evidence_operation_ids).size===payload.evidence_operation_ids.length&&payload.human_confirmed===true;
 }

 if(sourceReasoningActions.has(action)){
  const fields={database_reasoning_propose:['execution_operation_id','projection_spec','ontology_base64','profile'],database_reasoning_approve:['proposal_operation_id','note','human_confirmed'],database_reasoning_execute:['approval_operation_id'],database_reasoning_advisory_use:['reasoning_operation_id','execution_operation_id','selected_statement_ids','interpretation','note','human_confirmed']}[action];
  return payload&&typeof payload==='object'&&!Array.isArray(payload)&&Object.keys(payload).length===fields.length&&fields.every(k=>Object.hasOwn(payload,k))&&fields.every(k=>k==='projection_spec'?payload[k]&&typeof payload[k]==='object'&&!Array.isArray(payload[k]):k==='selected_statement_ids'?Array.isArray(payload[k])&&payload[k].every(v=>typeof v==='string'):k==='human_confirmed'?payload[k]===true:typeof payload[k]==='string');
 }
 const fields={database_external_relation_propose:['operation_id','candidate_id','spec','edit_reason'],database_external_relation_reject:['operation_id','candidate_id','reason'],database_relation_propose:['spec','origin'],database_relation_approve:['proposal_operation_id','note','human_confirmed'],database_query_propose:['spec','origin','relation_operation_ids'],database_query_approve:['proposal_operation_id','note','human_confirmed'],database_query_execute:['approval_operation_id','parameters'],database_document_review:['document_id','paragraph_id','document_sha256','interpretation'],database_document_read:['review_operation_id']}[action];
 return fields&&payload&&typeof payload==='object'&&!Array.isArray(payload)&&Object.keys(payload).length===fields.length&&fields.every(k=>Object.hasOwn(payload,k))&&fields.every(k=>['spec','origin','parameters'].includes(k)?payload[k]&&typeof payload[k]==='object'&&!Array.isArray(payload[k]):k==='relation_operation_ids'?Array.isArray(payload[k])&&payload[k].every(v=>typeof v==='string'):k==='human_confirmed'?payload[k]===true:typeof payload[k]==='string');
}
function markReviewedDirty(key){reviewedUI.dirty.add(key);if(key===reviewedKey()+':query'){const summary=document.querySelector('[data-reviewed-panel="editor"]>summary');if(summary)summary.textContent='질의 정의 작성 · 저장하지 않은 변경 있음';}updateAdvancedToolsLabel();}
function updateAdvancedToolsLabel(){const summary=document.querySelector('[data-reviewed-panel="advanced-tools"]>summary');if(summary)summary.textContent='고급 조회 도구'+([...reviewedUI.dirty].some(key=>key.startsWith(reviewedKey()+':'))?' · 저장하지 않은 변경 있음':'');}
function reviewedKey(){return `${state.current.id}:${state.current.revision}:${state.current.current_revision}:${state.current.archived?'archived':'active'}`;}
function reviewedDirty(){return [...reviewedUI.dirty].some(k=>k.startsWith(reviewedKey()+':'));}
function reviewedFields(){return state.current.draft.entries.filter(e=>e.status==='approved');}
function reviewedLabel(id,artifact){const entry=artifact?.dependencies?.fields?.[id]?.entry||artifact?.dependencies?.[id]?.entry||state.current.draft.entries.find(e=>e.id===id);return entry?`${entry.source.file}.${entry.source.column}`:id;}
function reviewedScope(root){root.append(el('p',`고정 원본: ${state.current.draft.database.label} · ${state.current.draft.database.snapshot_sha256}`,'reviewed-hash'),el('p','정책 해석의 정확성과 현재 의존성은 미확인입니다. 저장·승인·실행은 각각 별도 동작이며 서버가 실행 시 의존성을 다시 검사합니다.','callout'));}
async function reviewedSubmit(action,payload,requestKey=crypto.randomUUID(),revision=state.current.revision){
 if(!mutable())throw Error('현재 활성 버전에서만 저장하거나 실행할 수 있습니다.');
 if(!validReviewedPayload(action,payload))throw Error('저장할 요청 형식이 올바르지 않습니다.');
 const storage='operations-request-'+state.current.id;assertRequestAllowed(storage,requestKey);
 const request={action,workspace_id:state.current.id,revision,request_key:requestKey,payload};
 if(!recalled(storage))remember(storage,JSON.stringify(request));
 if(!recalled(storage))throw Error('요청 복구 정보를 저장할 수 없습니다. 브라우저 저장소를 확인하세요.');
 collectRecovery(state.current.id);renderRecovery();
 const stopProgress=cancellableExecutionKinds.has(action)?watchQuestionProgress(state.current.id,requestKey,action):()=>{};
 let response;try{response=await api({action,id:state.current.id,revision,request_key:requestKey,...payload});}finally{stopProgress();}
 resolveSubmitted(storage,requestKey,response.operation);retainOperation(response.operation);
 if(sourceReasoningActions.has(action)&&response.operation.state==='completed'){
  const suffix=action==='database_reasoning_propose'?'projection:'+payload.execution_operation_id:action==='database_reasoning_advisory_use'?'advisory:'+payload.reasoning_operation_id:'approval:'+payload.proposal_operation_id;
  reviewedUI.dirty.delete(reviewedKey()+':'+suffix);
 }
 if(response.operation.state==='completed'){if(action.startsWith('database_external_relation_'))reviewedUI.dirty.delete(reviewedKey()+':external-relation:'+payload.operation_id+':'+payload.candidate_id+(action.endsWith('_reject')?':rejection':':proposal'));const suffix={database_query_propose:'query',database_document_review:'documents'}[action];if(suffix)reviewedUI.dirty.delete(reviewedKey()+':'+suffix);if(action.endsWith('_approve'))reviewedUI.dirty.delete(reviewedKey()+':approval:'+payload.proposal_operation_id);reviewedUI.catalogs.delete(reviewedKey());}
 if(action==='database_question_scope'&&response.operation.state==='completed'){reviewedUI.dirty.delete(reviewedKey()+':question-scope');reviewedUI.forms.delete(reviewedKey()+':question-scope');}
 state.tab=['database_query_execute','database_question_scope'].includes(action)?'questions':'review';render();focusOperation(response.operation.id);
 if(cancellableExecutionKinds.has(action))$('notice').textContent=operationProgressText(response.operation);
}
function reviewedCatalog(category,onChoose){
 const box=el('section',undefined,'reviewed-catalog'),items=el('div'),capabilities=el('div'),more=button('저장 목록 불러오기',()=>task(()=>load(false)));let cursor=null,loaded=false;
 box.append(el('h3',({relation:'저장된 관계',query:'저장된 질의',paragraph:'검토한 문단'})[category]),el('p','작업 완료와 승인 상태를 구분하세요. 현재 실행 가능 여부는 미점검입니다. 같은 제목도 별도 저장본입니다.','muted'),capabilities,items,more);
 async function load(next){const page=await api({action:'database_review_catalog',id:state.current.id,revision:state.current.revision,category,cursor:next?cursor:null});if(!next)items.replaceChildren();if(page.capabilities){const c=page.capabilities;capabilities.replaceChildren(el('p',`문서 연결: ${c.documents_configured?'설정됨':'없음'} · 반환 한도 ${c.limits.max_rows}행 / ${c.limits.max_bytes} bytes · 최종 스냅샷 실행 제한 ${c.limits.timeout_seconds}초 (사전 검증 시간 제외)`,'muted'));}loaded=true;for(const item of page.items){const card=el('article',undefined,'entry');card.append(el('h4',item.title||item.document?.label||item.label||item.logical_id||item.operation_id),el('p',`${item.artifact_state||item.status||'상태 확인 필요'} · 버전 ${item.revision??'?'} · ${item.created||''}`,'muted'),el('p',item.question_scope||item.interpretation||'', 'source-quote'),el('p',`현재 의존성: ${typeof item.readiness==='string'?item.readiness:item.readiness?.state||'unknown'} · ${(item.fingerprint||'').slice(0,16)}`,'muted'));if(item.child)card.append(el('p',`${item.child.table}.${item.child.column} → ${item.parent.table}.${item.parent.column}`));if(item.document)card.append(el('p',`${item.document.version} · ${item.document.paragraph_id} · ${item.document.line_start}–${item.document.line_end}행`));card.append(el('p',`원본 SHA256 ${item.source_binding?.snapshot_sha256||'기록 확인 필요'}`,'reviewed-hash'));const oid=item.operation_id;card.append(button('이 저장본 열기',()=>task(async()=>{const op=await api({action:'operation',id:state.current.id,operation_id:oid});retainOperation(op);if(onChoose)onChoose(op);else{if(!canLeave())return;state.tab=op.kind==='database_query_execute'?'questions':'review';render();focusOperation(op.id);}})));items.append(card);}if(!page.items.length)items.append(el('p',page.next_cursor?'이번 기록 구간에 해당 항목이 없습니다. 다음 기록을 확인하세요.':'이 기록 구간에 해당 항목이 없습니다.','muted'));cursor=page.next_cursor;more.textContent=cursor?'다음 기록 불러오기':'목록 새로 확인';more.onclick=()=>{if(!state.busy)task(()=>load(Boolean(cursor)));};}
 return box;
}
function reviewedDocuments(){
 const key=reviewedKey()+':documents';if(reviewedUI.forms.has(key))return reviewedUI.forms.get(key);
 const box=el('article',undefined,'card reviewed-documents'),list=el('div'),paragraphs=el('div'),preview=el('div');let docOffset=0;
 box.append(el('h3','원문 문단 검토'),el('p','원문을 먼저 열고 적용 범위를 기록하세요. 문단 검토는 실행 정책의 정확성이나 적용 여부를 증명하지 않습니다.','muted'));
 const load=button('등록 문서 불러오기',()=>task(async()=>{const page=await api({action:'database_documents',id:state.current.id,revision:state.current.revision,offset:docOffset});if(!docOffset)list.replaceChildren();for(const doc of page.documents){list.append(button(`${doc.label} · ${doc.version}`,()=>task(()=>inspect(doc,0))));}if(!page.documents.length)list.append(el('p','이 스냅샷에 등록된 문서가 없습니다.'));docOffset=page.truncated?page.offset+page.limit:0;load.textContent=page.truncated?'다음 문서 불러오기':'문서 목록 새로 확인';}));
 async function inspect(doc,offset){if(reviewedUI.dirty.has(key)&&!window.confirm('문단 선택을 바꾸면 아직 저장하지 않은 문단 해석이 사라집니다. 계속할까요?'))return;const page=await api({action:'database_document',id:state.current.id,revision:state.current.revision,document_id:doc.document_id,offset});paragraphs.replaceChildren(el('h4',`${doc.label} · ${doc.version}`));preview.replaceChildren();for(const p of page.paragraphs)paragraphs.append(button(`${p.paragraph_id} · ${p.line_start}–${p.line_end}행`,()=>task(async()=>{if(preview.childNodes.length&&reviewedUI.dirty.has(key)&&!window.confirm('저장하지 않은 문단 해석을 지우고 다른 문단을 열까요?'))return;const response=await api({action:'database_document_preview',id:state.current.id,revision:state.current.revision,document_id:doc.document_id,paragraph_id:p.paragraph_id,document_sha256:doc.document_sha256});const original=response.paragraph,meaning=el('textarea');meaning.maxLength=4000;meaning.addEventListener('input',()=>reviewedUI.dirty.add(key));preview.replaceChildren(reviewedParagraph(original),field('검토한 해석 · 적용 범위',meaning));const save=button('이 원문과 해석의 검토 저장',()=>task(async()=>{if(!meaning.value.trim())throw Error('검토한 해석을 입력하세요.');await reviewedSubmit('database_document_review',{document_id:doc.document_id,paragraph_id:p.paragraph_id,document_sha256:doc.document_sha256,interpretation:meaning.value});}));submissionControl(save,!mutable());meaning.disabled=!mutable();preview.append(save);})));if(page.truncated)paragraphs.append(button('다음 문단',()=>task(()=>inspect(doc,page.offset+page.limit))));}
 box.append(load,list,paragraphs,preview);reviewedUI.forms.set(key,box);return box;
}
function reviewedParagraph(p){const box=el('section',undefined,'reviewed-paragraph'),provenance=el('details',undefined,'reviewed-provenance');provenance.append(el('summary','원본 해시 확인'),el('p',`문서 SHA256 ${p.document_sha256}\n문단 SHA256 ${p.paragraph_sha256}`,'reviewed-hash'));box.append(el('h4',`${p.label} · ${p.version} · ${p.paragraph_id}`),el('p',p.text,'source-quote'),el('p',`원문 ${p.line_start}–${p.line_end}행`,'muted'),provenance);return box;}
function reviewedRelations(){
 const key=reviewedKey()+':relations';if(reviewedUI.forms.has(key))return reviewedUI.forms.get(key);
 const box=el('article',undefined,'card');box.append(el('h3','선언된 외래키 검토'),el('p','단일 열의 자식 → 부모 LEFT 조인만 지원합니다. 부모 키는 고유해야 하며 연결되지 않은 부모 값은 NULL입니다. 이후 부모 열의 필터가 자식 행을 제외할 수 있습니다.','muted'));
 const entries=state.current.draft.entries;for(const source of state.current.draft.sources)for(const fk of source.foreign_keys||[]){const parent=state.current.draft.sources.find(s=>s.name===fk.table),column=fk.to||(parent?.primary_key.length===1?parent.primary_key[0]:null),childEntry=entries.find(e=>e.source.file===source.name&&e.source.column===fk.from),parentEntry=entries.find(e=>e.source.file===fk.table&&e.source.column===column);const supported=source.foreign_keys.filter(f=>f.id===fk.id).length===1&&childEntry&&parentEntry;const card=el('details',undefined,'entry');card.append(el('summary',`${source.name}.${fk.from} → ${fk.table}.${column||'복합 키'}`));if(!supported){card.append(el('p','지원하지 않는 복합 키 또는 확인할 수 없는 끝점입니다.'));box.append(card);continue;}card.append(el('p',`자식 필드: ${labels[childEntry.status]} · 부모 필드: ${labels[parentEntry.status]}`));const id=input(''),meaning=el('textarea');id.placeholder='order_items_orders';meaning.maxLength=4000;card.append(field('관계 식별 이름 · 영문자로 시작',id),field('관계의 의미와 적용 범위',meaning));const save=button('관계 제안 저장',()=>task(()=>reviewedSubmit('database_relation_propose',{spec:{id:id.value,child_entry_id:childEntry.id,parent_entry_id:parentEntry.id,interpretation:meaning.value,join_policy:'left_many_to_one_preserve_root'},origin:{kind:'human_authored_ui'}})));submissionControl(save,!mutable()||childEntry.status!=='approved'||parentEntry.status!=='approved');card.append(save);box.append(card);}box.addEventListener('input',()=>reviewedUI.dirty.add(key));if(!mutable())box.querySelectorAll('input,textarea,select').forEach(n=>n.disabled=true);reviewedUI.forms.set(key,box);return box;
}
function reviewedAggregateLabel(g,a){
 if(g.op==='sum_product')return `${g.name} = sum_product(${g.left.alias}.${reviewedLabel(g.left.entry_id,a)}, ${g.right.alias}.${reviewedLabel(g.right.entry_id,a)}) · 단위 ${g.unit} (검토자 표기 · 단위 검증 아님) · signed64 정수 · 한쪽이라도 NULL이면 제외`;
 return `${g.name} = ${g.op}${g.field?'('+reviewedLabel(g.field.entry_id,a)+')':''}`;
}
function reviewedFilterLabel(f,a,values=null){
 const ref=r=>`${r.alias}.${reviewedLabel(r.entry_id,a)}`;
 if(!f.left)return `${ref(f.field)} ${f.op} ${f.parameter?(values?JSON.stringify(values[f.parameter]?.value):'$'+f.parameter):'NULL'}`;
 return `${ref(f.left)} ${f.op} ${f.right.kind==='scalar'?'선택값 '+f.right.binding:ref(f.right)} · ${f.value_type} · binary_exact · NULL은 unknown으로 제외`;
}
function reviewedScalarSummary(s,a,values=null){
 const box=el('section',undefined,'reviewed-scalar-summary');box.append(el('h4','같은 스냅샷의 단일 값 선택'));
 for(const b of s.scalar_bindings||[])box.append(el('h4',b.name),kv({'표 식별 필드':reviewedLabel(b.table_entry_id,a),'선택 조건':`${reviewedLabel(b.selector_entry_id,a)} = ${values?JSON.stringify(values[b.parameter]?.value):'$'+b.parameter} · ${b.selector_type}`,'반환 필드':`${reviewedLabel(b.value_entry_id,a)} · ${b.value_type}`,'선택 규칙':'exactly_one · require_nonnull · binary_exact'}));
 box.append(el('p','같은 스냅샷에서 실제 일치 행이 정확히 하나이고 값이 NULL이 아닐 때만 실행합니다. 두 행의 값이 같아도 실패합니다. 값 선택 실패는 결과 0건이 아닙니다. 선택값은 서버가 구하며 직접 입력하거나 바꿀 수 없습니다.','muted'));return box;
}
function reviewedSpecView(a){const s=a.spec,box=el('section',undefined,'reviewed-spec');box.append(el('h4',s.title||s.id),el('p',s.question_scope||s.interpretation,'source-quote'),el('p',`저장 상태: ${a.status} · 지문 ${a.fingerprint}`,'reviewed-hash'),el('p',`원본 버전: ${a.source?.label||''} · ${a.source?.snapshot_sha256||''}`,'reviewed-hash'));if(a.kind==='relation'){box.append(el('p',`${reviewedLabel(s.child_entry_id,a)} → ${reviewedLabel(s.parent_entry_id,a)}`),el('p','자식 행 단위 유지 · LEFT many-to-one · 부모 미연결 값 NULL'));return box;}if(s.query_kind==='directed_reachability'){box.append(reviewedReachabilitySummary(s,a));return box;}box.append(el('p',`기준 행: ${reviewedLabel(s.root.entry_id,a)} · 별칭 ${s.root.alias} · 수량 단위 ${s.measure_grain}`));const stages=el('ol');stages.append(el('li',`연결: ${s.joins.map(j=>`${j.child_alias} → ${j.parent_alias} (${j.relation_id})`).join(', ')||'없음'}`),el('li',`모든 조건 AND: ${s.filters.map(f=>reviewedFilterLabel(f,a)).join(' AND ')||'필터 없음'}`),el('li',`묶음 기준: ${s.group_by.map(f=>`${f.alias}.${reviewedLabel(f.entry_id,a)}`).join(', ')||'없음'}`),el('li',`출력: ${s.projection.map(p=>p.name).concat(s.aggregates.map(g=>reviewedAggregateLabel(g,a))).join(', ')} · 중복 제거 ${s.distinct?'예':'아니요'}`));box.append(stages,table(['매개변수','자료형'],Object.entries(s.parameters)),el('p',`출력 의미: ${s.output_kind}`),el('p','NULL은 집계에서 제외하고 일반 출력에서는 보존합니다. 빈 그룹은 출력하지 않습니다. SUM은 기준 행의 열만 사용합니다.','muted'));if(s.aggregates.some(g=>g.op==='sum_product'))box.append(el('p','sum_product는 부호 있는 64비트 정수만 사용합니다. 입력·각 곱·최종 합이 범위를 벗어나면 실행에 실패합니다. NULL을 포함한 곱은 제외하며, 결과 단위는 검토자의 표기로만 보관합니다.','callout'));if(s.scalar_bindings?.length)box.append(reviewedScalarSummary(s,a));for(const text of s.limitations)box.append(el('p',text,'callout'));return box;}
function reviewedQueryBuilder(copy=null){
 const key=reviewedKey()+':query';if(!copy&&reviewedUI.forms.has(key))return reviewedUI.forms.get(key);
 const box=el('section',undefined,'reviewed-query-family'),family=select([['relational','행 조회 · 비교 · 집계'],['directed_reachability','방향 관계의 도달 후보']],copy?.result.artifact.spec.query_kind||'relational'),content=el('div');
 box.append(field('질의 종류',family),content);
 function draw(initial=false){content.replaceChildren(family.value==='directed_reachability'?reviewedReachabilityBuilder(initial?copy:null):reviewedRelationalBuilder(initial?copy:null));}
 family.addEventListener('change',()=>{draw();markReviewedDirty(key);});draw(true);family.disabled=!mutable();reviewedUI.forms.set(key,box);return box;
}
function reviewedReachabilitySummary(s,a,values=null){
 const box=el('section',undefined,'reviewed-reachability-summary');box.append(el('h4','방향 관계의 도달 후보'),kv({'노드 식별 필드':reviewedLabel(s.node_entry_id,a),'관계 식별 필드':reviewedLabel(s.edge_id_entry_id,a),'저장된 관계 방향':`${reviewedLabel(s.source_entry_id,a)} → ${reviewedLabel(s.destination_entry_id,a)}`,'출발점 관계 승인 이름':s.source_relation_id,'도착점 관계 승인 이름':s.destination_relation_id,'탐색 방향':s.direction==='forward'?'정방향 · 출발점 → 도착점':'역방향 · 도착점 → 출발점','시작 매개변수':`${s.seed_parameter} · ${s.node_key_type}${values?' = '+JSON.stringify(values[s.seed_parameter]?.value):''}`,'비교 규칙':s.comparison,'탐색 한도':`깊이 ${s.budgets.max_depth} · 방문 노드 ${s.budgets.max_nodes} (시작점 포함) · 조사 관계 ${s.budgets.max_edges}`}),el('p',`매 단계의 AND 조건: ${s.edge_filters.map(f=>`${reviewedLabel(f.entry_id,a)} ${f.op} ${f.op==='is_null'?'NULL':(values?JSON.stringify(values[f.parameter]?.value):'$'+f.parameter)+' · '+f.value_type}`).join(' AND ')||'필터 없음'}`),el('p',`추가 노드 출력: ${s.projection.map(p=>`${p.name} = ${reviewedLabel(p.entry_id,a)}`).join(', ')||'없음'}`),table(['매개변수','자료형'],Object.entries(s.parameters)),el('p','기존 노드만 탐색하며 시작점은 결과에서 제외합니다. 도달 노드는 중복 없이 한 번 출력합니다. 한도로 탐색이 멈추면 전체 후보 수는 미확인입니다. 잠재 영향 후보이며 일정 시뮬레이션이나 변경 승인이 아닙니다.','callout'));
 for(const text of s.limitations)box.append(el('p',text,'callout'));return box;
}
function reviewedReachabilityBuilder(copy=null){
 const key=reviewedKey()+':query',cacheKey=key+':reachability';if(!copy&&reviewedUI.forms.has(cacheKey))return reviewedUI.forms.get(cacheKey);
 const s=copy?.result.artifact.spec,fields=reviewedFields(),box=el('article',undefined,'card reviewed-builder reviewed-reachability-builder'),form=el('form');box.append(el('h3',s?'저장된 도달 질의의 새 사본':'방향 관계 도달 질의 작성'));reviewedScope(box);
 if(!fields.length){box.append(el('p','먼저 사용할 필드를 승인하세요.'));return box;}
 const chooser=(value)=>select([['','승인 필드 선택'],...fields.map(e=>[e.id,reviewedLabel(e.id)])],value||'');
 const id=input(s?s.id+'_copy':''),title=input(s?.title||''),scope=el('textarea'),node=chooser(s?.node_entry_id),edge=chooser(s?.edge_id_entry_id),source=chooser(s?.source_entry_id),destination=chooser(s?.destination_entry_id),direction=select([['forward','정방향 · 출발점 → 도착점'],['reverse','역방향 · 도착점 → 출발점']],s?.direction||'forward'),type=select([['integer','integer'],['text','text']],s?.node_key_type||'integer'),seed=input(s?.seed_parameter||'seed'),limits=el('textarea');scope.value=s?.question_scope||'';limits.value=s?.limitations.join('\n')||'';
 for(const n of [id,title,scope,node,edge,source,destination,seed])n.required=true;
 form.append(field('질의 식별 이름 · 영문자/숫자/밑줄',id),field('제목',title),field('질문의 범위',scope),field('노드 식별 승인 필드',node),field('관계 식별 승인 필드',edge),field('출발점 승인 필드',source),field('도착점 승인 필드',destination));
 const selected={source:null,destination:null};
 for(const [role,label] of [['source','출발점'],['destination','도착점']]){const section=el('section',undefined,'reviewed-endpoint-choice'),summary=el('div'),picker=el('details'),heading=el('summary',label+' 관계 승인 선택');picker.append(heading,reviewedCatalog('relation',op=>{if(op.kind!=='database_relation_approve'||op.state!=='completed'||op.result?.artifact.status!=='approved')throw Error('완료된 관계 승인을 선택하세요.');selected[role]=op;const a=op.result.artifact;summary.replaceChildren(el('p',`${a.spec.id}: ${reviewedLabel(a.spec.child_entry_id,a)} → ${reviewedLabel(a.spec.parent_entry_id,a)}`),el('p',`승인 저장본 ${op.id} · 버전 ${op.revision} · 현재 의존성 미점검`,'reviewed-hash'));picker.open=false;markReviewedDirty(key);}));section.append(el('h4',label+' → 노드 키의 저장된 승인'),summary,picker);form.append(section);if(s)summary.append(el('p',`이전 관계 이름 ${s[role+'_relation_id']} · 새 사본에서는 저장된 승인을 다시 선택하세요.`,'callout'));}
 form.append(field('탐색 방향',direction),field('노드 키와 시작값 자료형',type),field('시작 매개변수 이름',seed),el('p','시작값은 승인 후 실행할 때 입력합니다. 기존 노드 필수 · 시작점 결과 제외 · 도달 노드 중복 제거 · binary_exact 비교. 두 끝점은 같은 노드 키로 연결되는 서로 다른 저장된 관계 승인이어야 합니다.','muted'));
 const budgets={};for(const [name,label,max,fallback] of [['max_depth','최대 탐색 깊이',128,32],['max_nodes','최대 방문 노드 · 시작점 포함',10000,1000],['max_edges','최대 조사 관계',100000,10000]]){const n=input(String(s?.budgets[name]??fallback),'number');n.min='1';n.max=String(max);n.step='1';n.required=true;budgets[name]=n;form.append(field(`${label} · 1–${max}`,n));}
 const filters=[],projection=[],policies=[],extraParameters=[];
 function rows(label,array,create){const section=el('section',undefined,'reviewed-rows'),list=el('div');function add(v){const row=el('div',undefined,'reviewed-form-row'),value=create(row,v),item={value};array.push(item);row.append(button('행 삭제',()=>{array.splice(array.indexOf(item),1);row.remove();markReviewedDirty(key);}));list.append(row);markReviewedDirty(key);}section.append(el('h4',label),list,button(label+' 추가',()=>add()));form.append(section);return add;}
 const addExtraParameter=rows('추가 실행 매개변수',extraParameters,(row,v)=>{const name=input(v?.name||''),kind=select(['text','integer','number','date'].map(x=>[x,x]),v?.type||'text');name.required=true;row.append(field('매개변수 이름',name),field('매개변수 자료형',kind));return ()=>[name.value,kind.value];});
 const addFilter=rows('관계 필터',filters,(row,v)=>{const f=chooser(v?.entry_id),op=select(['eq','lt','lte','gt','gte','is_null'].map(x=>[x,x]),v?.op||'eq'),parameter=input(v?.parameter||''),valueType=select(['text','integer','number','date'].map(x=>[x,x]),v?.value_type||'text');f.required=true;function toggle(){parameter.disabled=valueType.disabled=op.value==='is_null'||!mutable();parameter.required=op.value!=='is_null';}op.addEventListener('change',toggle);toggle();row.append(field('관계 표의 승인 필드',f),field('비교',op),field('필터 매개변수 이름',parameter),field('필터 값 자료형',valueType));return ()=>({entry_id:f.value,op:op.value,...(op.value==='is_null'?{}:{parameter:parameter.value,value_type:valueType.value})});});
 const addProjection=rows('추가 노드 출력',projection,(row,v)=>{const f=chooser(v?.entry_id),name=input(v?.name||'');f.required=name.required=true;row.append(field('노드 표의 승인 필드',f),field('출력 이름',name));return ()=>({entry_id:f.value,name:name.value});});
 const policyList=el('div');form.append(el('h4','검토한 정책 문단'),policyList,reviewedCatalog('paragraph',op=>{if(op.kind!=='database_document_review'||op.state!=='completed')throw Error('완료된 문단 검토를 선택하세요.');if(policies.some(p=>p.id===op.id))return;policies.push(op);const row=el('section');row.append(reviewedParagraph(op.result.paragraph),el('p',op.result.interpretation,'source-quote'),button('참조 제거',()=>{policies.splice(policies.indexOf(op),1);row.remove();markReviewedDirty(key);}));policyList.append(row);markReviewedDirty(key);}));
 form.append(field('한계 · 한 줄에 하나',limits),el('p','출력은 potential_impact_candidates입니다. 한도를 높이면 새 검토가 필요합니다. 도달 탐색의 완결 여부와 화면 표시 제한은 별도로 기록됩니다.','callout'));
 const save=el('button','정의 검증 후 제안 저장','primary');save.type='submit';submissionControl(save,!mutable());form.append(save);
 form.addEventListener('submit',event=>{event.preventDefault();if(!form.reportValidity()||state.busy)return;task(async()=>{
  const relations=Object.values(selected);if(relations.some(r=>!r))throw Error('출발점과 도착점의 관계 승인을 모두 선택하세요.');if(new Set(relations.map(r=>r.result.artifact.spec.id)).size!==2)throw Error('서로 다른 관계 승인을 선택하세요.');
  for(const [role,control] of [['source',source],['destination',destination]]){const r=selected[role].result.artifact.spec;if(r.child_entry_id!==control.value||r.parent_entry_id!==node.value)throw Error('선택한 관계 승인의 끝점이 현재 필드 선택과 다릅니다.');}
  const table=id=>fields.find(e=>e.id===id)?.source.file,edgeFilters=filters.map(f=>f.value()),outputs=projection.map(p=>p.value());if([source.value,destination.value,...edgeFilters.map(f=>f.entry_id)].some(id=>table(id)!==table(edge.value)))throw Error('관계 식별자·끝점·필터는 같은 관계 표여야 합니다.');if(outputs.some(p=>table(p.entry_id)!==table(node.value)))throw Error('추가 출력은 노드 표의 필드여야 합니다.');
  const parameters={[seed.value]:type.value};for(const f of edgeFilters)if(f.parameter){if(Object.hasOwn(parameters,f.parameter)&&parameters[f.parameter]!==f.value_type)throw Error('동일 매개변수의 자료형이 다릅니다.');parameters[f.parameter]=f.value_type;}for(const item of extraParameters){const [name,kind]=item.value();if(Object.hasOwn(parameters,name))throw Error('추가 매개변수 이름이 중복됩니다.');parameters[name]=kind;}
  const spec={id:id.value,title:title.value,question_scope:scope.value,query_kind:'directed_reachability',edge_id_entry_id:edge.value,source_entry_id:source.value,destination_entry_id:destination.value,node_entry_id:node.value,source_relation_id:selected.source.result.artifact.spec.id,destination_relation_id:selected.destination.result.artifact.spec.id,direction:direction.value,node_key_type:type.value,comparison:'binary_exact',parameters,seed_parameter:seed.value,seed_policy:'require_existing_node',include_seed:false,node_semantics:'distinct_reachable',endpoint_policy:'require_existing_node',edge_filters:edgeFilters,projection:outputs,budgets:Object.fromEntries(Object.entries(budgets).map(([k,n])=>[k,Number(n.value)])),output_kind:'potential_impact_candidates',limitations:limits.value.split('\n').filter(v=>v.trim()),policy_references:policies.map(p=>({review_operation_id:p.id}))};
  await reviewedSubmit('database_query_propose',{spec,origin:{kind:'human_authored_ui',...(copy?{copied_operation_id:copy.id}:{})},relation_operation_ids:relations.map(r=>r.id)});
 });});
 if(s){const used=new Set([s.seed_parameter,...s.edge_filters.map(f=>f.parameter)]);for(const [name,type] of Object.entries(s.parameters))if(!used.has(name))addExtraParameter({name,type});s.edge_filters.forEach(addFilter);s.projection.forEach(addProjection);box.append(el('p','원래 방향·필터·시작 매개변수·한도·출력·한계를 복사했습니다. 관계 승인과 정책 문단은 다시 선택하세요. 이전 기록은 바뀌지 않습니다.','callout'));}
 form.addEventListener('input',()=>reviewedUI.dirty.add(key));form.addEventListener('change',()=>reviewedUI.dirty.add(key));if(!mutable())form.querySelectorAll('input,textarea,select,button').forEach(n=>n.disabled=true);box.append(form);reviewedUI.forms.set(cacheKey,box);return box;
}
function reviewedReachabilityResult(a,op,r){
 const box=el('section',undefined,'reviewed-reachability-result');if(op.request?.approval_operation_id)box.append(button('이 실행의 질의 승인 열기',()=>task(()=>openSavedOperation(state.current.id,op.request.approval_operation_id))));
 box.append(el('h4',a.closure_complete?'도달 탐색 완료':'도달 탐색 미완료'),kv({'탐색 상태':a.status,'전체 도달 후보 수':a.total_output_rows===null?'미확인 · 발견 수는 하한':a.total_output_rows,'발견한 후보':a.discovered_count,'반환 행':a.returned_count,'화면 표시 제한':a.truncated?'일부만 표시':'저장된 후보 전체 표시'}),el('p',a.closure_complete?'승인한 방향·필터·고정 스냅샷에서 탐색을 마쳤습니다. 외부 자료나 업무상 완전성을 보증하지 않습니다.':'탐색을 마치지 못했습니다. 현재 목록으로 전체 영향 후보나 영향 없음이라고 판단할 수 없습니다.','callout'));
 if(a.incomplete_reasons?.length)box.append(table(['미완료 이유'],a.incomplete_reasons.map(v=>[typeof v==='string'?v:JSON.stringify(v)])));
 const columns=Object.keys(a.rows[0]||{}).filter(k=>k!=='witness_path');box.append(table(columns,a.rows.map(row=>columns.map(k=>databaseValue(row[k])))),el('p','minimum_depth는 발견한 최소 깊이입니다. predecessor_id와 witness_edge_id는 도달 근거 한 개이며 모든 경로를 열거하지 않습니다. 표시 제한으로 선행 노드가 이 목록에 없을 수 있으며 아래 상세의 witness_path에서 시작점부터의 경로를 확인할 수 있습니다. 정수 식별자는 정확한 십진 문자열로 표시합니다.','muted'));
 const witness=el('details',undefined,'reviewed-witness');witness.append(el('summary','도달 근거와 탐색 기록'),detail('반환 노드별 선행 노드·관계',a.rows.map(row=>({node_id:row.node_id,minimum_depth:row.minimum_depth,predecessor_id:row.predecessor_id,witness_edge_id:row.witness_edge_id,witness_path:row.witness_path}))),detail('탐색 한도와 관측',{budgets:a.budgets,traversal_observations:a.traversal_observations}),detail('고정 원본·질의·실행 매개변수',a.provenance));box.append(witness);for(const text of a.limitations||[])box.append(el('p',text,'callout'));for(const evidence of r.reviewed_document_evidence||[])box.append(reviewedParagraph(evidence.paragraph),el('p',evidence.interpretation,'source-quote'));return box;
}

function reviewedRelationalBuilder(copy=null){
 const key=reviewedKey()+':query';if(!copy&&reviewedUI.forms.has(key+':relational'))return reviewedUI.forms.get(key+':relational');
 const box=el('article',undefined,'card reviewed-builder'),form=el('form'),fields=reviewedFields(),s=copy?.result.artifact.spec;box.append(el('h3',s?'저장된 질의의 새 사본':'질의 정의 작성'),el('p','조건은 모두 AND로 결합합니다. 저장은 제안만 만들며 승인과 실행은 별도입니다. 값은 승인 후 실행할 때 직접 입력합니다.','muted'));reviewedScope(box);
 if(!fields.length){box.append(el('p','먼저 사용할 필드를 승인하세요.'));return box;}
 const id=input(s?s.id+'_copy':''),title=input(s?.title||''),scope=el('textarea'),root=select(fields.map(e=>[e.id,reviewedLabel(e.id)]),s?.root.entry_id||fields[0].id),alias=input(s?.root.alias||'r'),kind=select([['recorded_facts','기록된 사실'],['prerequisite_candidates','선행 조건 후보'],['potential_impact_candidates','잠재 영향 후보']],s?.output_kind||'recorded_facts'),limits=el('textarea'),distinct=input('','checkbox');scope.value=s?.question_scope||'';limits.value=s?.limitations.join('\n')||'';distinct.checked=s?.distinct||false;for(const n of [id,title,scope,alias])n.required=true;
 form.append(field('질의 식별 이름 · 영문자/숫자/밑줄',id),field('제목',title),field('질문의 범위',scope),field('기준 행의 승인 필드',root),field('기준 표 별칭',alias));
 const joins=[],parameters=[],filters=[],projections=[],groups=[],aggregates=[],policies=[],scalarBindings=[];
 function rowsSection(label,array,create){const section=el('section',undefined,'reviewed-rows'),rows=el('div');section.append(el('h4',label),rows,button(label+' 추가',()=>add()));form.append(section);function add(initial){const row=el('div',undefined,'reviewed-form-row'),controls=create(row,initial);const record={...controls,node:row};array.push(record);row.append(button('행 삭제',()=>{array.splice(array.indexOf(record),1);row.remove();markReviewedDirty(key);}));rows.append(row);markReviewedDirty(key);return record;}return add;}
 function fieldRef(row,initial){const f=select(fields.map(e=>[e.id,reviewedLabel(e.id)]),initial?.entry_id||root.value),a=input(initial?.alias||alias.value);row.append(field('승인 필드',f),field('표 별칭',a));return {ref:()=>({entry_id:f.value,alias:a.value})};}
 const addJoin=rowsSection('관계 연결',joins,(row,initial)=>{
  let selected=initial?.operation||null;
  const choice=el('section',undefined,'reviewed-relation-choice'),picker=el('details',undefined,'reviewed-relation-picker'),pickerTitle=el('summary');
  function showChoice(){
   pickerTitle.textContent=selected?'관계 승인 변경':'저장된 관계 승인 선택';picker.open=!selected;
   if(!selected){choice.replaceChildren(el('p','저장된 관계 승인을 선택하세요.'));return;}
   const a=selected.result.artifact;
   choice.replaceChildren(el('h4',a.spec.id),el('p',`${reviewedLabel(a.spec.child_entry_id,a)} → ${reviewedLabel(a.spec.parent_entry_id,a)}`),el('p',`승인 · 저장 버전 ${selected.revision} · ${selected.id.slice(0,12)}`,'muted'),el('p','LEFT many-to-one · 자식 행 유지 · 부모 미연결 값 NULL','muted'));
  }
  picker.append(pickerTitle,reviewedCatalog('relation',op=>{if(op.kind!=='database_relation_approve'||op.state!=='completed')throw Error('완료된 관계 승인을 선택하세요.');selected=op;showChoice();pickerTitle.focus();markReviewedDirty(key);}));showChoice();
  const child=input(initial?.child_alias||alias.value),parent=input(initial?.parent_alias||'p');row.append(choice,picker,field('이미 연결된 자식 별칭',child),field('새 부모 별칭',parent));
  return {value:()=>{if(!selected)throw Error('관계 승인을 선택하세요.');return {relation_id:selected.result.artifact.spec.id,child_alias:child.value,parent_alias:parent.value};},operation:()=>selected?.id};
 });
 const addParameter=rowsSection('매개변수',parameters,(row,v)=>{const name=input(v?.name||''),type=select(['text','integer','number','date'].map(k=>[k,k]),v?.type||'text');row.append(field('이름',name),field('자료형',type));return {value:()=>[name.value,type.value]};});
 const addFilter=rowsSection('필터',filters,(row,v)=>{const ref=fieldRef(row,v?.field),op=select(['eq','lt','lte','gt','gte','is_null'].map(k=>[k,({eq:'같음',lt:'미만',lte:'이하',gt:'초과',gte:'이상',is_null:'NULL'})[k]]),v?.op||'eq'),parameter=input(v?.parameter||'');row.append(field('비교',op),field('매개변수 이름 · NULL 비교는 비움',parameter));return {value:()=>({field:ref.ref(),op:op.value,...(op.value==='is_null'?{}:{parameter:parameter.value})})};});
 const addScalar=rowsSection('단일 값 선택 · 선택 사항',scalarBindings,(row,v)=>{
  const name=input(v?.name||''),identity=select(fields.map(e=>[e.id,reviewedLabel(e.id)]),v?.table_entry_id||root.value),selector=select([],''),value=select([],''),parameter=input(v?.parameter||''),selectorType=select(['text','integer','number','date'].map(t=>[t,t]),v?.selector_type||'text'),valueType=select(['text','integer','number','date'].map(t=>[t,t]),v?.value_type||'text');
  name.required=parameter.required=true;
  function updateFields(initial=false){const entry=fields.find(e=>e.id===identity.value),allowed=fields.filter(e=>e.source.file===entry?.source.file);for(const [control,saved] of [[selector,initial?v?.selector_entry_id:selector.value],[value,initial?v?.value_entry_id:value.value]]){control.replaceChildren(...allowed.map(e=>{const option=el('option',reviewedLabel(e.id));option.value=e.id;return option;}));if(allowed.some(e=>e.id===saved))control.value=saved;}}
  updateFields(true);identity.addEventListener('change',()=>updateFields());
  row.append(field('선택값 이름',name),field('표 식별용 승인 필드',identity),field('선택에 사용할 승인 필드',selector),field('선택 조건 자료형',selectorType),field('선택 조건 매개변수 이름',parameter),field('반환할 승인 필드',value),field('반환값 자료형',valueType),el('p','최대 4개. 같은 표의 승인 필드만 선택합니다. 매개변수를 위 목록에 같은 자료형으로 등록하세요. 실제 일치 행 exactly_one, 반환값 require_nonnull, 비교 binary_exact를 적용합니다.','muted'));
  return {value:()=>({name:name.value,table_entry_id:identity.value,selector_entry_id:selector.value,selector_type:selectorType.value,parameter:parameter.value,value_entry_id:value.value,value_type:valueType.value,cardinality:'exactly_one',null_policy:'require_nonnull',comparison:'binary_exact'})};
 });
 const addTypedFilter=rowsSection('자료형을 지정한 비교 · 선택 사항',filters,(row,v)=>{
  const left=fieldRef(row,v?.left),op=select(['eq','lt','lte','gt','gte'].map(k=>[k,k]),v?.op||'eq'),type=select(['text','integer','number','date'].map(t=>[t,t]),v?.value_type||'text'),mode=select([['scalar','단일 선택값'],['field','이미 연결된 필드']],v?.right?.kind||'scalar'),binding=input(v?.right?.binding||''),second=el('section',undefined,'reviewed-comparison-fields'),right=fieldRef(second,v?.right?.kind==='field'?v.right:null),scalarField=field('위에서 정의한 선택값 이름',binding);
  function toggle(){const scalar=mode.value==='scalar';scalarField.hidden=!scalar;binding.disabled=!scalar||!mutable();binding.required=scalar;second.hidden=scalar;second.querySelectorAll('input,select').forEach(n=>n.disabled=scalar||!mutable());}mode.addEventListener('change',toggle);toggle();
  row.append(field('비교 연산',op),field('양쪽 값의 자료형',type),field('오른쪽 비교 대상',mode),scalarField,second,el('p','왼쪽과 필드 비교의 오른쪽은 기준 표 또는 승인 관계로 이미 연결된 별칭이어야 합니다. binary_exact로 비교하며 대소문자나 숫자 문자열을 변환하지 않습니다. 후보 필드의 NULL은 unknown으로 제외하고 집계합니다.','muted'));
  return {value:()=>({op:op.value,left:{kind:'field',...left.ref()},right:mode.value==='scalar'?{kind:'scalar',binding:binding.value}:{kind:'field',...right.ref()},value_type:type.value,null_policy:'unknown_excluded',comparison:'binary_exact'})};
 });
 const addProjection=rowsSection('출력 열',projections,(row,v)=>{const ref=fieldRef(row,v?.field),name=input(v?.name||'');row.append(field('출력 이름',name));return {value:()=>({field:ref.ref(),name:name.value})};});
 const addGroup=rowsSection('그룹 키',groups,(row,v)=>{const ref=fieldRef(row,v);return {value:ref.ref};});
 const addAggregate=rowsSection('집계',aggregates,(row,v)=>{
  const op=select(['sum','count_rows','count_distinct','sum_product'].map(k=>[k,k]),v?.op||'sum'),name=input(v?.name||''),ref=fieldRef(row,v?.op==='sum_product'?v.left:v?.field);
  const product=el('section',undefined,'reviewed-product-fields'),right=fieldRef(product,v?.right),unit=input(v?.unit||'');unit.maxLength=4000;
  unit.placeholder='예: cents · 검토자가 확인한 결과 단위';
  product.append(field('검토한 결과 단위 · 자동 단위 검증 아님',unit),el('p','위 첫 번째 필드와 이 두 번째 필드는 모두 기준 표의 기준 행 별칭이어야 합니다. 두 정수를 행별로 곱한 뒤 합산합니다. 입력·각 곱·최종 합은 부호 있는 64비트 정수 범위여야 하며, 범위를 벗어나면 실행에 실패합니다. 한쪽이라도 NULL인 행은 제외합니다. 단위는 검토자의 표기이며 환산하거나 검증하지 않습니다.','muted'));
  const rightLabels=product.querySelectorAll('label');if(rightLabels[0]?.firstChild)rightLabels[0].firstChild.textContent='두 번째 승인 필드';if(rightLabels[1]?.firstChild)rightLabels[1].firstChild.textContent='두 번째 표 별칭';
  function toggleProduct(){const active=op.value==='sum_product';product.hidden=!active;unit.required=active;product.querySelectorAll('input,select').forEach(n=>n.disabled=!active||!mutable());}
  op.addEventListener('change',toggleProduct);toggleProduct();
  row.append(field('집계 방식',op),field('출력 이름',name),el('p','SUM은 기준 행의 열만 선택하세요. count_rows는 필드 선택을 사용하지 않습니다.','muted'),product);
  return {value:()=>{
   if(op.value!=='sum_product')return {op:op.value,name:name.value,...(op.value==='count_rows'?{}:{field:ref.ref()})};
   const left=ref.ref(),second=right.ref(),rootEntry=fields.find(e=>e.id===root.value);
   if([left,second].some(f=>f.alias!==alias.value||fields.find(e=>e.id===f.entry_id)?.source.file!==rootEntry?.source.file))throw Error('sum_product의 두 필드와 별칭은 모두 기준 표의 기준 행이어야 합니다.');
   if(!unit.value.trim())throw Error('sum_product의 검토한 결과 단위를 입력하세요.');
   return {op:'sum_product',name:name.value,left,right:second,numeric_type:'integer',unit:unit.value.trim(),null_policy:'exclude_if_any_operand_null'};
  }};
 });
 const policyList=el('div');form.append(el('h4','검토한 정책 문단'),policyList,reviewedCatalog('paragraph',op=>{if(op.kind!=='database_document_review'||op.state!=='completed')throw Error('완료된 문단 검토를 선택하세요.');if(policies.some(p=>p.id===op.id))return;policies.push(op);const card=el('section');card.append(reviewedParagraph(op.result.paragraph),el('p',op.result.interpretation,'source-quote'),button('참조 제거',()=>{policies.splice(policies.indexOf(op),1);card.remove();markReviewedDirty(key);}));policyList.append(card);markReviewedDirty(key);}));
 form.append(field('결과 의미',kind),field('한계 · 한 줄에 하나',limits),field('중복 출력 제거 DISTINCT',distinct),el('p','그룹 집계가 있으면 모든 일반 출력 열을 그룹 키에도 추가하세요. NULL은 집계에서 제외하며 빈 그룹은 생략합니다.','muted'));
 const save=el('button','정의 검증 후 제안 저장','primary');save.type='submit';submissionControl(save,!mutable());form.append(save);form.addEventListener('submit',event=>{event.preventDefault();if(!form.reportValidity()||state.busy)return;task(async()=>{const pairs=parameters.map(p=>p.value());if(new Set(pairs.map(p=>p[0])).size!==pairs.length)throw Error('매개변수 이름이 중복됩니다.');const relationIds=joins.map(j=>j.operation());const spec={id:id.value,title:title.value,question_scope:scope.value,root:{entry_id:root.value,alias:alias.value},joins:joins.map(j=>j.value()),parameters:Object.fromEntries(pairs),filters:filters.map(f=>f.value()),projection:projections.map(p=>p.value()),group_by:groups.map(g=>g.value()),aggregates:aggregates.map(a=>a.value()),distinct:distinct.checked,output_kind:kind.value,limitations:limits.value.split('\n').filter(v=>v.trim()),policy_references:policies.map(p=>({review_operation_id:p.id})),null_policy:'exclude_from_aggregates_preserve_projection',empty_groups:'absent',measure_grain:alias.value};if(s?.scalar_bindings!==undefined||scalarBindings.length||spec.filters.some(f=>f.left)){spec.scalar_bindings=scalarBindings.map(b=>b.value());if(spec.scalar_bindings.length>4)throw Error('단일 값 선택은 최대 4개입니다.');}if(new Set(spec.joins.map(j=>j.relation_id)).size!==spec.joins.length)throw Error('같은 관계의 여러 버전을 함께 선택할 수 없습니다.');await reviewedSubmit('database_query_propose',{spec,origin:{kind:'human_authored_ui',...(copy?{copied_operation_id:copy.id}:{})},relation_operation_ids:[...new Set(relationIds)]});});});
 if(s){for(const [name,type] of Object.entries(s.parameters))addParameter({name,type});(s.scalar_bindings||[]).forEach(addScalar);s.filters.forEach(f=>f.left?addTypedFilter(f):addFilter(f));s.projection.forEach(addProjection);s.group_by.forEach(addGroup);s.aggregates.forEach(addAggregate);for(const j of s.joins)addJoin({...j});box.append(el('p','새 사본의 관계 승인과 정책 문단은 저장 목록에서 다시 선택하세요. 이전 승인과 결과는 바뀌지 않습니다.','callout'));}
 form.addEventListener('input',()=>reviewedUI.dirty.add(key));form.addEventListener('change',()=>reviewedUI.dirty.add(key));if(!mutable())form.querySelectorAll('input,textarea,select,button').forEach(n=>n.disabled=true);box.append(form);reviewedUI.forms.set(key+':relational',box);return box;
}
function reviewedRun(op){const a=op.result.artifact,s=a.spec,box=el('section',undefined,'reviewed-run'),controls={},preview=el('div');box.append(el('h4','승인된 정의 실행'),el('p','매개변수 값은 이 실행에만 적용됩니다. 승인한 정의가 값을 고정하지 않습니다. 현재 의존성은 미점검이며 서버가 실행 시 확인합니다.','callout'));for(const [name,type] of Object.entries(s.parameters)){const n=input('',type==='date'?'date':'text');controls[name]=n;box.append(field(`${name} · ${type}`,n));n.addEventListener('input',draw);}function draw(){preview.replaceChildren(el('h4','이번 실행의 비교 조건'));if(s.query_kind==='directed_reachability')preview.append(reviewedReachabilitySummary(s,a,controls));else for(const f of s.filters)preview.append(el('p',reviewedFilterLabel(f,a,controls)));if(s.scalar_bindings?.length)preview.append(reviewedScalarSummary(s,a,controls));}draw();box.append(preview);const run=button('승인된 질의 실행',()=>task(async()=>{const parameters={};for(const [name,type] of Object.entries(s.parameters)){let value=controls[name].value;if(type==='integer'||type==='number'){if(!value.trim()||!Number.isFinite(Number(value))||type==='integer'&&!Number.isSafeInteger(Number(value)))throw Error(`${name}: 정확히 표현할 수 있는 ${type} 값을 입력하세요.`);value=Number(value);}parameters[name]=value;}await reviewedSubmit('database_query_execute',{approval_operation_id:op.id,parameters});}),'primary');submissionControl(run,!mutable());box.append(run);return box;}
function sourceReasoningOperation(op){
 const key=reviewedKey()+':source-operation:'+op.id;if(reviewedUI.forms.has(key))return reviewedUI.forms.get(key);
 const card=el('article',undefined,'card source-reasoning'),r=op.result||{},plan=r.plan,receipt=r.receipt;
 const names={database_reasoning_propose:'투영·온톨로지 계획',database_reasoning_approve:'추론 계획 승인',database_reasoning_execute:'원본 연결 RDFS 추론 기록',database_reasoning_advisory_use:'선택한 도출문의 참고 사용 기록'};
 card.append(el('h3',names[op.kind]),badge(op.state),el('p',`저장 버전 ${op.revision} · ${op.id}`,'reviewed-hash'),el('p','원래 질의 답은 수정하지 않습니다. 검토한 의미와 RDFS 공리에 따른 참고 근거이며, 외부 사실성·업무 승인·SHACL 검증을 뜻하지 않습니다. 확인은 로컬 결정이며 검토자 신원을 인증하지 않습니다.','callout'));
 if(op.error)card.append(operationError(op.error));
 if(op.revision!==state.current.revision)card.append(el('p','다른 버전의 과거 기록입니다. 현재 자료에 다시 적용할 수 없으며 원래 기록을 표시합니다.','callout'));
 if(!state.current.local_reasoning?.enabled)card.append(el('p','실행기가 비활성화되어 새 승인·실행·참고 저장은 사용할 수 없습니다. 과거 기록은 읽을 수 있습니다.','callout'));
 const enabled=mutable()&&op.revision===state.current.revision&&Boolean(state.current.local_reasoning?.enabled)&&op.state==='completed'&&r.eligible===true;
 for(const [id,label] of [[r.execution_operation_id||op.request.execution_operation_id,'원래 질의 답 열기'],[r.proposal_operation_id||op.request.proposal_operation_id,'투영·온톨로지 계획 열기'],[r.approval_operation_id||op.request.approval_operation_id,'이 실행의 계획 승인 열기'],[r.reasoning_operation_id||op.request.reasoning_operation_id,'이 참고의 추론 실행 열기']])if(id)card.append(button(label,()=>task(()=>openSavedOperation(state.current.id,id))));
 if(plan){const p=plan.projection;card.append(kv({'계획 지문':plan.fingerprint,'규칙 프로필':plan.profile,'실행기 SHA256':plan.binary_sha256,'원래 질의 실행':r.execution_operation_id}),el('p',plan.projection_spec.interpretation,'source-quote'),detail('검토할 투영 정의 · 한계',plan.projection_spec),detail('원본·질의 승인·매개변수 연결',plan.binding),detail('행·열·NULL 누락·집계 표현·의존성 명세',p.manifest));
  for(const [label,value] of [['원본 값의 투영 · asserted',p.projection_data],['검토한 행 의미 · asserted',p.projection_semantics],['온톨로지 원문 · asserted',p.ontology?.original],['허용된 온톨로지 직렬화 · asserted',p.ontology?.normalized],['실제 실행에 제출할 결합 입력',p.combined_input]])card.append(detail(label,value));
 }
 if(r.review)card.append(detail('명시적 검토 확인 · 신원 인증 아님',r.review));
 if(op.kind==='database_reasoning_propose'&&plan){const note=el('textarea'),confirm=input('','checkbox'),dirty=reviewedKey()+':approval:'+op.id;note.maxLength=4000;card.append(field('계획 승인 검토 메모',note),field('저장된 투영·원문 온톨로지·누락·한계를 확인하고 이 계획을 승인합니다',confirm));const approve=button('이 추론 계획만 승인',()=>task(async()=>{if(!confirm.checked||!note.value.trim())throw Error('검토 메모와 명시적 확인이 필요합니다.');await reviewedSubmit('database_reasoning_approve',{proposal_operation_id:op.id,note:note.value,human_confirmed:true});}));submissionControl(approve,!enabled);card.append(approve);note.addEventListener('input',()=>markReviewedDirty(dirty));confirm.addEventListener('change',()=>markReviewedDirty(dirty));}
 if(op.kind==='database_reasoning_approve'){const run=button('승인한 입력으로 OO 추론 실행',()=>task(()=>reviewedSubmit('database_reasoning_execute',{approval_operation_id:op.id})));submissionControl(run,!enabled);card.append(el('p','승인은 실행하지 않습니다. 이 버튼이 별도 로컬 실행을 시작하며 실패 시 자동 재시도하지 않습니다.','muted'),run);}
 if(receipt){const event=(receipt.events||[]).find(e=>e.command==='reason')?.result||{};card.append(kv({'실행 상태':receipt.status,'규칙 프로필':receipt.profile,'종료점 도달':String(receipt.reasoning_complete),'산출물 보존':receipt.artifact_completeness,'출력 제한':String(receipt.output_limit_reached),'인증서 별도 검증':receipt.certificate_verification||'미확인','입력 SHA256':receipt.input_sha256,'실행기 SHA256':receipt.binary_sha256,'규칙 팩 SHA256':event.truth_maintenance?.rule_pack_sha256||'보고 없음'}),detail('실제 입력 · asserted',receipt.asserted_turtle??'입력 보존 없음'),detail('전체 closure · asserted와 derived 포함',receipt.closure_turtle??'closure 보존 없음'));
  for(const name of ['asserted.tsv','derivations.tsv','scope.tsv','refutation.tsv'])card.append(detail('원시 산출물 · '+name,receipt.derivation_artifacts?.[name]||'파일이 보존되지 않았습니다. 검증 통과를 뜻하지 않습니다.'));
  card.append(detail('실제 영수증 · 이벤트·표준 출력·오류·출처',receipt));
 }
 if(op.kind==='database_reasoning_execute'){
  if(!r.eligible)card.append(el('p','실패·미완료·누락·출력 제한이 있는 기록은 참고 근거로 사용할 수 없습니다. 남아 있는 원시 영수증은 위에서 확인하세요.','callout'));
  const statements=r.derived_statements||[];card.append(el('h4',`입력과 구별한 도출문 ${statements.length}개`),el('p','closure에서 투영 값·검토 의미·온톨로지 입력을 뺀 집합입니다. 관측 행의 도출된 rdf:type만 참고 저장 대상으로 선택할 수 있습니다. 온톨로지 자체의 도출문은 원문에 남습니다.','muted'),detail('전체 도출문 · asserted 제외',statements));
  const choices=statements.filter(s=>s.advisory_eligible),selected=new Map(),dirty=reviewedKey()+':advisory:'+op.id;
  const selection=el('details');selection.append(el('summary',`참고로 저장할 행 분류 선택 · ${choices.length}개`));for(const s of choices){const check=input('','checkbox');selected.set(s.id,check);const label=field(typeof s.triple==='string'?s.triple:JSON.stringify(s.triple),check);label.className='derived-choice';selection.append(label);check.addEventListener('change',()=>markReviewedDirty(dirty));}card.append(selection);
  if(choices.length){const interpretation=el('textarea'),note=el('textarea'),confirm=input('','checkbox');interpretation.maxLength=note.maxLength=4000;card.append(field('선택한 도출문의 참고 해석',interpretation),field('참고 사용 검토 메모',note),field('선택한 문장을 원래 답과 별도인 참고 근거로 저장합니다',confirm));for(const n of [interpretation,note,confirm])n.addEventListener('input',()=>markReviewedDirty(dirty));const save=button('선택한 도출문을 참고 기록으로 저장',()=>task(async()=>{const ids=[...selected].filter(([,n])=>n.checked).map(([id])=>id);if(!ids.length||ids.length>200||!interpretation.value.trim()||!note.value.trim()||!confirm.checked)throw Error('1–200개 도출문·해석·검토 메모·별도 확인이 필요합니다.');await reviewedSubmit('database_reasoning_advisory_use',{reasoning_operation_id:op.id,execution_operation_id:r.execution_operation_id,selected_statement_ids:ids,interpretation:interpretation.value,note:note.value,human_confirmed:true});}));submissionControl(save,!enabled);card.append(save);}
 }
 if(r.status==='advisory_use'){const selectedView=el('div');card.append(el('h4','원래 답과 별도로 저장한 참고 근거'),el('p',r.interpretation,'source-quote'),detail('선택한 도출문 식별자',r.selected_statement_ids),button('저장한 참고 문장 원문 불러오기',()=>task(async()=>{const saved=await api({action:'operation',id:state.current.id,operation_id:r.reasoning_operation_id});const ids=new Set(r.selected_statement_ids),facts=(saved.result?.derived_statements||[]).filter(s=>ids.has(s.id));selectedView.replaceChildren(detail('선택한 도출문 · 원래 추론 기록에서 조회',facts));if(facts.length!==ids.size)selectedView.append(el('p','일부 선택 문장을 확인할 수 없습니다. 근거가 없는 문장을 보완하지 않았습니다.','callout'));})),selectedView,el('p','원래 답·질의 승인·필드 의미는 이 참고 저장으로 바뀌지 않았습니다.','muted'));}
 card.append(detail('요청·저장 상태·연결 진단',op));if(!enabled)card.querySelectorAll('input,textarea,select').forEach(n=>n.disabled=true);if(terminalStates.has(op.state))reviewedUI.forms.set(key,card);return card;
}
function sourceReasoningPanel(op){
 const box=el('details',undefined,'source-reasoning');box.dataset.sourceReasoningExecution=op.id;
 box.append(el('summary','저장된 질의 결과에서 추론 · 별도 참고 근거'),el('p','원래 답과 행은 그대로 보존합니다. 출력 행을 관측 자료로 투영하고, 온톨로지 제안 저장 → 별도 승인 → 명시적 실행 → 선택한 도출문 참고 저장 순서로 진행합니다.','callout'));
 box.append(el('p','집계 행도 질의 결과 관측입니다. 실제 개체의 동일성·배송 사실·업무 승인·외부 완전성을 뜻하지 않습니다. NULL은 누락 명세에 보존하며, 없는 RDF를 거짓으로 판단하지 않습니다.','muted'));
 const list=el('div'),more=button('이 답의 추론·참고 기록 불러오기',()=>task(()=>load(false)));let cursor=null;
 async function load(next){const page=await api({action:'database_reasoning_catalog',id:state.current.id,revision:state.current.revision,execution_operation_id:op.id,cursor:next?cursor:null});if(!next)list.replaceChildren();for(const item of page.items||[]){const d=el('article',undefined,'entry');d.append(el('p',`${item.kind||'추론 기록'} · ${item.state||item.status||'상태 미확인'} · 버전 ${item.revision??'?'} · ${item.id}${item.stale?' · 과거 버전':''}`),button('이 추론 연결 기록 열기',()=>task(()=>openSavedOperation(state.current.id,item.id))));list.append(d);}if(!page.items?.length)list.append(el('p','이 기록 구간에 저장된 연결이 없습니다.','muted'));cursor=page.next_cursor;more.textContent=cursor?'다음 연결 기록 불러오기':'연결 목록 새로 확인';more.onclick=()=>task(()=>load(Boolean(cursor)));}
 box.append(more,list);
 if(!state.current.local_reasoning?.enabled)box.append(el('p','로컬 실행기가 비활성화되어 새 실행을 시작할 수 없습니다. 저장된 계획·실패·추론·참고 기록은 위 목록에서 읽을 수 있습니다.','callout'));
 const a=op.result?.artifact;
 if(op.state!=='completed'||!a||a.query_kind==='directed_reachability'||a.truncated||a.status!=='complete'){
  box.append(el('p','완료된 일반 관계형 질의의 전체 출력만 투영할 수 있습니다. 실패·행 제한·경로 탐색 결과는 새 추론에 사용할 수 없습니다. 원래 기록은 보존됩니다.','callout'));return box;
 }
 const form=el('details');form.append(el('summary','투영과 RDFS 온톨로지 작성'));
 const key=reviewedKey()+':projection:'+op.id,rowClass=input('urn:factory-lab:semantics:QueryResultObservation'),interpretation=el('textarea'),limitations=el('textarea'),ontology=el('textarea');
 rowClass.maxLength=1000;interpretation.maxLength=4000;limitations.maxLength=8000;ontology.maxLength=16384;ontology.className='ontology-input';
 ontology.placeholder='<urn:factory-lab:semantics:QueryResultObservation> <http://www.w3.org/2000/01/rdf-schema#subClassOf> <urn:factory-lab:semantics:ReviewEvidence> .';
 const mappings=el('div'),rows=[];
 const outputNames=Object.keys(a.rows?.[0]||{});
 if(!outputNames.length)form.append(el('p','저장 결과가 0행입니다. 승인한 질의 정의에서 출력 이름을 확인해 입력하세요. 서버가 저장된 정의의 이름인지 검증합니다. 0행은 외부 사실 부재를 뜻하지 않습니다.','callout'));
 function addMapping(){if(rows.length>=20)throw Error('매핑은 최대 20개입니다.');const row=el('div',undefined,'projection-column'),name=outputNames.length?select([['','출력 열 선택'],...outputNames.map(n=>[n,n])],''):input(''),predicate=input('urn:factory-lab:semantics:'),datatype=select([['','자료형 명시'],['text','문자열'],['integer','정확한 signed64 정수']],'');row.append(field('저장된 출력 열',name),field('술어 IRI',predicate),field('선언할 자료형',datatype));const record={row,name,predicate,datatype};rows.push(record);row.append(button('이 매핑 삭제',()=>{rows.splice(rows.indexOf(record),1);row.remove();markReviewedDirty(key);}));mappings.append(row);}
 const add=button('출력 열 매핑 추가',()=>{addMapping();markReviewedDirty(key);});addMapping();
 form.append(field('관측 행 클래스 IRI',rowClass),el('p','클래스·술어는 urn:factory-lab:semantics: 이름공간을 사용합니다. 자료형은 샘플에서 자동 추정하지 않습니다. 매핑하지 않은 열과 NULL은 별도 명세에 남습니다.','muted'),mappings,add,field('이 투영의 해석',interpretation),field('해석의 한계 · 한 줄에 하나',limitations),field('검토할 RDFS 온톨로지 · UTF-8 최대 16 KiB',ontology),el('p','허용 공리: subClassOf, subPropertyOf, domain, range. 가져오기·개체 사실·빈 노드는 지원하지 않습니다. 최대 200행·20열·5,000트리플·전체 입력 64 KiB이며 초과 시 잘라서 실행하지 않습니다.','muted'));
 const save=button('투영·온톨로지 계획 저장',()=>task(async()=>{
  if(!interpretation.value.trim()||!limitations.value.trim()||!ontology.value.trim()||!rows.length||rows.some(r=>!r.name.value||!r.datatype.value))throw Error('출력 열·자료형·해석·한계·온톨로지를 명시하세요.');
  const bytes=new TextEncoder().encode(ontology.value);if(bytes.length>16384)throw Error('온톨로지 UTF-8 입력은 최대 16 KiB입니다.');let binary='';for(const byte of bytes)binary+=String.fromCharCode(byte);
  await reviewedSubmit('database_reasoning_propose',{execution_operation_id:op.id,projection_spec:{row_class_iri:rowClass.value,columns:rows.map(r=>({output_name:r.name.value,predicate_iri:r.predicate.value,datatype:r.datatype.value})),null_policy:'omit_with_manifest',subject_policy:'execution_row_ordinal',interpretation:interpretation.value,limitations:limitations.value.split('\n').map(s=>s.trim()).filter(Boolean)},ontology_base64:btoa(binary),profile:'rdfs'});
 }));submissionControl(save,!mutable()||!state.current.local_reasoning?.enabled);form.append(save);form.addEventListener('input',()=>markReviewedDirty(key));form.addEventListener('change',()=>markReviewedDirty(key));if(!mutable())form.querySelectorAll('input,textarea,select,button').forEach(n=>n.disabled=true);box.append(form);return box;
}
function reviewedExternalProvenance(artifact){
 const origins=[];if(artifact?.origin?.format==='external-relation-origin-1')origins.push(['이 관계',artifact.origin]);
 for(const [name,relation] of Object.entries(artifact?.dependencies?.relations||artifact?.provenance?.dependencies?.relations||{}))if(relation.origin?.format==='external-relation-origin-1')origins.push([name,relation.origin]);
 const box=el('section',undefined,'reviewed-external-provenance');if(!origins.length)return box;
 box.append(el('h4','외부 후보에서 이어진 관계 근거'),el('p','아래 연결은 저장된 파일과 로컬 검토 기록입니다. 생산자 신원과 실제 생성 입력은 인증하지 않았으며 정책 해석이나 사실성을 보증하지 않습니다.','callout'));
 for(const [name,origin] of origins){const d=el('details');d.append(el('summary',name+' · '+origin.candidate_kind),kv({'가져오기 기록':origin.import_operation_id,'외부 후보':origin.candidate_id,'외부 파일 SHA256':origin.raw_sha256,'후보 내용 SHA256':origin.candidate_payload_sha256||'상세 기록 참조','스냅샷 SHA256':origin.source?.snapshot_sha256||'기록 확인 필요','끝점 수정':String(origin.endpoint_edit),'수정 이유':origin.edit_reason}),el('p',origin.interpretation,'source-quote'),detail('원래 후보 · 끝점 · 로컬 연결',origin),button('이 관계의 외부 가져오기 기록 열기',()=>task(()=>openSavedOperation(state.current.id,origin.import_operation_id))));box.append(d);}
 return box;
}
function reviewedOperation(op){if(op.kind==='database_question_scope')return questionScopeOperation(op);if(sourceReasoningActions.has(op.kind))return sourceReasoningOperation(op);const cacheKey=reviewedKey()+':operation:'+op.id;if(reviewedUI.forms.has(cacheKey))return reviewedUI.forms.get(cacheKey);const card=el('article',undefined,'card reviewed-operation'),r=op.result,a=r?.artifact;card.append(el('h3',({database_external_relation_propose:'외부 후보의 관계 제안',database_external_relation_reject:'외부 관계 후보 선택 제외',database_relation_propose:'관계 제안',database_relation_approve:'관계 승인',database_query_propose:'질의 제안',database_query_approve:'질의 승인',database_query_execute:'질의 실행',database_document_review:'문단 검토',database_document_read:'검토 문단 조회'})[op.kind]),badge(op.state),el('p',`저장 버전 ${op.revision} · ${op.created}`,'muted'));if(op.error)card.append(operationError(op.error));if(r?.rejection){const rejection=r.rejection;card.append(el('p','이 후보를 선택에서 제외한 기록입니다. 기존 승인 대기 제안과 승인된 관계는 취소하지 않습니다. 기존 제안은 계속 승인할 수 있으며, 해석을 바꾸려면 새 제안을 저장하세요.','callout'),el('p',rejection.reason,'source-quote'),kv({'외부 후보':rejection.candidate_id,'후보 종류':rejection.candidate_kind,'외부 파일 SHA256':rejection.raw_sha256,'스냅샷 SHA256':rejection.source?.snapshot_sha256,'생산자 인증':'인증되지 않음'}),detail('선택 제외의 원본 연결',rejection),button('선택 제외한 후보의 가져오기 기록 열기',()=>task(()=>openSavedOperation(state.current.id,rejection.import_operation_id))));}if(a)card.append(reviewedExternalProvenance(a));if(r?.paragraph)card.append(reviewedParagraph(r.paragraph),el('p',r.interpretation,'source-quote'),el('p','문단 참조 검토 기록입니다. 정책 적용 여부와 실행 정책의 정확성은 미확인입니다.','callout'));
 if(op.kind==='database_document_review'&&op.state==='completed'){const read=button('검토한 원문 조회 기록 저장',()=>task(()=>reviewedSubmit('database_document_read',{review_operation_id:op.id})));submissionControl(read,!mutable());card.append(read);}
 if(a?.spec){card.append(reviewedSpecView(a));const deps=a.kind==='query'?a.dependencies.fields:a.dependencies;const dependencies=table(['의존 필드','저장된 해석'],Object.values(deps||{}).map(d=>[`${d.entry.source.file}.${d.entry.source.column}`,d.entry.interpretation]));dependencies.classList.add('reviewed-dependencies');dependencies.setAttribute('aria-label','의존 필드와 저장된 해석 · 가로 스크롤 가능');card.append(dependencies);for(const rid of r.relation_operation_ids||[])card.append(button('저장된 관계 승인 열기 · '+rid.slice(0,12),()=>task(()=>openSavedOperation(state.current.id,rid))));for(const evidence of r.reviewed_document_evidence||[])card.append(reviewedParagraph(evidence.paragraph),el('p',evidence.interpretation,'source-quote'));if(a.status==='pending'){const note=el('textarea'),confirm=input('','checkbox');note.maxLength=4000;note.addEventListener('input',()=>reviewedUI.dirty.add(reviewedKey()+':approval:'+op.id));confirm.addEventListener('change',()=>reviewedUI.dirty.add(reviewedKey()+':approval:'+op.id));card.append(field('이 저장본을 검토한 메모',note),field('저장된 원본·조건·한계를 확인하고 이 정의를 승인합니다',confirm));const approve=button('이 저장된 정의 승인',()=>task(async()=>{if(!confirm.checked||!note.value.trim())throw Error('검토 메모와 명시적 확인이 필요합니다.');await reviewedSubmit(a.kind==='relation'?'database_relation_approve':'database_query_approve',{proposal_operation_id:op.id,note:note.value,human_confirmed:true});}));submissionControl(approve,!mutable());card.append(approve);}if(a.kind==='query'){card.append(button('새 사본 편집',()=>{if(!canLeave())return;reviewedUI.forms.delete(reviewedKey()+':query');const editor=reviewedQueryBuilder(op);state.tab='questions';render();openReviewedEditor();editor.scrollIntoView({block:'start'});}));if(a.status==='approved')card.append(reviewedRun(op));}}
 if(a?.rows&&a.query_kind==='directed_reachability')card.append(reviewedReachabilityResult(a,op,r));
 if(a?.rows&&a.query_kind!=='directed_reachability'){if(op.request?.approval_operation_id)card.append(button('이 실행의 질의 승인 열기',()=>task(()=>openSavedOperation(state.current.id,op.request.approval_operation_id))));card.append(kv({'일치 기준 행':a.matched_root_rows,'전체 출력 행':a.total_output_rows,'반환 행':a.returned_count,'결과 제한':a.truncated?'일부만 표시':'전체 출력 표시','결과 의미':a.output_kind}),table(Object.keys(a.rows[0]||{}),a.rows.map(row=>Object.values(row).map(databaseValue))),el('p',a.rows.length?'고정 스냅샷과 승인한 질의 범위의 결과입니다.':'이 스냅샷의 질의 조건에서 일치 결과가 없습니다. 외부 자료의 부재를 뜻하지 않습니다.','callout'),table(['집계','NULL 제외 행'],Object.entries(a.aggregate_null_exclusions)),table(['관계','NULL 자식 키','부모 미연결 키'],a.join_observations.map(j=>[j.relation_id,j.null_child_keys,j.unmatched_nonnull_child_keys])),el('p','연결 관측은 질문 필터 적용 전 자식 표 전체 범위입니다.','muted'),kv({'질의 지문':a.provenance.contract_fingerprint,'원본 SHA256':a.provenance.source.snapshot_sha256}),table(['실행 매개변수','값'],Object.entries(a.provenance.parameters).map(([k,v])=>[k,databaseValue(v)])));if(a.product_aggregate_observations){const diagnostics=el('section',undefined,'reviewed-product-observations');diagnostics.append(el('h4','행별 곱의 합계 · NULL 제외 내역'),el('p','질문 조건에 맞는 전체 기준 행의 집계입니다. 출력 행 제한 전이며, 양쪽 모두 NULL인 행은 제외 행 수에서 한 번만 셉니다. 단위는 검토자의 표기이며 자동 검증 결과가 아닙니다.','muted'));for(const [name,d] of Object.entries(a.product_aggregate_observations))diagnostics.append(el('h4',name),kv({'검토한 결과 단위':d.unit,'결과 표시 형식':d.value_encoding==='decimal_integer_string'?'정확한 정수의 십진 문자열 · 반올림 없음':d.value_encoding||'기록 없음','숫자 범위':'signed64 정수 · 입력·각 곱·최종 합 범위 초과 시 실패','왼쪽 NULL 행':d.left_null_rows,'오른쪽 NULL 행':d.right_null_rows,'제외 행 (중복 제외)':d.excluded_rows,'포함한 곱의 수':d.included_terms}));card.append(diagnostics);}if(a.scalar_binding_observations?.length){const observations=el('section',undefined,'reviewed-scalar-observations');observations.append(el('h4','실행에서 선택한 단일 값'),el('p','승인된 정의와 같은 스냅샷에서 선택한 값입니다. 필드 의미·업무 정책의 정확성을 보증하지 않습니다.','muted'));for(const b of a.scalar_binding_observations)observations.append(el('h4',b.name),kv({'선택 매개변수':b.parameter,'선택에 사용한 값':databaseValue(b.selector_value),'선택 자료형':b.selector_type,'선택값 표시 형식':b.selector_value_encoding==='decimal_integer_string'?'정확한 정수의 십진 문자열 · 반올림 없음':b.selector_value_encoding||'기록 없음','실제로 선택한 값':databaseValue(b.resolved_value),'반환 자료형':b.value_type,'반환값 표시 형식':b.resolved_value_encoding==='decimal_integer_string'?'정확한 정수의 십진 문자열 · 반올림 없음':b.resolved_value_encoding||'기록 없음','실제 일치 행':b.matched_rows,'선택 규칙':`${b.cardinality} · ${b.null_policy} · ${b.comparison}`,'표 식별 필드 ID':b.field_entry_ids.table_entry_id,'선택 필드 ID':b.field_entry_ids.selector_entry_id,'반환 필드 ID':b.field_entry_ids.value_entry_id,'선택 정의 지문':b.binding_fingerprint,'원본 SHA256':b.source.snapshot_sha256}));card.append(observations);}if(a.comparison_null_exclusions?.length)card.append(el('h4','자료형 지정 비교 · NULL 제외 관측'),el('p','필터 번호는 저장된 전체 필터 목록의 1부터 시작하는 순서입니다. 질문 필터 적용 전, 관계를 연결한 전체 기준 행에서 셉니다. 각 필터의 NULL 행은 서로 겹칠 수 있습니다.','muted'),table(['필터 번호','NULL로 비교 불가한 행'],a.comparison_null_exclusions.map(d=>[d.filter_index+1,d.null_rows])));for(const l of a.limitations)card.append(el('p',l,'callout'));for(const d of r.reviewed_document_evidence||[])card.append(reviewedParagraph(d.paragraph),el('p',d.interpretation,'source-quote'));}
 if(op.kind==='database_query_execute'&&isDatabaseWorkspace())card.append(sourceReasoningPanel(op));
 card.append(el('p','정책 해석·사실성·업무상 완전성은 확인하지 않습니다. 현재 의존성은 미점검입니다. 과거 결과는 당시 저장본입니다.','muted'),detail('요청과 저장 기록 · 진단용',{id:op.id,request:op.request,result:r,error:op.error}));if(!mutable())card.querySelectorAll('input,textarea,select').forEach(n=>n.disabled=true);if(terminalStates.has(op.state))reviewedUI.forms.set(cacheKey,card);return card;}
function reviewedReviewPanel(root){root.append(reviewedDocuments(),reviewedRelations());for(const category of ['relation','query','paragraph'])root.append(reviewedCatalog(category));for(const op of state.current.operations.filter(o=>reviewedActions.has(o.kind)&&!['database_query_execute','database_question_scope'].includes(o.kind)))root.append(operationCard(op));}

function renderDatabaseLibrary(root){
 databaseOnboarding(root);
 heading(root,'등록 원본과 표 구조','고정된 데이터베이스 스냅샷의 전체 표 수와 행 수를 표시합니다.');databaseSourceSummary(root);
 const sources=state.current.draft.sources;if(!sources.length){root.append(el('p','등록 스냅샷에 표가 없습니다.','muted'));return;}
 const chosen=databaseUI.tables.get(state.current.id)||sources[0].name,choice=select(sources.map(s=>[s.name,`${s.name} · 전체 ${s.row_count}행`]),chosen),preview=el('article',undefined,'card database-source-preview');
 const draw=()=>{const source=sources.find(s=>s.name===choice.value);databaseUI.tables.set(state.current.id,source.name);preview.replaceChildren(el('h3',source.name),el('p',`전체 ${source.row_count}행 · 아래는 ${source.sample.length}행 샘플 (최대 ${source.sample_limit}행)`,'muted'),table(source.headers,source.sample.map(row=>source.headers.map(c=>databaseValue(row[c])))),detail('관측한 열과 키 선언',{columns:source.columns,primary_key:source.primary_key,foreign_keys:source.foreign_keys}),el('p','키와 외래키는 저장된 선언입니다. 업무 의미를 확인하거나 조인 실행을 승인한 결과가 아닙니다.','muted'));};
 choice.addEventListener('change',draw);root.append(field('미리볼 등록 표',choice),preview);draw();
 root.append(reviewedDocuments());
 root.append(detail('관계 선언 · 실행하지 않는 후보',state.current.draft.relationship_proposals||[]),el('p','데이터 정리에서 원문 문단과 선언된 외래키를 검토하고, 질문하기에서 형식화한 질의를 저장·승인·실행할 수 있습니다. 자연어 해석과 업무 판단은 자동 검증하지 않습니다.','callout'));
}
function renderDatabaseReview(root){
 databaseOnboarding(root);
 const latest=state.current.latest_extension;
 if(latest){const notice=el('section',undefined,'card proposal-receipt');notice.dataset.testid='latest-semantic-proposal';notice.append(el('h2',latest.origin==='observed_native_semantic_generation'?'생성한 의미 초안 · 원본과 비교':'가져온 의미 초안 · 원본과 비교'),el('p',`원본 열 ${latest.physical_columns}개 · 의미 용어/개념 ${latest.semantic_concepts}개 · 관계 기록 ${latest.relation_candidates}개 (선언 FK ${latest.declared_relations} · 의미 관계 ${latest.semantic_relations}) · 미지원 ${latest.unsupported}개`),el('p',latest.stale?'이 제안은 이전 자료 버전 기준입니다. 원래 결과와 현재 승인을 구분해서 확인하세요.':'결과는 자동 저장됐습니다. 원본 값·기존 승인·질문 조회는 아직 바꾸지 않았습니다. 아래 비교 표에서 필요한 열만 선택해 의미를 확인하세요.','muted'),button('원본 값과 제안 비교 표 열기',()=>task(()=>openSavedOperation(state.current.id,latest.operation_id)),'primary'));root.append(notice);const loaded=state.current.operations.find(o=>o.id===latest.operation_id&&!o.summary_only);if(loaded)root.append(operationCard(loaded));}
 databaseShapesPanel(root);
 appendReviewInventory(root);
 const advanced=el('details',undefined,'review-secondary');advanced.append(el('summary','표 연결·조회 정의·문서 검토 · 고급 설정'),el('p','필드 승인 뒤 여러 표를 연결하거나 재사용할 조회를 정의할 때 사용합니다. 단순 원본 열 검토에는 필요하지 않습니다.','muted'));reviewedReviewPanel(advanced);root.append(advanced);extensionPanel(root,new Set(latest?[latest.operation_id]:[]));const reasoning=el('details',undefined,'review-secondary');reasoning.append(el('summary','RDF 규칙으로 분류 확인 · 선택 기능'));reasoningPanel(reasoning);root.append(reasoning);
}
const shapesUI=new Map();
function databaseShapesPanel(root){
 const box=el('section',undefined,'card database-shapes');box.dataset.testid='database-shapes';
 box.append(el('h2','SHACL 초안 · 원본 선언으로 만들고 표본 검사'),el('p','DB에 명시된 타입·NOT NULL에서 초안을 만듭니다. LLM 호출 없이 생성하며, 업무 규칙·재고 충분 여부·정책 적용 조건을 추론하지 않습니다.','muted'));
 const make=button('DB 선언에서 SHACL 초안 만들기 · 모델 호출 없음',()=>task(()=>extensionSend({action:'database_shapes_propose',id:state.current.id,revision:state.current.revision,request_key:crypto.randomUUID()})));make.disabled=!mutable()||hasPending();box.append(make);
 const saved=state.current.operations.filter(o=>['database_shapes_propose','database_shapes_validate'].includes(o.kind));
 for(const op of saved.slice(0,6))box.append(operationCard(op));
 if(!saved.length)box.append(el('p','아직 생성한 SHACL 초안이 없습니다. 의미 제안 생성과 별도 기능이며, 생성·검사 결과는 검토 자료로 저장됩니다.','muted'));
 root.append(box);
}
function databaseShapesOperation(op){
 const card=el('article',undefined,'card shapes-operation');card.append(el('h3',op.kind==='database_shapes_propose'?'생성한 SHACL 초안':'SHACL 표본 검사 기록'),badge(op.state),el('p',`자료 버전 ${op.revision} · ${op.created}`,'muted'));
 if(op.summary_only){card.append(button('저장된 SHACL 결과 열기',()=>task(()=>openSavedOperation(state.current.id,op.id))));return card;}
 if(op.error){card.append(operationError(op.error));return card;}
 const result=op.result;if(!result){card.append(el('p','저장된 처리 상태를 확인하세요. 자동으로 다시 실행하지 않습니다.'));return card;}
 if(op.kind==='database_shapes_validate'){
  const report=result.report;card.append(el('p',report.status==='completed'?(report.conforms?'지정한 표본·제약 범위에서 위반 없음':'지정한 표본에서 제약 위반 발견'):'검사를 완료하지 못했습니다: '+report.status,'callout'));
  if(report.status==='completed')card.append(kv({'실제 검사기':report.engine,'검사 대상 행':report.target_count,'NodeShape':report.shape_count,'PropertyShape':report.property_shape_count,'위반 수':report.result_count}));
  if(report.reason)card.append(el('p',report.reason));
  for(const violation of report.results||[])card.append(kv({'대상':violation.focus_nodes?.join('\n'),'속성':violation.paths?.join('\n'),'설명':violation.messages?.join('\n')}));
  card.append(el('p','전체 DB·현재 재고·업무상 사실성을 검증한 결과가 아닙니다. 이 검사는 승인 상태나 LLM 답변을 자동으로 바꾸지 않습니다.','muted'),detail('검사한 SHACL 원문',result.shapes_turtle),detail('원본 결합·검사 범위',report));return card;
 }
 const a=result.artifact,key=reviewedKey()+':shapes:'+op.id,dirty=key+':edit';let edited=shapesUI.get(key)??a.shapes_turtle;
 const editor=el('textarea');editor.value=edited;editor.rows=12;editor.maxLength=262144;editor.className='shapes-turtle';editor.setAttribute('aria-label','검토·수정할 SHACL Turtle');editor.disabled=!mutable()||op.revision!==state.current.revision;
 editor.addEventListener('input',()=>{edited=editor.value;shapesUI.set(key,edited);markReviewedDirty(dirty);});
 card.append(el('p',`원본 선언에서 만든 규칙 ${a.rules.length}개 · 내보낸 표본 ${a.exported_rows}행 · 검사 최대 ${a.limits.rows}행. LLM 의미 제안에서 만든 업무 제약이 아닙니다.`,'callout'),table(['표·열','근거 선언','SHACL 타입','필수 값'],a.rules.map(r=>[`${r.table}.${r.column}`,r.declared_type,r.datatype?.split('#').at(-1)||'제약 없음',r.min_count===1?'명시적 NOT NULL → minCount 1':'필수 선언 없음'])),field('SHACL 초안 · 필요하면 수정 후 표본 검사',editor));
 const test=button('현재 SHACL로 표본 검사·결과 저장 · 모델 호출 없음',()=>task(async()=>{const request_key=crypto.randomUUID();await extensionSend({action:'database_shapes_validate',id:state.current.id,revision:state.current.revision,request_key,proposal_operation_id:op.id,shapes_turtle:editor.value});if(state.current.operations.some(o=>o.request_key===request_key&&terminalStates.has(o.state)))reviewedUI.dirty.delete(dirty);}));test.disabled=!mutable()||hasPending()||op.revision!==state.current.revision;
 const download=button('현재 SHACL Turtle 다운로드',()=>{const url=URL.createObjectURL(new Blob([editor.value],{type:'text/turtle;charset=utf-8'})),link=el('a');link.href=url;link.download=`shacl-draft-v${op.revision}.ttl`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});card.append(test,download,el('p','단순 타입·minCount·maxCount와 내보낸 행 대상만 지원합니다. SPARQL·JS·규칙·외부 가져오기는 실행하지 않습니다. 검사 통과는 업무 규칙 승인이나 사실성 보증이 아닙니다.','muted'),detail('검사할 RDF 표본 · 전체 DB 아님',a.sample_data_turtle),detail('생성에서 제외한 항목과 근거',a.omissions),detail('원본·표본 결합과 한계',a.source_binding));return card;
}
function reviewedQuestionPanel(name,label,initialOpen){
 const key=reviewedKey()+':'+name,box=el('details',undefined,'card reviewed-question-panel');box.dataset.reviewedPanel=name;
 box.open=reviewedUI.questionPanels.has(key)?reviewedUI.questionPanels.get(key):initialOpen;box.append(el('summary',label));
 box.addEventListener('toggle',()=>{if(box.isConnected)reviewedUI.questionPanels.set(key,box.open);});return box;
}
function openReviewedEditor(){const editor=document.querySelector('[data-reviewed-panel="editor"]');if(editor){for(let node=editor;node;node=node.parentElement)if(node.tagName==='DETAILS'){node.open=true;if(node.dataset.reviewedPanel)reviewedUI.questionPanels.set(reviewedKey()+':'+node.dataset.reviewedPanel,true);}editor.querySelector('summary').focus();}}
const questionScopeReasons={source_not_supplied:'필요한 자료가 제공되지 않음 · 운영자 판단',retrieval_not_performed:'필요한 조회를 아직 수행하지 않음',unsupported_operation:'현재 지원하지 않는 작업',needs_external_verification:'외부 확인이 필요함'};
function questionScopeForm(){
 const key=reviewedKey()+':question-scope';if(reviewedUI.forms.has(key))return reviewedUI.forms.get(key);
 const box=el('details',undefined,'card question-scope-form');box.append(el('summary','답하지 못한 질문과 필요한 근거 기록'));
 const question=el('textarea'),requirements=el('textarea'),reason=select(Object.entries(questionScopeReasons),'retrieval_not_performed'),note=el('textarea'),evidence=el('textarea'),confirm=input('','checkbox');
 question.maxLength=note.maxLength=4000;requirements.maxLength=20019;evidence.maxLength=3000;
 for(const [name,n] of Object.entries({question,requirements,reason,note,evidence,confirm}))n.dataset.questionScopeField=name;
 box.append(el('p','운영자가 미해결 사유와 추가로 필요한 근거를 남깁니다. 이 저장은 질의 실행이나 원본 부재의 자동 판정이 아니며 모델을 호출하지 않습니다.','callout'),field('답하지 못한 질문',question),field('추가로 필요한 근거 · 한 줄에 하나, 최대 20개',requirements),field('미해결 사유 · 운영자 분류',reason),field('판단 설명 · 확인한 범위와 남은 작업',note),field('선택할 저장 근거 ID · 선택 사항, 한 줄에 하나',evidence),el('p','같은 자료실·현재 버전에서 완료된 질의 실행 또는 검토 문단 조회만 선택할 수 있습니다. 서버가 원본 연결을 확인합니다. 선택하지 않은 자료는 미검색 범위로 남습니다.','muted'));
 const available=el('details');available.append(el('summary','불러온 저장 근거 ID 확인'));
 const candidates=state.current.operations.filter(o=>o.revision===state.current.revision&&o.state==='completed'&&['database_query_execute','database_document_read'].includes(o.kind));
 if(!candidates.length)available.append(el('p','현재 불러온 기록에 선택 가능한 근거가 없습니다. 근거 없이도 미해결 사유를 저장할 수 있습니다.','muted'));
 for(const op of candidates){const add=button('이 근거 ID 추가',()=>{const ids=evidence.value.split('\n').map(v=>v.trim()).filter(Boolean);if(!ids.includes(op.id)){ids.push(op.id);evidence.value=ids.join('\n');markReviewedDirty(key);}});add.disabled=!mutable();available.append(el('p',`${op.kind==='database_query_execute'?'질의 실행':'검토 문단 조회'} · ${op.id}`,'reviewed-hash'),add);}
 box.append(available,field('미해결 사유는 나의 판단이며, 자료 부재·질문 범위·외부 사실이 자동 검증되지 않았음을 확인합니다',confirm));
 const save=button('미해결 질문 기록 저장',()=>task(async()=>{
  const payload={question:question.value.trim(),unresolved_requirements:requirements.value.split('\n').map(v=>v.trim()).filter(Boolean),reason_kind:reason.value,assessment_note:note.value.trim(),evidence_operation_ids:evidence.value.split('\n').map(v=>v.trim()).filter(Boolean),human_confirmed:confirm.checked};
  if(!validReviewedPayload('database_question_scope',payload))throw Error('질문, 필요한 근거(각 1,000자 이하), 판단 설명과 명시적 확인을 입력하세요. 근거 ID는 중복 없이 최대 20개입니다.');
  await reviewedSubmit('database_question_scope',payload);
 }),'primary');submissionControl(save,!mutable());box.append(save);
 for(const n of [question,requirements,reason,note,evidence,confirm]){n.disabled=!mutable();n.addEventListener('input',()=>markReviewedDirty(key));n.addEventListener('change',()=>markReviewedDirty(key));}
 reviewedUI.forms.set(key,box);return box;
}
function questionScopeOperation(op){
 const card=el('article',undefined,'card question-scope-result'),r=op.result;
 card.append(el('h3','미해결 질문 · 운영자 판단'),badge(op.state),el('p',`저장 버전 ${op.revision} · ${op.id}`,'reviewed-hash'));
 if(op.error)card.append(operationError(op.error));
 if(r&&op.state==='completed'){
  card.append(el('p',r.question,'source-quote'),el('p',questionScopeReasons[r.reason_kind]||r.reason_kind),el('p',r.assessment_note),el('p','질문에 대한 답이나 원본 부재 판정이 아닙니다. 운영자가 기록한 미해결 사유이며 질문 범위와 부재 여부는 검증하지 않았습니다.','callout'));
  const needs=el('ul');for(const requirement of r.unresolved_requirements||[])needs.append(el('li',requirement));card.append(el('h4','추가로 필요한 근거'),needs,el('p',`저장된 원본: ${r.source?.label||r.source?.source_id||'기록 없음'} · 선택 근거 ${(r.evidence||[]).length}개`,'muted'),el('p','미검색 범위: 선택한 저장 근거 밖의 모든 자료. 이번 저장은 추가 조회나 부재 검사를 수행하지 않았습니다.','muted'));
  if(op.revision!==state.current.revision)card.append(el('p','현재 화면과 다른 버전의 과거 판단입니다. 아래 원본과 구조는 저장 당시 범위입니다.','callout'));
  const selected=el('details');selected.append(el('summary',`선택한 저장 근거 · ${(r.evidence||[]).length}개`));
  for(const e of r.evidence||[])selected.append(el('p',`${e.kind} · ${e.operation_id}`,'reviewed-hash'),detail('저장 근거 요약',e.summary),button('이 저장 근거 열기',()=>task(()=>openSavedOperation(state.current.id,e.operation_id))));
  if(!r.evidence?.length)selected.append(el('p','선택한 저장 근거가 없습니다.'));
  card.append(selected,detail('저장 당시 원본 버전·스키마 범위',{source:r.source,schema_inventory:r.schema_inventory,scope:r.scope}),detail('요청·근거 해시·확인 기록',{id:op.id,request_key:op.request_key,request:op.request,result:r}));
 }
 card.append(button('동일 요청의 저장 기록 다시 열기',()=>task(()=>openSavedOperation(state.current.id,op.id))));return card;
}
function renderDatabaseQuestions(root){
 renderConversation(root,state.current.operations.filter(o=>o.kind==='question'));
 const tools=reviewedQuestionPanel('advanced-tools','고급 조회 도구',false);tools.dataset.testid='database-advanced-tools';
 tools.append(el('p','질의 정의 작성, 저장된 승인과 실행, 원본의 일치 값 조회를 열 수 있습니다. 도구를 여는 것만으로 실행하지 않습니다.','muted'));
 tools.addEventListener('input',updateAdvancedToolsLabel);tools.addEventListener('change',updateAdvancedToolsLabel);
 tools.querySelector('summary').textContent='고급 조회 도구'+(reviewedDirty()?' · 저장하지 않은 변경 있음':'');root.append(tools);
 tools.append(questionScopeForm());
 const scopeRecords=state.current.operations.filter(o=>o.kind==='database_question_scope');
 if(scopeRecords.length){const scopes=reviewedQuestionPanel('question-scopes',`미해결 질문 기록 · 불러온 기록 ${scopeRecords.length}개`,true);for(const op of scopeRecords)scopes.append(operationCard(op));tools.append(scopes);}
 // Saved chronology, never detail-loading order; equal timestamps use the store's id ordering.
 const executions=state.current.operations.filter(o=>o.kind==='database_query_execute').sort((a,b)=>a.created===b.created?(a.id<b.id?-1:a.id>b.id?1:0):(a.created>b.created?-1:1)),approvals=state.current.operations.filter(o=>o.kind==='database_query_approve');
 if(!approvals.length){const guidance=el('div',undefined,'callout');guidance.append(el('p','불러온 기록에 승인된 질의가 없습니다. 저장된 승인을 더 불러오거나 새 정의를 작성할 수 있습니다. 원본 자료의 부재를 뜻하지 않습니다.'),button('질의 도구 열기',()=>{tools.open=true;reviewedUI.questionPanels.set(reviewedKey()+':advanced-tools',true);tools.querySelector('summary').focus();}));guidance.querySelector('button').dataset.testid='database-open-query-tools';tools.append(guidance);}
 const current=executions[0];
 if(current){const result=el('section',undefined,'current-answer');result.append(el('div','최근 불러온 질의 실행','eyebrow'),operationCard(current));tools.append(result);}
 const editor=reviewedQuestionPanel('editor','질의 정의 작성',false),editorLabel=editor.querySelector('summary');
 const updateEditorLabel=()=>{editorLabel.textContent='질의 정의 작성'+(reviewedUI.dirty.has(reviewedKey()+':query')?' · 저장하지 않은 변경 있음':'');};
 updateEditorLabel();editor.addEventListener('input',updateEditorLabel);editor.addEventListener('change',updateEditorLabel);editor.append(reviewedQueryBuilder());tools.append(editor);
 const saved=reviewedQuestionPanel('approvals',`저장된 질의 승인 · 불러온 기록 ${approvals.length}개`,false);saved.append(reviewedCatalog('query'));for(const op of approvals)saved.append(operationCard(op));tools.append(saved);
 if(executions.length>1){const older=executions.slice(1),failed=older.filter(op=>op.state!=='completed').length,history=reviewedQuestionPanel('executions',`이전 질의 실행 · 불러온 기록 ${older.length}개${failed?' · 완료되지 않은 기록 '+failed+'개':''}`,false);for(const op of older)history.append(operationCard(op));tools.append(history);}
 const catalog=state.current.row_lookup_catalog||[],form=el('article',undefined,'card database-row-lookup');
 if(!catalog.length)form.append(el('p','승인한 원본 열이 없습니다. 데이터 정리에서 의미를 검토하고 승인하세요. 원본에 데이터가 없다는 뜻은 아닙니다.','callout'));
 else{
  const choice=select(catalog.map(c=>[c.entry_id,`${c.file} · ${c.column} · 전체 ${c.total_source_rows}행`]),catalog[0].entry_id),type=select([['text','문자열'],['number','숫자'],['null','NULL (값 없음)']],'text'),value=input(),scope=el('div');
  const update=()=>{const c=catalog.find(c=>c.entry_id===choice.value);scope.replaceChildren(el('p',c.reviewed_interpretation,'source-quote'),detail('승인한 조회 범위',{source_id:c.source_id,source_version:c.source_version,table:c.file,column:c.column,total_source_rows:c.total_source_rows}));value.disabled=type.value==='null'||!mutable();};choice.addEventListener('change',update);type.addEventListener('change',update);update();
  const run=button('전체 스냅샷에서 일치 행 조회',()=>{let selected=value.value;if(type.value==='number'){if(!value.value.trim()||!Number.isFinite(Number(value.value))){$('error').hidden=false;$('error').textContent='유한한 숫자 값을 입력하세요.';return;}selected=Number(value.value);if(Number.isInteger(selected)&&!Number.isSafeInteger(selected)){$('error').hidden=false;$('error').textContent='이 정수는 브라우저가 정확히 표현할 수 없습니다. 식별자라면 문자열로 조회하세요.';return;}}if(type.value==='null')selected=null;execute(null,crypto.randomUUID(),state.current.revision,null,{entry_id:choice.value,value:selected});},'primary');submissionControl(run,!mutable());choice.disabled=type.disabled=!mutable();
  form.append(field('조회할 승인 원본 열',choice),scope,field('일치 값의 자료형',type),field('정확히 일치할 값 · 빈 문자열도 가능',value),run,el('p','최대 50행을 반환하며 전체 일치 행 수를 별도로 기록합니다. 대소문자·자료형 비교는 저장된 SQLite 열의 규칙을 따릅니다.','muted'));
 }
 tools.append(form);
 const history=el('details',undefined,'card database-history');history.open=true;history.append(el('summary','저장된 원본 조회 기록'));
 for(const op of state.current.operations.filter(o=>o.kind==='source_lookup'))history.append(operationCard(op));appendHistoryMore(history);tools.append(history);
}
function databaseLookupResult(op){
 const card=el('article',undefined,'card database-lookup-result'),r=op.result;card.append(el('h3','등록 스냅샷의 원본 조회'),badge(op.state),el('p',`요청 당시 자료실 버전 ${op.revision}`,'muted'));
 if(op.error)card.append(operationError(op.error));
 if(op.state==='completed'&&r){
  const scope=r.scope||{},selection=op.request?.selection||{},hasValue=Object.hasOwn(selection,'value')||Object.hasOwn(scope,'value'),savedValue=Object.hasOwn(selection,'value')?selection.value:scope.value;
  const predicate=el('section',undefined,'database-saved-predicate');predicate.append(el('h4','저장된 조회 조건'),kv({'원본 표':scope.file||'기록 없음','조회한 열':scope.column||'기록 없음','일치 조건':'정확히 같은 값','조회한 값':hasValue?JSON.stringify(savedValue):'기록 없음','값의 자료형':!hasValue?'기록 없음':savedValue===null?'NULL (값 없음)':typeof savedValue==='number'?'숫자':typeof savedValue==='string'?'문자열':typeof savedValue,'승인한 의미':scope.reviewed_interpretation||'기록 없음','고정 원본 버전':r.source_version||'기록 없음'}));card.append(predicate);
  card.append(kv({'전체 표 행 수':r.total_source_rows,'전체 일치 행 수':r.total_matching_rows,'반환한 행 수':r.returned_count,'반환 한도':r.limit,'결과 제한':r.truncated?'일부 행만 반환됨':'일치 범위 전체 반환됨'}),el('p','조회한 고정 스냅샷과 선택한 열의 범위입니다. 현재 원본의 최신성이나 다른 자료의 부재를 판정하지 않습니다.','callout'));
  const columns=r.scope?.reviewed_columns?.map(c=>c.column)||Object.keys(r.records[0]?.values||{});
  card.append(table(['결과 내 순번',...columns],r.records.map(row=>[row.source.match_index,...columns.map(c=>databaseValue(row.values[c]))])),el('p','결과 내 순번은 이번 응답 안의 순서이며 영구 행 식별자나 기본 키가 아닙니다. 중복 일치 행도 유지합니다.','muted'),detail('원본 버전·선택 범위·검토한 의미',{source_version:r.source_version,scope:r.scope,workspace:r.workspace,unreviewed_fields:r.unreviewed_fields}),detail('저장된 조회 결과 전체',r));
 }else if(!op.error)card.append(el('p','완료된 조회 결과가 없습니다. 요청 복구에서 상태를 확인하세요.','callout'));
 card.append(button('저장된 조회 기록 다시 열기',()=>task(()=>openSavedOperation(state.current.id,op.id))));return card;
}
function renderDatabaseChanges(root){
 heading(root,'검토 버전과 고정 원본','새 데이터는 운영자가 새 스냅샷으로 등록해야 합니다. 기존 원본이나 승인을 새 원본에 자동으로 옮기지 않습니다.');databaseSourceSummary(root);
 const history=el('article',undefined,'card');history.append(el('h3','저장된 검토 버전'));
 for(const v of state.current.versions)history.append(button(`버전 ${v.number} 열기`,()=>{if(canLeave())task(async()=>show(await api({action:'get',id:state.current.id,revision:v.number})));}));
 history.append(button('현재 버전으로 돌아가기',()=>{if(canLeave())task(async()=>show(await api({action:'get',id:state.current.id,revision:null})));}));root.append(history);
}

function renderLibrary(root){
 const workspace=state.current,draft=workspace.draft;
 heading(root,'원본 자료','업로드한 원문을 그대로 보관합니다. 미리보기의 빈 셀은 미확인 값입니다.');root.querySelector('h2').dataset.preparationTarget='sources';
 const meta=el('article',undefined,'card');meta.append(kv({'자료 버전':draft.metadata.snapshot_id,'자료 기준일':draft.metadata.as_of,'통화':currencyLabel(draft.metadata.currency)}));root.append(meta);
 state.sourceSelections??=new Map();
 const selected=state.sourceSelections.get(workspace.id);
 const initial=draft.sources.find(source=>source.name===selected)||draft.sources[0];
 if(initial){
  const layout=el('div',undefined,'source-layout'),navigator=el('nav',undefined,'source-navigator'),preview=el('div',undefined,'source-preview-region');
  navigator.setAttribute('aria-label','원본 파일 선택');preview.id='selected-source-preview';
  const sourceLabel=source=>`${source.name} · ${source.kind==='table'?`표 ${source.rows.length}행`:`문서 ${source.paragraphs.length}문단`}`;
  const choice=select(draft.sources.map(source=>[source.name,sourceLabel(source)]),initial.name);
  choice.setAttribute('aria-controls',preview.id);
  const mobile=field('확인할 원본 파일',choice);mobile.className='source-mobile-selector';
  const buttons=new Map();
  const choose=name=>{
   const source=draft.sources.find(item=>item.name===name);if(!source)return;
   state.sourceSelections.set(workspace.id,name);choice.value=name;
   for(const [filename,control] of buttons){control.setAttribute('aria-current',filename===name?'true':'false');}
   preview.replaceChildren(sourcePreview(source));
  };
  for(const source of draft.sources){const control=button(sourceLabel(source),()=>choose(source.name));control.setAttribute('aria-controls',preview.id);buttons.set(source.name,control);navigator.append(control);}
  choice.addEventListener('change',()=>choose(choice.value));choose(initial.name);
  layout.append(mobile,navigator,preview);root.append(layout);
 }else root.append(el('p','저장된 원본 파일이 없습니다.','empty'));
 root.append(detail('고정 분류 규칙 · OWL 공리',draft.ontology));
}
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
function decisionEditor(entry,withSelection=false){const pending=state.edits.get(entry.id);if(pending)entry={...entry,...pending};const card=el('div',undefined,'entry');card.dataset.reviewId=entry.id;const title=el('div',undefined,'entry-title');let checked;if(withSelection){checked=input('','checkbox');checked.setAttribute('aria-label',`${entry.source.column} 선택`);title.append(checked);}title.append(el('label',entry.source.column||`${entry.source.file} · ${entry.kind==='policy'?'정책 문단 '+entry.source.paragraph:'관계 후보'}`),badge(entry.status));card.append(title);const external=(state.current.draft.extension_reviews||[]).filter(r=>r.entry_id===entry.id);if(external.length)card.append(detail('외부 제안에서 가져온 사람 검토 이력 · 현재 결정과 대조 필요',external));const source=state.current.draft.sources.find(s=>s.name===entry.source.file);if(entry.kind==='mapping'){card.append(el('p','원본 예시: '+source.rows.slice(0,3).map(r=>r[entry.source.column]||'(빈 값)').join(' / '),'muted'));}else if(entry.kind==='policy'){card.append(el('p',entry.source.text,'source-quote'),el('p',`${entry.source.file} · 원문 ${entry.source.line_start}–${entry.source.line_end}행`,'muted'),el('p','적용 대상, 금액 기준, 예외, 시행일이 아래 규칙과 일치하는지 확인하세요.','callout'));}else{card.append(el('p',`${entry.source.file}의 ${entry.source.column}의 연결 후보를 기록합니다. 승인만으로 자동 조회가 실행되지는 않습니다. 설명과 양쪽 열을 승인하면 질문하기에서 관계와 값을 직접 선택해 대조할 수 있습니다. 기존 업무 계산은 고정된 참조 규칙을 사용합니다.`,'muted'),el('p',relationOrigin(entry),'muted'));}for(const question of (Array.isArray(entry.extraction?.questions)?entry.extraction.questions:[]).filter(v=>typeof v==='string'))card.append(el('p',question,'callout'));for(const ref of (Array.isArray(entry.extraction?.related_policy_statements)?entry.extraction.related_policy_statements:[]).filter(v=>v&&typeof v==='object'&&typeof v.entry_id==='string')){const other=state.current.draft.entries.find(e=>e.id===ref.entry_id);card.append(el('p',`${ref.file} · ${ref.line_start}–${ref.line_end}행`,'muted'));if(other?.source.text)card.append(el('p',other.source.text,'source-quote'));}const relationPanel=el('div');if(entry.kind==='relation'){relationPanel.append(relationEvidence(entry));card.append(relationPanel);}const mentionPanel=el('div');if(entry.kind!=='policy'){mentionPanel.append(sourceMentions(entry));card.append(mentionPanel);}if(entry.extraction?.source_evidence)card.append(proposalEvidence(entry));const grid=el('div',undefined,'review-grid'),target=targetControl(entry),status=select(Object.entries(labels).filter(([k])=>['pending','approved','excluded','insufficient'].includes(k)),entry.status),note=el('textarea'),interpretation=el('textarea');if(entry.kind==='relation')target.addEventListener('change',()=>{const selected={...entry,target:JSON.parse(target.value)};mentionPanel.replaceChildren(sourceMentions(selected));relationPanel.replaceChildren(relationEvidence(selected));});status.setAttribute('aria-label','검토 상태');note.value=entry.note;interpretation.value=entry.interpretation;note.maxLength=interpretation.maxLength=4000;grid.append(field(entry.kind==='policy'?'적용할 규칙':entry.kind==='relation'?'검토할 연결 후보':'표준 필드',target),field('검토 상태',status));let meaning;if(entry.kind==='policy'){meaning=el('p',undefined,'source-quote');const inputs=el('div');const update=()=>{const c=state.current.contracts[target.value];meaning.textContent=c?c.meaning:'실행되는 규칙이 없습니다.';inputs.replaceChildren();const actual=state.current.policy_inputs?.[target.value];if(actual){inputs.append(el('p','아래는 승인된 필드에서 읽은 원본 값입니다. 정책 문장과 값·적용 대상이 일치하는지 확인하세요. 일치 여부를 자동 판정하거나 문장으로 계산 규칙을 바꾸지 않습니다.','callout'));for(const f of actual.fields){const block=el('details');block.append(el('summary',`${f.field} · ${f.state==='available'?'원본 값 확인':f.state==='ambiguous'?'승인 연결이 여러 개':'필드 연결 검토 필요'}`));if(f.source)block.append(el('p',`${f.source.file} · ${f.source.column}`,'muted'),table(['CSV 레코드','원문 행','원본 값'],f.records.map(v=>[v.record,`${v.line_start}–${v.line_end}`,v.value])),detail('필드 출처',f.source));inputs.append(block);}}};target.addEventListener('change',update);update();card.append(meaning,inputs);}const dateControls=[];if(entry.kind==='policy'){for(const [i,candidate] of (state.current.policy_date_candidates?.[entry.id]||[]).entries()){const saved=entry.temporal?.[i];const control=select([['unresolved','역할 확인 필요'],['start','적용 시작일 (당일 포함)'],['end','적용 종료일 (당일 포함)'],['context','참고 날짜 · 적용 기간 아님']],saved?.role||'unresolved');dateControls.push({candidate,control});grid.append(field(`${candidate.date} · 날짜 ${i+1}의 역할`,control));}if(dateControls.length)card.append(el('p','원문을 보고 각 날짜의 역할을 선택하세요. 참고 날짜로 분류해도 정책의 유효성이 자동 확인되는 것은 아닙니다. 적용 대상과 기간을 해석란에 기록하세요.','callout'));}if(entry.kind==='mapping'){interpretation.placeholder='예: 이 열은 주문의 고유 번호입니다. 환불 접수 번호와 구분합니다.';card.append(el('p','필드 설명은 승인한 열의 조회 목록과 근거에 함께 보관합니다. 모델에 전달될 수 있지만 새 계산 규칙이나 자동 연결을 만들지는 않습니다.','muted'));}grid.append(field(entry.kind==='mapping'?'이 필드의 업무 의미 · 적용 범위':'검토한 해석 · 적용 범위',interpretation),field('메모 · 제외한 이유',note));card.append(grid);for(const control of [target,status,note,interpretation,...dateControls.map(v=>v.control)]){control.disabled=!mutable();control.addEventListener('input',()=>{state.edits.set(entry.id,value());changed();});}const value=()=>({entry_id:entry.id,status:status.value,target:entry.kind==='relation'?JSON.parse(target.value):target.value,note:note.value,interpretation:interpretation.value,...(entry.kind==='policy'?{temporal:dateControls.map(v=>({...v.candidate,role:v.control.value}))}:{})});const save=button('이 항목 저장',()=>task(()=>saveDecisions([value()])));save.disabled=!mutable();card.append(save,detail('제안 근거 · 이전 검토 기록',{reason:entry.reason,source:entry.source,extraction:entry.extraction,overlap:entry.overlap,previous_decision:entry.previous_decision}));return {card,checked,value};}
async function generateSuggestions(requestKey,revision=state.current.revision){await task(async()=>{
 const storage='operations-generation-'+state.current.id,existing=recalled(storage);
 assertRequestAllowed(storage,requestKey);
 if(!existing)remember(storage,JSON.stringify({request_key:requestKey,revision,draft_digest:state.current.digest}));
 collectRecovery(state.current.id);renderRecovery();
 const stopProgress=watchQuestionProgress(state.current.id,requestKey);
 try{
  const response=await api({action:'suggest',id:state.current.id,revision,request_key:requestKey});
  stopProgress();
  resolveSubmitted(storage,requestKey,response.operation);
  await show(await api({action:'get',id:state.current.id,revision:null}));
  const messages={completed:'초안 생성 기록을 불러왔습니다. 제안을 확인한 뒤 적용하세요.',failed:'초안 생성에 실패했습니다. 저장된 오류 기록을 확인하세요.',interrupted:'초안 생성이 중단되었습니다. 저장된 기록을 확인하세요. 자동으로 다시 호출하지 않습니다.',cancelled:'초안 생성이 취소되었습니다. 이미 시작한 호출은 과금될 수 있으며, 받은 결과는 기록에 남습니다.'};
  $('notice').textContent=Object.hasOwn(messages,response.operation.state)?messages[response.operation.state]:'아직 실행 중인 요청입니다. 원래 생성 요청 확인으로 상태를 확인하세요. 새로 호출하지 않습니다.';
 }catch(error){stopProgress();render();$('notice').textContent='초안 생성 결과를 확인하지 못했습니다. 원래 요청 기록을 확인하세요. 자동으로 다시 호출하지 않습니다.';throw error;}
 finally{stopProgress();}
});}
// Imported artifacts are data. No upstream SQL, approval or provider identity is trusted.
const extensionUI={open:new Map(),staged:new Map(),views:new Map(),drafts:new Map(),reasoningOpen:new Map(),reasoningSavedOpen:new Map()};
function extensionKey(op){return `${state.current.id}:${op.id}`;}
function extensionPending(){return recalled('operations-extension-'+state.current.id);}
function extensionStaged(op){const key=extensionKey(op);if(!extensionUI.staged.has(key))extensionUI.staged.set(key,new Map());return extensionUI.staged.get(key);}
function extensionVolatile(){const prefix=state.current?.id+':';return [...extensionUI.staged].some(([k,v])=>k.startsWith(prefix)&&v.size)||[...extensionUI.drafts.keys()].some(k=>k.startsWith(prefix));}
function extensionDirty(){return state.edits.size>0||state.policies.size>0||extensionVolatile();}
async function extensionSend(payload,replay=false){
 const id=state.current.id,key='operations-extension-'+id;
 if([...recoveries.values()].some(r=>!r.resolved&&recalled(r.storage)===r.raw))throw Error('먼저 기존 요청 복구를 완료하세요.');
 if(extensionPending()&&(!replay||JSON.stringify(JSON.parse(extensionPending()).payload)!==JSON.stringify(payload)))throw Error('먼저 저장된 확장 요청의 상태를 확인하세요.');
 if(!mutable()||payload.revision!==state.current.revision)throw Error('원래 요청의 현재 활성 버전에서만 재전송할 수 있습니다.');
 const stored=JSON.stringify({request_key:payload.request_key,revision:payload.revision,payload});remember(key,stored);
 if(recalled(key)!==stored)throw Error('요청 복구 정보를 이 브라우저에 저장할 공간이 없습니다. 요청을 전송하지 않았습니다.');
 const stopProgress=payload.action==='local_reasoning'?watchQuestionProgress(id,payload.request_key,payload.action):()=>{};
 try{
  const response=await api(payload);
  stopProgress();
  if(['extension_review','extension_localize'].includes(response.operation.kind)&&response.operation.state==='completed'){
   await show(await api({action:'get',id,revision:null}));
   if(response.operation.kind==='extension_localize')retainOperation(await api({action:'operation',id,operation_id:payload.operation_id}));
  }
  if(response.operation.kind==='local_reasoning'){extensionUI.reasoningOpen.set(id,true);extensionUI.reasoningSavedOpen.set(id+':'+response.operation.id,true);}
  retainOperation(response.operation);extensionUI.open.set(id,true);state.tab='review';state.edited=extensionDirty();render();focusOperation(response.operation.id);
  if(terminalStates.has(response.operation.state)){remember(key,null);render();focusOperation(response.operation.id);}
  $('notice').textContent=response.operation.kind==='extension_localize'?(response.operation.state==='completed'?'한국어 번역 초안을 비교 표에 채웠습니다. 원본과 기존 승인은 그대로입니다.':'번역에 실패했습니다. 기록을 확인하세요. 자동 재시도하지 않습니다.'):response.operation.kind.startsWith('database_shapes_')?'SHACL 초안 또는 표본 검사 기록을 저장했습니다. 자동 승인·답변 차단은 하지 않습니다.':response.operation.kind==='local_reasoning'?operationProgressText(response.operation):response.operation.state==='completed'?(response.operation.kind==='extension_review'?'선택한 필드를 한 버전으로 승인했습니다. 나머지 후보는 현재 버전에서 다시 가져와야 합니다.':'외부 제안을 저장했습니다. 원본 필드의 의미와 연결은 아직 승인되지 않았습니다.'):'저장된 처리 결과를 확인하세요.';
 }catch(error){extensionUI.open.set(id,true);render();throw error;}finally{stopProgress();}
}
function reasoningPanel(root){
 const w=state.current,cap=w.local_reasoning||{},section=el('details',undefined,'reasoning-panel');
 section.open=extensionUI.reasoningOpen.get(w.id)||false;section.addEventListener('toggle',()=>{if(section.isConnected)extensionUI.reasoningOpen.set(w.id,section.open);});
 section.append(el('summary','OpenOntologies · 업로드한 RDF 추론'));
 section.append(el('p','업로드한 Turtle에 포함된 사실과 공리만 처리합니다. 자료실 원본과의 일치·포함 범위는 확인하지 않습니다. 결과는 참고용이며 필드 승인이나 업무 판단을 바꾸지 않습니다.','muted'));
 if(!cap.enabled)section.append(el('p','운영자가 로컬 추론 실행기를 설정하지 않았습니다. 저장된 결과는 읽을 수 있습니다.','callout'));
 else{
  const file=input('','file');file.accept='.ttl,text/turtle';const profile=select((cap.profiles||[]).map(p=>[p,p]),(cap.profiles||[])[0]);
  const run=button('업로드한 RDF로 로컬 추론 실행',()=>task(async()=>{
   const selected=file.files[0];if(!selected||selected.size>cap.max_input_bytes)throw Error(`Turtle 파일을 선택하세요. 최대 ${cap.max_input_bytes}바이트입니다.`);
   const bytes=new Uint8Array(await selected.arrayBuffer());new TextDecoder('utf-8',{fatal:true}).decode(bytes);let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
   await extensionSend({action:'local_reasoning',id:w.id,revision:w.revision,request_key:crypto.randomUUID(),asserted_base64:btoa(binary),profile:profile.value});
  }));
  const update=()=>{run.disabled=!mutable()||hasPending()||!file.files.length;};file.disabled=profile.disabled=!mutable()||hasPending();file.addEventListener('change',update);update();
  section.append(field(`사실·공리가 포함된 UTF-8 Turtle · 최대 ${cap.max_input_bytes}바이트`,file),field('실행할 규칙 프로필',profile),run,el('p','모델 호출 없이 서버의 로컬 실행기를 사용합니다. 실행 중 중지를 요청할 수 있습니다. 서버가 중단을 확인할 때까지 기다리며, 자료 준비 중에는 바로 멈추지 않을 수 있습니다. 새 실행은 별도 기록으로 남습니다.','muted'));
 }
 const runs=w.operations.filter(o=>o.kind==='local_reasoning');
 if(!runs.length)section.append(el('p','불러온 실행 목록에 로컬 추론 기록이 없습니다. 이전 실행 기록 더 보기에서 과거 기록을 확인할 수 있습니다.','muted'));
 for(const op of runs){const saved=el('details',undefined,'reasoning-saved'),savedKey=w.id+':'+op.id;saved.dataset.savedOperationId=op.id;saved.open=extensionUI.reasoningSavedOpen.get(savedKey)||false;saved.addEventListener('toggle',()=>{if(saved.isConnected)extensionUI.reasoningSavedOpen.set(savedKey,saved.open);});saved.append(el('summary',`${op.request?.profile||'저장된 프로필'} · 버전 ${op.revision} · ${labels[op.state]||op.state} · ${op.id}`),operationCard(op));section.append(saved);}
 if(runs.length>=2)reasoningComparison(section,runs);
 root.append(section);
}
function reasoningResult(op){
 const card=el('article',undefined,'card reasoning-result'),r=op.result?.receipt;
 card.append(el('h3','업로드한 RDF의 로컬 추론 기록'),badge(op.state),el('p',`요청 당시 자료 버전 ${op.revision} · 필드 승인 없음`,'muted'));
 card.append(el('p','이 기록은 업로드한 스냅샷만 다룹니다. 자료실 원본 포함 여부·완전성·외부 사실성은 확인하지 않았습니다. SHACL 검사 결과가 아닙니다.','callout'));
 if(op.revision!==state.current.revision)card.append(el('p','현재 자료 버전과 다른 과거 실행입니다. 재계산하지 않고 저장된 결과를 표시합니다.','muted'));
 if(op.error)card.append(operationError(op.error));
 if(!r){card.append(el('p','저장된 추론 실행 기록이 없습니다. 완료·추론 없음·통과로 해석할 수 없습니다.','callout'),detail('요청과 보존 상태',{request:op.request,status:op.result?.status,receipt_error:op.result?.receipt_error}));return card;}
 const names={completed:'실행 완료',partial:'부분 실행',timed_out:'시간 제한',failed:'실행 실패',cancelled:'실행 중단',running:'실행 중'},event=(r.events||[]).find(e=>e.command==='reason')?.result||{};
 card.append(kv({'실행 결과':names[r.status]||r.status,'규칙 프로필':r.profile,'반복 종료 확인':r.reasoning_complete===true?'실행기가 종료점 도달을 보고함':r.reasoning_complete===false?'종료점 미도달':'확인되지 않음','산출물 범위':r.artifact_completeness==='complete'?'실행 산출물 저장 완료':'부분 산출물일 수 있음','인증서 별도 검증':r.certificate_verification==='not_run'?'실행하지 않음':r.certificate_verification||'미확인','측정 시간(초)':r.elapsed_seconds}));
 if(r.status!=='completed'||r.output_limit_reached)card.append(el('p','이 실행은 완료된 결과로 사용할 수 없습니다. 아래 내용은 실패·시간 제한 또는 출력 제한 전에 남은 일부일 수 있습니다.','callout'));
 const counts={};for(const [key,label] of [['initial_triples','실행기가 보고한 초기 트리플'],['final_triples','실행기가 보고한 최종 트리플'],['inferred_count','실행기가 보고한 추가 추론']])if(Object.hasOwn(event,key))counts[label]=event[key];
 if(Object.keys(counts).length)card.append(kv(counts));else card.append(el('p','저장된 추론 집계가 없습니다. 0개라는 뜻이 아닙니다.','muted'));
 const samples=event.sample_inferences;
 if(Array.isArray(samples)&&samples.length){const d=el('details');d.append(el('summary',`실행기가 제공한 추론 예시 ${samples.length}개 · 전체 목록 아님`));samples.forEach(v=>d.append(el('pre',typeof v==='string'?v:JSON.stringify(v))));card.append(d);}
 else card.append(el('p','추론 예시가 제공되지 않았습니다. 전체 결과는 저장된 closure를 확인하세요.','muted'));
 if(event.certificate?.by_rule)card.append(detail('실행기가 보고한 규칙별 도출 수',event.certificate.by_rule));
 card.append(detail('입력 사실·공리 · 업로드 원문 Turtle',r.asserted_turtle??'입력 원문이 저장되지 않았습니다.'),detail('출력 closure · 입력과 도출 결과를 포함한 원문',r.closure_turtle??'출력 closure가 저장되지 않았습니다.'));
 const artifacts=r.derivation_artifacts||{};
 for(const [name,label] of [['asserted.tsv','입력 사실 목록'],['derivations.tsv','규칙·결론·전제 기록'],['scope.tsv','실행기가 기록한 처리 범위'],['refutation.tsv','반박 기록']]){
  const artifact=artifacts[name];card.append(detail(`${label} · ${name}`,artifact?{sha256:artifact.sha256,text:artifact.text}: '이 파일이 저장되지 않았습니다. 빈 결과나 검증 통과를 뜻하지 않습니다.'));
 }
 card.append(detail('입력·실행기·출력 출처',{input_sha256:r.input_sha256,input_bytes:r.input_bytes,binary_sha256:r.binary_sha256,profile:r.profile,rule_pack_sha256:event.truth_maintenance?.rule_pack_sha256,closure_sha256:r.closure_sha256,workspace_base_digest:op.result.base_workspace_digest,workspace_membership:op.result.workspace_membership,limits:r.limits}),detail('실행 이벤트 · 표준 출력 · 오류 출력',{events:r.events,stdout:r.stdout,stderr:r.stderr,exit_code:r.exit_code,output_limit_reached:r.output_limit_reached}));
 card.append(button('이 추론의 저장 기록 다시 열기',()=>task(()=>openSavedOperation(state.current.id,op.id))));return card;
}
function reasoningComparison(root,runs){
 const box=el('details',undefined,'reasoning-comparison');box.append(el('summary','저장된 두 실행 비교 · 원문 텍스트'));
 const options=runs.map(o=>[o.id,`${o.id} · 버전 ${o.revision} · ${labels[o.state]||o.state}`]),left=select(options,runs[1].id),right=select(options,runs[0].id),output=el('div'),controls=el('div',undefined,'review-grid');
 controls.append(field('비교할 이전 실행',left),field('비교할 이후 실행',right));
 box.append(el('p','저장 기록만 읽습니다. Turtle을 트리플로 해석하거나 의미 차이를 판정하지 않습니다. 줄 순서·공백·직렬화가 달라도 텍스트 차이로 표시합니다.','muted'),controls,button('저장된 입력·출력 비교',()=>task(async()=>{
  if(left.value===right.value)throw Error('서로 다른 두 실행을 선택하세요.');
  const a=await api({action:'operation',id:state.current.id,operation_id:left.value}),b=await api({action:'operation',id:state.current.id,operation_id:right.value});
  const ar=a.result?.receipt,br=b.result?.receipt;output.replaceChildren();
  output.append(table(['항목','이전 실행','이후 실행'],[['요청 버전',a.revision,b.revision],['실행 상태',ar?.status||a.state,br?.status||b.state],['프로필',ar?.profile,br?.profile],['입력 SHA-256',ar?.input_sha256,br?.input_sha256],['출력 SHA-256',ar?.closure_sha256,br?.closure_sha256],['실행기 SHA-256',ar?.binary_sha256,br?.binary_sha256]]));
  for(const [key,label] of [['asserted_turtle','입력 원문'],['closure_turtle','출력 원문']]){
   const section=el('details');section.append(el('summary',label+' · 같은 줄 번호의 텍스트 비교'));
   if(typeof ar?.[key]!=='string'||typeof br?.[key]!=='string')section.append(el('p','한쪽 또는 양쪽 원문이 저장되지 않아 비교할 수 없습니다.','callout'));
   else{const x=ar[key].split('\n'),y=br[key].split('\n'),changes=[];for(let i=0;i<Math.max(x.length,y.length);i++)if(x[i]!==y[i])changes.push([i+1,x[i]??'(이 줄 없음)',y[i]??'(이 줄 없음)']);section.append(el('p',`서로 다른 위치 ${changes.length}줄 · 처음 ${Math.min(100,changes.length)}줄 표시. RDF 사실의 추가·삭제 수가 아닙니다.`,'muted'),table(['줄 번호','이전 텍스트','이후 텍스트'],changes.slice(0,100)),detail('이전 전체 원문',ar[key]),detail('이후 전체 원문',br[key]));}
   output.append(section);
  }
  if(ar?.status!=='completed'||br?.status!=='completed')output.prepend(el('p','미완료 실행이 포함되어 있습니다. 차이가 추론의 완전한 변화라고 볼 수 없습니다.','callout'));
 })),output);root.append(box);
}

function extensionPanel(root,omit=new Set()){
 const w=state.current,box=el('details',undefined,'card extension-panel');box.open=extensionUI.open.get(w.id)||false;
 box.append(el('summary','다른 도구에서 만든 필드·관계 제안 파일 불러오기 · 선택'));
 box.addEventListener('toggle',()=>{if(box.isConnected)extensionUI.open.set(w.id,box.open);});
 box.append(el('h3','이미 만들어 둔 제안 파일이 있을 때만 사용하세요'),el('p','NVIDIA auto-ontology가 내보낸 YAML 또는 JSON에서 컬럼 설명과 관계 후보를 불러와, 이 저장소의 원본과 대조할 검토 초안으로 저장합니다. 파일이 없다면 건너뛰어도 됩니다.'),el('p','① 제안 파일 선택 → ② 원본 컬럼과 제안 내용 대조 → ③ 사용할 항목을 수정·승인합니다. 불러오기만으로 승인되거나 질문에 사용되지 않습니다.','muted'),el('p','이 버튼은 모델을 호출하거나 외부 DB에 연결하지 않습니다. 일반 OWL·TTL 파일 업로드 기능도 아닙니다. 지금 의미 제안을 생성하려면 상단 확장 도구의 NVIDIA 기능 또는 의미 초안 생성을 사용하세요.','muted'));
 const pending=extensionPending();
 if(pending){
  const recovery=el('div',undefined,'callout');recovery.append(el('p','응답이 확정되지 않은 로컬 확장 요청이 있습니다. 새 가져오기와 승인을 멈추고 저장된 상태를 확인하세요.'));
  recovery.append(button('확장 요청 상태 확인',()=>task(async()=>{
   let request;try{request=JSON.parse(pending);}catch{throw Error('저장된 확장 요청 식별자를 읽지 못했습니다. 자동 재전송하지 않습니다.');}
   const status=await api({action:'progress',id:w.id,request_key:request.request_key});
   if(terminalStates.has(status.state)&&await openSavedOperation(w.id,status.id)){remember('operations-extension-'+w.id,null);render();focusOperation(status.id);}
   else if(status.state==='not_recorded'){
    $('notice').textContent='아직 접수 기록이 없습니다. 원래 키를 유지합니다. 늦게 도착하는 요청과 중복되지 않도록 새 키로 보내지 않습니다.';
    if(request.payload&&!recovery.querySelector('[data-extension-replay]')){const retry=button('동일한 원래 요청 다시 전송',()=>task(()=>extensionSend(request.payload,true)));retry.dataset.extensionReplay='true';retry.disabled=!mutable()||request.revision!==w.revision;recovery.append(retry);}
   }
   else{
    $('notice').textContent=operationProgressText({...status,kind:status.kind||request.payload?.action});
    if(status.state==='running'&&request.payload?.action==='local_reasoning'&&!recovery.querySelector('[data-extension-cancel]')){
     const cancel=button(status.cancel_requested?'중지 요청됨':'실행 중지 요청',()=>task(async()=>{const current=await api({action:'cancel',id:w.id,request_key:request.request_key});$('notice').textContent=operationProgressText({...current,kind:'local_reasoning'});cancel.disabled=Boolean(current.cancel_requested)||current.state!=='running';cancel.textContent=current.cancel_requested?'중지 요청됨':'실행 중지 요청';}));
     cancel.dataset.extensionCancel='true';cancel.disabled=Boolean(status.cancel_requested);recovery.append(cancel);
    }
   }
  })));
  box.append(recovery);
 }
 const file=input('','file');file.accept='.yaml,.yml,.json';
 const importButton=button('파일 가져와 검토',()=>task(async()=>{
  const selected=file.files[0];if(!selected||selected.size>1000000)throw Error('1,000,000바이트 이하의 YAML 또는 JSON 파일을 선택하세요.');
  const bytes=new Uint8Array(await selected.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
  await extensionSend({action:'extension_import',id:w.id,revision:w.revision,request_key:crypto.randomUUID(),raw_base64:btoa(binary)});
 }));
 file.disabled=!mutable()||hasPending();importButton.disabled=true;
 file.addEventListener('change',()=>{importButton.disabled=!mutable()||hasPending()||!file.files.length;});
 box.append(field('기본 내보내기 YAML / JSON · 최대 1,000,000바이트',file),importButton);
 box.append(el('p','지원 스키마: Auto-Ontology 1.3.0. 파일에 기록된 물리 카탈로그와 모델의 의미 제안은 구분해서 표시합니다. 생산자 신원은 인증하지 않습니다.','muted'));
 for(const op of w.operations.filter(o=>['extension_import','extension_review','extension_invocation_association'].includes(o.kind)&&!omit.has(o.id)))box.append(operationCard(op));
 appendHistoryMore(box);
 root.append(box);
}
function extensionResult(op){
 const card=el('article',undefined,'card extension-result');card.append(el('h3',op.kind==='extension_review'?'외부 제안의 사람 승인 기록':'외부 제안 원본'),badge(op.state),el('p',`요청 당시 자료 버전 ${op.revision}`,'muted'));
 card.append(detail('요청 식별 정보',{workspace_id:op.workspace||state.current.id,import_operation_id:op.kind==='extension_import'?op.id:undefined,operation_id:op.id,revision:op.revision,request_key:op.request_key}));
 if(op.error)card.append(operationError(op.error));
 if(op.kind==='extension_review'){
  if(op.result)card.append(el('p',`저장된 승인 버전 ${op.result.adopted_revision} · 원래 외부 제안은 변경하지 않았습니다.`),detail('승인한 필드와 출처',op.result));
  else if(!op.error)card.append(el('p','승인이 확정되지 않았습니다. 저장된 상태를 확인하세요.','callout'));
  return card;
 }
 const p=op.result;if(op.state!=='completed'||!p){if(!op.error)card.append(el('p','가져오기가 완료되지 않아 적용할 수 없습니다.','callout'));return card;}
 const stale=op.revision!==state.current.revision||p.base_workspace_digest!==state.current.digest;
 const blocked=stale||!mutable()||hasPending()||Boolean(p.unresolved_references.length);
 if(isDatabaseWorkspace())card.append(proposalComparison(op,blocked,()=>updateBatch()));
 card.append(el('p',stale?'현재 버전과 다른 제안입니다. 읽기만 가능합니다. 남은 후보를 승인하려면 현재 버전에서 파일을 다시 가져오세요.':'구문을 읽은 미승인 제안입니다. 파일의 주장과 사람이 승인한 연결은 별개입니다.',stale?'callout':'muted'));
 if(p.unresolved_references.length)card.append(el('p',`해결되지 않은 외부 참조 ${p.unresolved_references.length}개. 참조를 수정한 파일을 다시 가져오기 전에는 승인할 수 없습니다.`,'callout'));
 card.append(kv({'지원 스키마 대상':`${p.upstream.version} · ${p.upstream.commit}`,'생산자 인증':'인증되지 않음','변환 결과':p.validation_state==='parsed'?'구문 읽음 · 의미 검토 필요':'지원하지 않는 내용 또는 참조 검토 필요'}));
 const physical=p.concepts.filter(c=>['database','schema','table'].includes(c.kind)),semantic=p.concepts.filter(c=>['term','concept'].includes(c.kind));
 card.append(el('p',`물리 카탈로그 ${physical.length}개 · 물리 열 ${p.fields.filter(c=>c.kind==='column').length}개 · 의미 용어/개념 ${semantic.length}개 · 지원하지 않는 항목 ${p.unsupported.length}개`,'muted'));
 const k=extensionKey(op),view=extensionUI.views.get(k)||{kind:'semantic',page:0,query:''};extensionUI.views.set(k,view);
 const choice=select([['semantic','의미 제안'],['physical','물리 카탈로그'],['relations','관계 후보'],['unsupported','지원하지 않는 내용']],view.kind),query=input(view.query),list=el('div');query.type='search';
 const controls=el('div',undefined,'review-grid');controls.append(field('확인할 내용',choice),field('이름 / 식별자 검색',query));const advanced=el('details',undefined,'proposal-advanced');advanced.append(el('summary','전체 개념·관계 후보·미지원 원문 보기'),controls,list);if(isDatabaseWorkspace())card.append(advanced);else card.append(controls,list);
 function draw(){
  list.replaceChildren();let all=view.kind==='physical'?[...physical,...p.fields.filter(c=>c.kind==='column')]:view.kind==='semantic'?[...semantic,...p.fields.filter(c=>c.kind!=='column')]:view.kind==='relations'?p.relations:p.unsupported;
  const total=all.length;all=all.filter(c=>JSON.stringify(c).toLocaleLowerCase().includes(view.query.toLocaleLowerCase()));const max=Math.max(0,Math.ceil(all.length/20)-1);view.page=Math.min(view.page,max);
  list.append(el('p',`전체 ${total}개 · 검색 결과 ${all.length}개 · ${view.page+1}/${max+1}페이지 (페이지당 최대 20개)`,'muted'));
  if(!all.length)list.append(el('p',view.kind==='semantic'?'이 범위에 의미 제안이 없습니다. 물리 카탈로그와 지원하지 않는 내용은 별도 목록에서 확인하세요.':'이 범위에 표시할 항목이 없습니다. 검증 통과를 뜻하지 않습니다.','muted'));
  for(const c of all.slice(view.page*20,view.page*20+20)){
   const item=el('details',undefined,'extension-candidate');item.append(el('summary',`${c.source_payload?.name||c.source_id||c.path||c.id} · ${c.kind||c.reason} · ${extensionStaged(op).has(c.id)?'승인 준비 목록에 담음':'미승인 원본'}`));
   let loaded=false;item.addEventListener('toggle',()=>{if(item.open&&!loaded){loaded=true;item.append(el('p',c.source_path||c.path,'muted'),detail('외부 파일의 원래 주장',c.source_payload??c.value??c));
    if(isDatabaseWorkspace()&&['foreign_keys','semantic_fks','joins'].includes(c.kind))item.append(externalRelationEditor(op,c,stale||!mutable()));
    else if(['column','column_attribute'].includes(c.kind))item.append(extensionEditor(op,c,blocked,updateBatch));
    else item.append(el('p','이 항목은 읽기 전용입니다. 새 스키마나 실행 규칙으로 승인하지 않습니다.','muted'));
   }});list.append(item);
  }
  const pager=el('div',undefined,'actions'),prev=button('이전 후보',()=>{view.page--;draw();}),next=button('다음 후보',()=>{view.page++;draw();});prev.disabled=view.page===0;next.disabled=view.page===max;pager.append(prev,next);list.append(pager);
 }
 choice.addEventListener('change',()=>{view.kind=choice.value;view.page=0;draw();});query.addEventListener('input',()=>{view.query=query.value;view.page=0;draw();});
 const batch=el('div',undefined,'extension-batch');card.append(batch);
 function updateBatch(){
  const decisions=[...extensionStaged(op).values()];card.querySelector('[data-testid=proposal-comparison]')?.refreshSelection?.();batch.replaceChildren(el('p',`승인 준비 ${decisions.length}개 · 아직 저장하지 않았습니다.`));
  if(decisions.length)batch.append(table(['원본 열','검토한 의미','대상'],decisions.map(d=>{const e=state.current.draft.entries.find(e=>e.id===d.entry_id);return [`${e?.source.file} · ${e?.source.column}`,d.interpretation,d.target];})));
  const approve=button('선택한 필드 승인 미리보기',()=>extensionApprovalPreview(op,decisions),'primary');approve.disabled=blocked||!decisions.length;
  const clear=button('승인 준비 목록 비우기',()=>{extensionStaged(op).clear();state.edited=extensionDirty();updateBatch();});clear.disabled=!decisions.length;batch.append(approve,clear);
 }
 draw();updateBatch();
 card.append(detail(`지원하지 않는 내용 ${p.unsupported.length}개 · 실행하지 않음`,p.unsupported),detail(`해결되지 않은 참조 ${p.unresolved_references.length}개`,p.unresolved_references),detail('원본 해시와 가져오기 기준',{raw_sha256:p.raw_sha256,base_workspace_digest:p.base_workspace_digest,source_hashes:p.source_hashes,producer_authenticated:p.producer_authenticated}),detail('전체 원본 문서 · 읽기 전용',p.raw_document));return card;
}

function proposalComparison(op,blocked,onChange=()=>{}){
 const p=op.result,box=el('section',undefined,'proposal-comparison');box.dataset.testid='proposal-comparison';
 const observed=state.current.latest_extension?.operation_id===op.id&&state.current.latest_extension.origin==='observed_native_semantic_generation';
 box.append(el('h3','원본 값 → 제안 → 검토할 의미 → 승인 후 사용'),el('p',observed?'실제 LLM 실행에서 가져온 초안입니다. 열 이름이 정확히 일치하는 후보를 나란히 놓았으며, 이 대응 자체가 사람의 승인은 아닙니다.':'외부 파일의 설명을 원본 옆에 표시합니다. 파일만으로 LLM 생성 여부나 설명의 정확성을 인증하지 않습니다.','muted'));
 const sources=state.current.draft.sources.filter(s=>s.kind==='database_table'),sourceChoice=select([['','모든 표'],...sources.map(s=>[s.name,s.name])],''),filter=input('');filter.type='search';filter.setAttribute('aria-label','비교할 원본 열 검색');
 const controls=el('div',undefined,'review-grid');controls.append(field('비교할 표',sourceChoice),field('원본 열 검색',filter));box.append(controls);
 const korean=state.current.proposal_korean?.[op.id]||{},list=el('div'),actions=el('div',undefined,'actions'),count=el('p',undefined,'muted');box.append(count,list,actions);let page=0;
 function draw(){
  list.replaceChildren();actions.replaceChildren();let rows=state.current.draft.entries.filter(e=>e.kind==='mapping'&&(!sourceChoice.value||e.source.file===sourceChoice.value)&&(`${e.source.file}.${e.source.column}`).toLocaleLowerCase().includes(filter.value.toLocaleLowerCase()));
  const max=Math.max(0,Math.ceil(rows.length/20)-1);page=Math.min(page,max);count.textContent=`원본 열 ${rows.length}개 · ${page+1}/${max+1}페이지 · 필요한 열만 선택하세요. 편집과 선택만으로는 서버에 승인되지 않습니다.`;
  const wrap=el('div',undefined,'table-wrap proposal-table-wrap');wrap.tabIndex=0;wrap.setAttribute('aria-label','원본과 의미 제안 비교 표 · 가로 스크롤 가능');const t=el('table',undefined,'proposal-table'),head=el('thead'),header=el('tr');
  for(const label of ['선택·원본 열','원본 값 · 최대 3행','제안한 설명','수정할 의미 · 현재 승인','승인 후 사용 범위']){const th=el('th',label);th.scope='col';header.append(th);}head.append(header);const body=el('tbody');t.append(head,body);wrap.append(t);list.append(wrap);
  for(const entry of rows.slice(page*20,page*20+20)){
   const source=sources.find(s=>s.name===entry.source.file),columns=p.fields.filter(c=>c.kind==='column'&&c.source_payload.name===entry.source.column&&p.concepts.some(table=>table.kind==='table'&&table.id===c.parent_id&&table.source_payload.name===source?.name));
   const column=columns.length===1?columns[0]:null,attributes=column?p.fields.filter(c=>c.kind==='column_attribute'&&c.source_payload.column_id===column.source_id&&c.source_payload.description):[],ambiguous=columns.length>1||(!column?.source_payload.description&&attributes.length>1),candidate=ambiguous?null:(column?.source_payload.description?column:attributes[0]||column);
   const unsupported=candidate&&[candidate,column].some(c=>c&&p.unsupported.some(u=>u.path===c.source_path||u.path.startsWith(c.source_path+'.'))),disabled=blocked||!candidate||unsupported;
   const row=el('tr'),identity=el('td'),check=input('','checkbox'),name=`${entry.source.file}.${entry.source.column}`;check.setAttribute('aria-label',name+' 의미 검토 선택');check.disabled=disabled;identity.append(check,el('strong',name));row.append(identity);
   const samples=el('td');for(const sample of (source?.sample||[]).slice(0,3))samples.append(el('div',databaseValue(sample[entry.source.column])));row.append(samples);
   const proposal=el('td',candidate?.source_payload.description||(!candidate?'일치하는 설명 후보 없음':'설명 제안 없음'));if(ambiguous)proposal.append(el('p','후보가 중복되어 자동 연결하지 않았습니다. 아래 전체 후보에서 원본을 선택하세요.','muted'));if(candidate)proposal.append(detail('제안 위치·식별자',{candidate_id:candidate.id,source_path:candidate.source_path,raw_sha256:p.raw_sha256}));row.append(proposal);
   const editor=el('td'),meaning=el('textarea'),scope=select([['source_only','원본 열 조회에 사용'],...(state.current.mapping_targets||[]).filter(x=>x!=='source_only').map(x=>[x,x])],'source_only');meaning.rows=3;meaning.maxLength=4000;meaning.setAttribute('aria-label',name+' 검토할 의미');scope.setAttribute('aria-label',name+' 승인 후 사용 범위');
   const key=candidate?`${extensionKey(op)}:${candidate.id}`:null,saved=key&&(extensionUI.drafts.get(key)||extensionStaged(op).get(candidate.id));const translation=candidate&&korean[candidate.id];meaning.value=saved?.interpretation??translation?.meaning_ko??candidate?.source_payload.description??'';meaning.lang='ko';meaning.placeholder='이 열의 의미와 적용 범위를 한국어로 작성하세요.';scope.value=saved?.target||'source_only';meaning.disabled=scope.disabled=disabled;check.checked=Boolean(candidate&&extensionStaged(op).has(candidate.id));
   if(translation){editor.append(el('p','한국어 번역 초안 · 기존 승인을 자동 변경하지 않습니다.','muted'));if(entry.interpretation)editor.append(detail('현재 승인 해석 원문',entry.interpretation));}editor.append(el('p',`현재: ${labels[entry.status]||entry.status} · ${translation?.current_meaning_ko||entry.interpretation||'의미 미검토'}`,'muted'),meaning);row.append(editor);const usage=el('td');usage.append(scope,el('p','열의 의미를 저장합니다. 주문 변경 허가·재고 최신성 확인·조회 정의 생성은 하지 않습니다.','muted'));row.append(usage);
   const value=()=>({candidate_id:candidate.id,entry_id:entry.id,target:scope.value,interpretation:meaning.value,note:'원본 값과 외부 제안을 비교해 검토',manual_binding:''});
   function edit(){if(!candidate)return;if(check.checked&&[...extensionStaged(op).values()].some(v=>v.entry_id===entry.id&&v.candidate_id!==candidate.id)){check.checked=false;$('notice').textContent='같은 원본 열에 다른 후보가 이미 선택되어 있습니다. 기존 준비 목록을 먼저 확인하세요.';return;}extensionUI.drafts.set(key,value());if(check.checked&&meaning.value.trim())extensionStaged(op).set(candidate.id,value());else extensionStaged(op).delete(candidate.id);changed();updateSelection();onChange();}
   check.addEventListener('change',()=>{if(check.checked&&!meaning.value.trim()){check.checked=false;$('notice').textContent='검토할 의미를 먼저 적어 주세요.';return;}edit();});meaning.addEventListener('input',edit);scope.addEventListener('change',edit);body.append(row);
  }
  const previous=button('이전 원본 열',()=>{page--;draw();}),next=button('다음 원본 열',()=>{page++;draw();});previous.disabled=page===0;next.disabled=page===max;actions.append(previous,next);
  const translate=button('표시된 열 설명을 한국어로 번역 · 유료',()=>task(async()=>{if(state.edited||extensionVolatile()){throw Error('작성 중인 입력을 먼저 저장하거나 정리한 뒤 번역하세요.');}const entries=rows.slice(page*20,page*20+20),ids=p.fields.filter(c=>c.kind==='column'&&c.source_payload.description&&entries.some(e=>c.source_payload.name===e.source.column&&p.concepts.some(t=>t.kind==='table'&&t.id===c.parent_id&&t.source_payload.name===e.source.file))).map(c=>c.id);if(!ids.length)throw Error('번역할 물리 열 설명이 없습니다.');await extensionSend({action:'extension_localize',id:state.current.id,revision:state.current.revision,request_key:crypto.randomUUID(),operation_id:op.id,candidate_ids:ids});}));translate.dataset.testid='proposal-korean';translate.disabled=!mutable()||!state.current.proposal_translation_enabled;actions.append(translate);updateSelection();
 }
 const selected=el('p',undefined,'proposal-selection'),approve=button('선택한 필드 승인 미리보기',()=>extensionApprovalPreview(op,[...extensionStaged(op).values()]),'primary');approve.dataset.testid='comparison-approval-preview';
 function updateSelection(){const n=extensionStaged(op).size;selected.textContent=`승인 준비 ${n}개 · 아직 적용하지 않았습니다. 아래 미리보기에서 최종 승인하면 한 새 버전에 저장됩니다.`;approve.disabled=blocked||!n;}
 box.refreshSelection=updateSelection;sourceChoice.addEventListener('change',()=>{page=0;draw();});filter.addEventListener('input',()=>{page=0;draw();});box.append(selected,approve);draw();return box;
}
function externalRelationEditor(op,c,blocked){
 const key=reviewedKey()+':external-relation:'+op.id+':'+c.id;
 if(reviewedUI.forms.has(key))return reviewedUI.forms.get(key);
 const box=el('section',undefined,'extension-editor external-relation-editor');box.dataset.candidateId=c.id;
 const fields=reviewedFields(),options=[['','승인한 원본 열을 직접 선택'],...fields.map(e=>[e.id,reviewedLabel(e.id)])];
 const child=select(options,''),parent=select(options,''),id=input(''),meaning=el('textarea'),reason=el('textarea'),rejectReason=el('textarea');
 id.maxLength=80;meaning.maxLength=reason.maxLength=rejectReason.maxLength=4000;meaning.value=c.source_payload?.description||'';
 box.append(el('h4','외부 관계 후보의 로컬 검토'),el('p','생산자 인증은 없습니다. 외부 열 이름과 참조를 원본에 대조하고 승인한 양쪽 열을 직접 선택하세요. 서버가 저장 시 외부 참조와 실제 외래 키를 검사합니다. 가져온 SQL은 실행하지 않습니다.','callout'),kv({'가져오기 기록':op.id,'후보 식별자':c.id,'후보 종류':c.kind,'원본 파일 SHA256':op.result.raw_sha256,'현재 스냅샷 SHA256':state.current.draft.database.snapshot_sha256,'외부 경로 선택 제안':String(c.source_payload?.use_in_join_paths??'기록 없음')}),detail('가져오기 기준 · 인증되지 않은 원본 연결',{source_hashes:op.result.source_hashes,base_workspace_digest:op.result.base_workspace_digest,import_revision:op.revision,producer_authenticated:op.result.producer_authenticated}));
 if(c.kind==='joins')box.append(el('p','표 사이의 join 표현식은 실행 가능한 열 관계로 채택하지 않습니다. 이 후보는 읽기 또는 선택 제외만 가능합니다.','callout'));
 if(blocked)box.append(el('p','현재 편집 가능한 가져오기 기록이 아닙니다. 현재 버전에서 같은 파일을 다시 가져와 검토하세요.','callout'));
 if(!fields.length)box.append(el('p','먼저 사용할 원본 열을 승인한 뒤 외부 파일을 다시 가져오세요.','callout'));
 box.append(field('로컬 관계 식별 이름',id),field('자식 행의 승인 필드',child),field('부모 키의 승인 필드',parent),field('수정한 관계 의미 · 적용 범위',meaning),field('원본과의 연결 · 수정 이유',reason));
 const save=button('외부 후보에서 관계 제안 저장',()=>task(async()=>{if(!id.value.trim()||!child.value||!parent.value||!meaning.value.trim()||!reason.value.trim())throw Error('관계 이름, 양쪽 승인 필드, 의미와 수정 이유를 모두 입력하세요.');await reviewedSubmit('database_external_relation_propose',{operation_id:op.id,candidate_id:c.id,spec:{id:id.value,child_entry_id:child.value,parent_entry_id:parent.value,interpretation:meaning.value,join_policy:'left_many_to_one_preserve_root'},edit_reason:reason.value});}));
 submissionControl(save,blocked||!fields.length||c.kind==='joins');box.append(save,el('p','저장은 미승인 제안만 만듭니다. 저장된 정의를 별도로 검토하고 승인한 뒤 질의에서 선택하세요.','muted'));
 const rejection=el('details');rejection.append(el('summary','이 후보의 선택 제외 기록'),el('p','중복 후보 등을 이번 선택에서 제외합니다. 기존 승인 대기 제안과 승인된 관계는 취소하지 않으며, 관계가 거짓이라는 판정도 아닙니다. 기존 제안은 계속 승인할 수 있으며, 해석을 바꾸려면 새 제안을 저장하세요.','callout'),field('선택 제외 이유 · 중복이면 관련 후보 기록',rejectReason));
 const reject=button('후보 선택 제외 저장',()=>task(async()=>{if(!rejectReason.value.trim())throw Error('선택 제외 이유를 입력하세요.');await reviewedSubmit('database_external_relation_reject',{operation_id:op.id,candidate_id:c.id,reason:rejectReason.value});}));submissionControl(reject,blocked);rejection.append(reject);box.append(rejection);
 for(const n of [child,parent,id,meaning,reason,rejectReason]){n.disabled=blocked;n.addEventListener('input',()=>markReviewedDirty(key+(n===rejectReason?':rejection':':proposal')));n.addEventListener('change',()=>markReviewedDirty(key+(n===rejectReason?':rejection':':proposal')));}
 reviewedUI.forms.set(key,box);return box;
}
function extensionEditor(op,c,blocked,onStage){
 const related=c.kind==='column_attribute'?op.result.fields.find(f=>f.kind==='column'&&f.source_id===c.source_payload.column_id):c;
 const unsupported=[c,related].filter(Boolean).some(f=>op.result.unsupported.some(u=>u.path===f.source_path||u.path.startsWith(f.source_path+'.')));
 blocked=blocked||unsupported;
 const box=el('div',undefined,'extension-editor'),entries=state.current.draft.entries.filter(e=>e.kind==='mapping'),key=`${extensionKey(op)}:${c.id}`,saved=extensionUI.drafts.get(key)||extensionStaged(op).get(c.id);
 const source=select([['','원본 열 선택'],...entries.map(e=>[e.id,`${e.source.file} · ${e.source.column}`])],saved?.entry_id||'');
 const target=select([['source_only','원본 조회에만 사용'],...(state.current.mapping_targets||[]).filter(t=>t!=='source_only').map(t=>[t,t])],saved?.target||'source_only'),meaning=el('textarea'),note=el('textarea'),binding=el('textarea');
 meaning.value=saved?.interpretation??c.source_payload.description??'';note.value=saved?.note||'';binding.value=saved?.manual_binding||'';for(const n of [meaning,note,binding])n.maxLength=4000;
 if(unsupported)box.append(el('p','이 후보 또는 연결된 열에 지원하지 않는 필드가 있어 승인할 수 없습니다. 내용을 수정한 파일을 다시 가져오세요.','callout'));
 const evidence=el('div'),error=el('p',undefined,'callout');error.hidden=true;error.setAttribute('role','alert');
 const value=()=>({candidate_id:c.id,entry_id:source.value,target:target.value,interpretation:meaning.value,note:note.value,manual_binding:binding.value});
 const preview=()=>{evidence.replaceChildren();const e=entries.find(e=>e.id===source.value);if(!e)return;const s=state.current.draft.sources.find(s=>s.name===e.source.file);const rows=s.kind==='database_table'?s.sample:s.rows,total=s.kind==='database_table'?s.row_count:s.rows.length;evidence.append(el('p',`실제 저장한 원본 예시 · ${Math.min(3,rows.length)}행 샘플 / 전체 ${total}행`,'muted'),table(['원본 값'],rows.slice(0,3).map(r=>[databaseValue(r[e.source.column])])),el('p',`현재 결정: ${labels[e.status]} · ${e.target||'미정'} · ${e.interpretation||'해석 없음'}`,'muted'),detail('선택한 원본 해시',s.sha256));};
 source.addEventListener('change',preview);preview();
 box.append(el('p','외부 설명을 원본 값과 대조한 뒤 수정하세요. 이름이 다른 원본에 연결하려면 그 이유를 적어야 합니다.','muted'),field('연결할 실제 원본 열',source),evidence,field('조회 대상 필드',target),field('사람이 검토한 의미 · 필수',meaning),field('이름이 다른 원본을 선택한 이유',binding),field('검토 메모',note),error);
 const stage=button('이 필드를 승인 준비 목록에 담기',()=>{
  error.hidden=true;const d=value();if(!d.entry_id||!d.interpretation.trim()){error.textContent='원본 열을 선택하고 검토한 의미를 적어 주세요.';error.hidden=false;return;}
  if([...extensionStaged(op).values()].some(v=>v.entry_id===d.entry_id&&v.candidate_id!==c.id)){error.textContent='같은 원본 열이 이미 승인 준비 목록에 있습니다. 목록을 비운 뒤 연결을 다시 선택하세요.';error.hidden=false;return;}
  extensionStaged(op).set(c.id,d);extensionUI.drafts.delete(key);changed();onStage();$('notice').textContent='승인 준비 목록에 담았습니다. 아래에서 선택한 필드를 함께 확인하고 승인하세요.';
 });stage.disabled=blocked;
 for(const n of [source,target,meaning,note,binding]){n.disabled=blocked;n.addEventListener('input',()=>{extensionUI.drafts.set(key,value());extensionStaged(op).delete(c.id);changed();onStage();});}
 box.append(stage);return box;
}
function extensionApprovalPreview(op,decisions){
 if(state.edits.size||state.policies.size){$('error').hidden=false;$('error').textContent='기존 필드·정책의 미저장 검토를 먼저 저장하거나 정리하세요. 확장 승인은 새 버전을 만듭니다.';return;}
 const dialog=el('dialog',undefined,'approval-preview');dialog.setAttribute('aria-labelledby','extension-approval-title');const title=el('h2','선택한 외부 필드 연결 승인');title.id='extension-approval-title';
 const entries=state.current.draft.entries;dialog.append(title,el('p','아래 연결과 해석을 사람이 승인합니다. 기존 결정을 바꾸며 모든 선택을 한 새 버전에 저장합니다. 외부 원본은 변경하지 않습니다. 나머지 후보는 새 버전에서 다시 가져와야 합니다.','callout'));
 for(const d of decisions){const e=entries.find(e=>e.id===d.entry_id),comparison=el('section',undefined,'extension-approval-comparison');comparison.append(el('h3',`${e.source.file} · ${e.source.column}`),kv({'현재 결정':`${labels[e.status]} · ${e.target}`,'현재 의미':e.interpretation||'기록 없음','승인할 대상':d.target,'승인할 의미':d.interpretation,'실행 범위':d.target==='source_only'?'승인한 원본 열의 정확한 값 조회':'선택한 대상의 기존 실행 범위','외부 제안 실행 기록':op.id}));dialog.append(comparison);}
 dialog.append(button('취소',()=>dialog.close()),button(`${decisions.length}개 필드 한 번에 승인`,()=>{dialog.close();task(()=>extensionSend({action:'extension_review_batch',id:state.current.id,revision:state.current.revision,request_key:crypto.randomUUID(),operation_id:op.id,decisions}));},'primary'));
 const opener=document.activeElement;dialog.addEventListener('close',()=>{dialog.remove();opener?.focus();});document.body.append(dialog);dialog.showModal();
}

function modelProposalPanel(root){
 const info=state.current.model_proposals||{};const box=el('article',undefined,'card');box.append(el('h3','의미 초안 생성'),el('p',info.enabled?`선택 가능한 모델: ${info.model} · 기존 예산 원장을 공유합니다.`:'현재는 로컬 사전·규칙으로 제안합니다. 외부 모델 생성은 서버에서 활성화하지 않았습니다.','muted'));
 const pending=recalled('operations-generation-'+state.current.id);
 if(pending)box.append(el('p','화면 위의 요청 복구에서 서버 상태를 먼저 확인하세요.','callout'));
 const run=button('모델로 새 초안 제안',()=>{if(canLeave()&&window.confirm('이 자료실의 원문 전체를 설정된 외부 모델에 보내고 공유 예산에서 유료 호출 1회를 시도합니다. 결과는 따로 저장되며 기존 승인을 바로 바꾸지 않습니다. 진행할까요?'))generateSuggestions(crypto.randomUUID());});submissionControl(run,!mutable()||!info.enabled||state.current.draft.adapter!=='commerce-csv-1');box.append(run);root.append(box);
 for(const op of state.current.operations.filter(o=>o.kind==='model_suggestions'))root.append(operationCard(op));
 appendHistoryMore(root);
}
function focusOperation(id){
 const card=[...document.querySelectorAll('[data-operation-id]')].find(node=>node.dataset.operationId===id);
 const target=card||document.querySelector('.run-history>summary');
 if(target){for(let parent=target.parentElement;parent;parent=parent.parentElement)if(parent.tagName==='DETAILS'){parent.open=true;if(parent.dataset.reviewedPanel)reviewedUI.questionPanels.set(reviewedKey()+':'+parent.dataset.reviewedPanel,true);if(parent.classList.contains('reasoning-panel'))extensionUI.reasoningOpen.set(state.current.id,true);if(parent.dataset.savedOperationId)extensionUI.reasoningSavedOpen.set(state.current.id+':'+parent.dataset.savedOperationId,true);}target.focus();target.scrollIntoView({block:'nearest'});}
}
function setHistoryOpen(open){state.historyOpen??=new Map();state.historyOpen.set(state.current.id,open);}
function appendHistoryMore(root){
 if(state.current.operations_next)root.append(button('이전 실행 기록 더 보기',()=>task(async()=>{
  const page=await api({action:'history',id:state.current.id,before:state.current.operations_next});
  const seen=new Set(state.current.operations.map(operation=>operation.id));
  const added=page.operations.filter(operation=>!seen.has(operation.id));
  state.current.operations.push(...added);state.current.operations_next=page.operations_next;state.current.operation_count=page.operation_count;
  if(state.tab==='questions')setHistoryOpen(true);
  render();
  const first=added.find(operation=>state.tab!=='questions'||operation.kind!=='model_suggestions');
  focusOperation(first?.id);
 })));
}
function proposalResult(op){const card=el('article',undefined,'card');card.append(el('h3','모델 의미 초안'),badge(op.state),el('p',`요청 당시 버전 ${op.revision}`,'muted'));
 if(op.state==='interrupted')card.append(el('p','서버 중단 전에 생성이 완료됐는지 확인할 수 없습니다. 기존 자료와 승인은 유지됩니다. 기록 확인은 같은 요청을 다시 호출하지 않습니다. 새로 생성하기 전에는 외부 호출 원장에서 처리·비용 여부를 확인하세요.','callout'));
 if(op.error)card.append(operationError(op.error));
 if(op.result?.draft){card.append(el('p',op.state==='completed'?'자동 승인되지 않은 제안입니다. 적용하면 새 버전으로 저장되고 모든 항목을 다시 검토합니다. 이전 승인은 과거 버전에 남습니다.':'생성이 완료되지 않아 기존 자료와 승인은 유지됩니다. 남은 제안은 확인용이며 적용할 수 없습니다.','callout'));
 const preview=el('details');preview.append(el('summary','제안 내용 확인'),table(['원문 위치','제안','이유'],op.result.draft.entries.filter(e=>e.kind!=='relation').map(e=>[`${e.source.file} · ${e.source.column||e.source.paragraph}`,e.target||'미정',e.reason])));for(const e of op.result.draft.entries.filter(e=>e.kind!=='relation'&&e.extraction?.source_evidence))preview.append(el('h4',e.source.file+' · '+(e.source.column||e.source.paragraph)),proposalEvidence(e,op.result.draft));for(const relation of op.result.draft.entries.filter(e=>e.kind==='relation')){
  const block=el('section',undefined,'card');
  block.append(el('h4',`${relation.source.file} · ${relation.source.column} → ${relation.target.file} · ${relation.target.column}`),badge(relation.status),el('p',relationOrigin(relation,false),'callout'),el('p',relation.reason,'source-quote'));
  const questions=relation.extraction?.questions||[];
  if(questions.length){block.append(el('h4','확인할 질문'));const list=el('ul');questions.forEach(q=>list.append(el('li',q)));block.append(list);}
  if(relation.extraction?.source_evidence)block.append(proposalEvidence(relation,op.result.draft));
  preview.append(block);
 }
 card.append(preview);
 const adopt=button('이 초안을 새 버전으로 적용',()=>{if(canLeave()&&window.confirm('현재 승인을 새 초안에 승계하지 않고 모두 다시 검토합니다. 새 버전으로 적용할까요?'))task(async()=>show(await api({action:'adopt_suggestions',id:state.current.id,revision:state.current.revision,operation_id:op.id})));});adopt.disabled=op.state!=='completed'||!mutable()||op.revision!==state.current.revision||op.result.base_digest!==state.current.digest;card.append(adopt);
 }else if(!op.error)card.append(el('p','처리 결과가 확정되지 않았습니다. 같은 요청으로 확인하세요.','muted'));
 card.append(button('생성 요청 기록 확인',()=>task(()=>openSavedOperation(state.current.id,op.id))));return card;}
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
  state.edited=extensionVolatile();render();$('notice').textContent='일반 검토 입력을 서버에 임시 저장했습니다. 외부 제안의 편집·승인 준비 목록은 임시 저장에 포함되지 않습니다.';
 }));save.disabled=!mutable();box.append(save);
 if(saved){box.append(el('p',`임시 저장: 자료 버전 ${saved.revision} · ${new Date(saved.updated).toLocaleString('ko-KR')}`,'muted'));
  const restore=button('임시 저장한 입력 복원',()=>{
   if(!canLeave())return;
   const latest=state.current.review_buffer;if(!latest||latest.revision!==state.current.revision){$('notice').textContent='자료 버전이 바뀌어 복원할 수 없습니다.';return;}
   state.edits=new Map(latest.content.entries.map(e=>[e.entry_id,e]));state.policies=new Map(latest.content.policies.map(e=>[e.target,e]));state.edited=extensionVolatile();render();
  });restore.disabled=!mutable()||saved.revision!==state.current.revision;box.append(restore);
  if(saved.revision!==state.current.revision)box.append(el('p','다른 자료 버전에서 작성한 입력입니다. 자동 적용할 수 없습니다. 아래 기록을 비교해 다시 검토하세요.','callout'));
  box.append(detail('보관한 입력 확인',saved));
 }
 root.append(box);
}
function policyAgreementPanel(root){
 const names={unreviewed:'대조 전',agrees:'일치 확인',discrepant:'불일치',unresolved:'확인 필요',stale:'자료 변경 · 재검토 필요'};
 const box=el('article',undefined,'card');box.dataset.preparationTarget='policy_agreement';box.append(el('h2','정책 문서와 표 대조'),el('p','문서의 조건과 표의 값·적용 대상을 비교하세요. 일치 확인은 사용자의 판단이며 자동 검증이 아닙니다. 불일치는 원본 자료나 필드 연결을 수정한 뒤 다시 확인해야 합니다.','callout'));
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
 const card=el('details',undefined,'card');card.dataset.preparationTarget='manual_relation';card.append(el('summary','관계 직접 추가'),el('p','자동 제안에 없는 연결을 두 파일의 열에서 선택하세요. 추가한 뒤 의미와 원본 값을 검토해야 하며, 자동 승인되거나 조회되지 않습니다.','muted'));
 const options=tables.flatMap(s=>s.headers.map(column=>[JSON.stringify({file:s.name,column}),`${s.name} · ${column}`]));
 const left=select(options,options[0][0]),right=select(options,options.find(([v])=>JSON.parse(v).file!==tables[0].name)[0]),reason=el('textarea');reason.maxLength=4000;
 card.append(field('기준 파일과 열',left),field('연결할 파일과 열',right),field('연결을 제안하는 이유',reason));
 const add=button('검토 대기로 추가',()=>task(async()=>{const edits=new Map(state.edits),policies=state.policies;const row=await api({action:'add_relation',id:state.current.id,revision:state.current.revision,source:JSON.parse(left.value),target:JSON.parse(right.value),reason:reason.value});await show(row,edits,policies);if(edits.size||policies.size)changed();}));
 for(const control of [left,right,reason,add])control.disabled=!mutable();card.append(add);root.append(card);
}
function reviewInventoryRows(){
 const d=state.current.draft;
 return d.entries.map(original=>{const entry={...original,...state.edits.get(original.id)},source=d.sources.find(s=>s.name===entry.source.file),rows=source?.rows||source?.sample||[];
  const samples=entry.kind==='policy'?[entry.source.text||'']:rows.slice(0,3).map(row=>row[entry.source.column]===null?'(NULL)':String(row[entry.source.column]??''));
  const target=entry.target&&typeof entry.target==='object'?`${entry.target.file} · ${entry.target.column}`:entry.target==='source_only'?'원본 값 조회 (표준 연결 없음)':entry.target||'미지정';
  return {id:entry.id,kind:entry.kind,sourceLabel:entry.source.file,column:entry.source.column||(entry.kind==='policy'?`문단 ${entry.source.paragraph}`:'연결 후보'),samples,meaning:entry.interpretation||'',target,status:original.status,unsaved:state.edits.has(entry.id)};
 });
}
function databaseDecisionEditor(original){
 const entry={...original,...state.edits.get(original.id)},source=state.current.draft.sources.find(s=>s.name===entry.source.file),card=el('div',undefined,'entry');card.dataset.reviewId=entry.id;
 const status=select(['pending','approved','excluded','insufficient'].map(k=>[k,labels[k]]),entry.status),meaning=el('textarea'),note=el('textarea');status.setAttribute('aria-label','검토 상태');meaning.value=entry.interpretation;note.value=entry.note;meaning.maxLength=note.maxLength=4000;
 card.append(el('p','이 승인은 원본 열의 의미와 조회 범위를 기록합니다. 새 계산식이나 업무 규칙을 만들지 않습니다.','muted'),table(['원본 예시 · 전체 자료 아님'],source.sample.slice(0,8).map(row=>[databaseValue(row[entry.source.column])])),field('검토 상태',status),field('이 열의 업무 의미 · 승인 시 필수',meaning),field('메모 · 제외 시 이유 필수',note));
 const value=()=>({entry_id:entry.id,status:status.value,target:'source_only',interpretation:meaning.value,note:note.value});for(const control of [status,meaning,note]){control.disabled=!mutable();control.addEventListener('input',()=>{state.edits.set(entry.id,value());changed();});}
 const save=button('이 필드의 검토 결정 저장',()=>task(()=>saveDecisions([value()])));save.disabled=!mutable();card.append(save);const annotations=(state.current.draft.extension_reviews||[]).filter(r=>r.entry_id===entry.id);if(annotations.length)card.append(detail('다른 도구의 제안에서 이어진 검토 이력',annotations));return {card,value};
}
function appendReviewInventory(root){
 root.append(el('p','자료 구조와 표본은 승인 전에도 탐색할 수 있습니다. 원본 조회에 필요한 열부터 검토하세요. 모든 항목을 한꺼번에 승인할 필요는 없습니다.','callout'));
 const intro=heading(root,'검토·승인','① 예시 값을 확인하고 ② 항목의 의미를 검토·수정한 뒤 ③ 승인할 필드를 선택해 저장하세요.');intro.querySelector('h2').dataset.preparationTarget='review_overview';
 root.append(el('p','필드는 열의 의미, 정책은 문서의 적용 조건, 관계는 표 사이의 연결을 뜻합니다. 승인되지 않은 제안은 초안으로 남습니다. 집계는 저장된 승인 상태입니다. 미저장 수정은 별도로 표시하며, 저장한 결정은 새 버전으로 보존합니다.','review-intro'));
 const inspector=el('section',undefined,'review-inspector');inspector.hidden=true;inspector.setAttribute('aria-label','선택한 항목 검토');
 const editors=new Map();let inventory;
 const open=id=>{if(state.busy)return;const original=state.current.draft.entries.find(e=>e.id===id);if(!original)return;
  const editor=editors.get(id)||(isDatabaseWorkspace()?databaseDecisionEditor(original):decisionEditor(original));editors.set(id,editor);inspector.replaceChildren();const header=el('div',undefined,'section-head'),title=el('h3',`${original.source.file} · ${original.source.column||'문단 '+original.source.paragraph}`);title.tabIndex=-1;header.append(title,button('목록으로 돌아가기',()=>{inspector.hidden=true;inventory.element.querySelector(`[data-review-id="${CSS.escape(id)}"] button`)?.focus();}));inspector.append(header,el('p','원본 예시와 제안된 의미를 대조하세요. 상태와 해석을 바꾼 뒤 아래 저장 버튼으로 확정합니다.','muted'),editor.card);inspector.hidden=false;
  if(!editor.inventoryListener){editor.card.addEventListener('input',()=>inventory.update({entries:reviewInventoryRows()}));editor.card.addEventListener('change',()=>inventory.update({entries:reviewInventoryRows()}));editor.inventoryListener=true;}
  title.focus({preventScroll:true});inspector.scrollIntoView({block:'start'});
 };
 inventory=ReviewInventory.create({entries:reviewInventoryRows(),mutable:()=>mutable(),allowBulk:true,kindLabels:{mapping:'컬럼',policy:'문서·정책',relation:'표 연결'},onOpen:open,onApprove:ids=>{
  if(state.busy)return;const decisions=ids.map(id=>{const entry=state.current.draft.entries.find(e=>e.id===id);const editor=editors.get(id);return {...(editor?editor.value():{entry_id:id,status:entry.status,target:entry.target,note:entry.note,interpretation:entry.interpretation,...state.edits.get(id)}),status:'approved'};});previewDecisions(decisions);
 }});
 root.append(inventory.element,inspector);return inventory;
}

function renderReview(root){
 appendReviewInventory(root);
 const tools=el('details',undefined,'review-secondary preparation-tools'),workspaceId=state.current.id;state.preparationToolsOpen??=new Map();tools.open=state.preparationToolsOpen.get(workspaceId)||false;tools.addEventListener('toggle',()=>{if(tools.isConnected)state.preparationToolsOpen.set(workspaceId,tools.open);});tools.append(el('summary','의미 초안 생성·관계 추가·정책 설정'),el('p','직접 검토할 항목이 없거나 의미 제안을 다시 만들 때 사용하세요. 위 목록의 승인을 대신하지 않습니다.','muted'));modelProposalPanel(tools);manualRelationPanel(tools);policyAgreementPanel(tools);reviewBufferPanel(tools);policyResolutionPanel(tools);root.append(tools);extensionPanel(root);const reasoning=el('details',undefined,'review-secondary');reasoning.append(el('summary','RDF 규칙으로 분류 확인 · 선택 기능'));reasoningPanel(reasoning);root.append(reasoning);
}
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
  if(source)box.append(el('p','원본의 첫 3개 레코드 · 전체 값 검증은 아닙니다.','muted'),table(['원본 위치','원본 값'],(source.rows||source.sample||[]).slice(0,3).map((r,i)=>[source.locations?.[i]?source.locations[i].line_start+'–'+source.locations[i].line_end:'표본 '+(i+1),databaseValue(r[entry.source.column])])));
  if(entry.extraction?.source_evidence)box.append(proposalEvidence(entry));
  modal.append(box);
 }
 const close=button('돌아가기',()=>modal.close());
 const apply=button('선택한 내용 승인',()=>{modal.close();task(()=>saveDecisions(decisions));},'primary');apply.disabled=invalid||!mutable();
 modal.append(close,document.createTextNode(' '),apply);
 modal.addEventListener('close',()=>modal.remove());document.body.append(modal);modal.showModal();
}
function savedCases(){if(Array.isArray(state.current.cases))return state.current.cases;const entries=state.current.draft.entries.filter(e=>e.kind==='mapping'&&e.status==='approved');const id=entries.find(e=>e.target==='cases.id'),question=entries.find(e=>e.target==='cases.question'),label=entries.find(e=>e.target==='cases.label');if(!id||!question||id.source.file!==question.source.file)return [];const source=state.current.draft.sources.find(s=>s.name===id.source.file);return source.rows.map(r=>({id:r[id.source.column],question:r[question.source.column],label:label&&label.source.file===source.name?r[label.source.column]:''}));}
function relationLookupForm(){const card=el('article',undefined,'card');card.dataset.preparationTarget='relation_rows';card.append(el('h3','두 CSV의 같은 값 대조'),el('p','직접 선택한 관계의 두 열에서 같은 문자열을 찾습니다. 중복 행을 모두 표시하며 같은 업무 객체인지, 정책이 적용되는지는 판단하지 않습니다.','muted'));const catalog=state.current.relation_catalog||[];if(!catalog.length){card.append(el('p','설명을 적고 승인한 관계와 양쪽 열의 승인이 필요합니다. 데이터 정리에서 확인하세요.','muted'));return card;}const choice=select(catalog.map(r=>[r.relation_id,`${r.source.file} · ${r.source.column} ↔ ${r.target.file} · ${r.target.column}`]),catalog[0].relation_id);choice.setAttribute('aria-label','대조할 관계');const value=input();value.maxLength=2000;value.setAttribute('aria-label','양쪽 열에서 찾을 값');const run=button('두 CSV 대조 실행',()=>{if(!value.value.trim()){value.setCustomValidity('공백이 아닌 값을 입력하세요.');value.reportValidity();return;}execute(null,crypto.randomUUID(),state.current.revision,null,{relation_id:choice.value,value:value.value});});value.addEventListener('input',()=>value.setCustomValidity(''));submissionControl(run,!mutable());card.append(field('대조할 관계',choice),field('양쪽 열에서 찾을 값',value),run);return card;}
function relationResult(result){const box=el('div');box.append(el('p','선택한 두 열의 정확한 문자열 대조입니다. 같은 업무 객체라는 뜻은 아니며 정책·제약·추론 검사는 수행하지 않았습니다.','callout'),el('p',`찾은 값: ${result.value}`));for(const side of ['source','target']){const data=result.sides[side];box.append(el('h4',`${data.scope.file} · ${data.scope.column} · ${data.records.length}행`));if(!data.records.length)box.append(el('p','선택한 파일의 이 열에서는 일치하는 행을 찾지 못했습니다. 다른 자료에도 없다는 뜻은 아닙니다.','callout'));for(const row of data.records)box.append(table(['원본 열','값'],Object.entries(row.values)),el('p',`${row.source.file} · CSV 레코드 ${row.record} · 원문 ${row.source.line_start}–${row.source.line_end}행`,'muted'));}box.append(detail('검토한 관계 설명 · 원본 출처',result));return box;}
function documentLookupForm(){const card=el('article',undefined,'card');card.dataset.preparationTarget='source_document';card.append(el('h3','승인한 문단 직접 읽기'),el('p','모델 호출 없이 원문을 확인하고 조회 기록을 저장합니다. 정책 적용 여부는 판단하지 않습니다.','muted'));const catalog=state.current.document_catalog||[];if(!catalog.length){card.append(el('p','데이터 정리에서 승인한 문단이 없습니다. 전체 원문은 자료실에서 확인할 수 있습니다.','muted'));return card;}const choice=select(catalog.map(e=>[e.entry_id,`${e.file} · 문단 ${e.paragraph} · ${e.preview.slice(0,60)}`]),catalog[0].entry_id);choice.setAttribute('aria-label','확인할 승인 문단');const run=button('선택한 문단 조회',()=>execute(null,crypto.randomUUID(),state.current.revision,null,{entry_id:choice.value}));submissionControl(run,!mutable());card.append(field('확인할 승인 문단',choice),run);return card;}
function rowLookupForm(){
 const card=el('article',undefined,'card');card.dataset.preparationTarget='source_rows';card.append(el('h3','원본 열로 행 찾기'),el('p','주문번호가 여러 행에 반복되어도 모두 표시합니다. 승인한 열만 사용하며 합계나 정책 판단은 하지 않습니다.','muted'));
 const choices=state.current.row_lookup_catalog||[];
 if(!choices.length){card.append(el('p','조회할 열을 데이터 정리에서 먼저 검토하고 승인하세요.','empty'));return card;}
 const column=select(choices.map(c=>[c.entry_id,`${c.file} · ${c.column}`]),choices[0].entry_id),value=input('');value.maxLength=2000;
 const run=button('일치하는 원본 행 조회',()=>execute(null,crypto.randomUUID(),state.current.revision,null,{entry_id:column.value,value:value.value}),'primary');submissionControl(run,!mutable());
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
 const run=button('원본 기록 조회',()=>execute(null,crypto.randomUUID(),state.current.revision,null,{table:tableSelect.value,identifier:identifier.value}),'primary');submissionControl(run,!mutable());
 card.append(field('조회할 자료',tableSelect),field('조회할 식별자',identifier),hint,run);return card;
}
function proposalForm(){
 const card=el('article',undefined,'card');card.dataset.preparationTarget='replacement_proposal';card.append(el('h3','주문 항목 변경안 검토'),el('p','질문 파일 없이 변경안을 지정합니다. 승인 자료로 정해진 조회·계산·검토를 실행하며 실제 주문은 변경하지 않습니다.','muted'));
 const options=target=>{const matches=state.current.draft.entries.filter(e=>e.kind==='mapping'&&e.status==='approved'&&e.target===target);if(matches.length!==1)return [];const ref=matches[0].source;const src=state.current.draft.sources.find(s=>s.name===ref.file);return src.rows.map(r=>[r[ref.column],r[ref.column]]);};
 const items=options('items.id'),skus=options('skus.id'),item=select(items,''),replacement=select(skus,'');
 item.setAttribute('aria-label','변경할 주문 항목');replacement.setAttribute('aria-label','대체 상품 옵션');
 card.append(field('변경할 주문 항목',item),field('대체 상품 옵션',replacement));
 const flags={};for(const [key,label] of [['retain_discount','기존 할인 유지 요청'],['free_shipping','무료배송 요청'],['split','부분 출고 요청'],['promise_arrival','요청 도착일 약속 검토']]){flags[key]=input('','checkbox');card.append(field(label,flags[key]));}
 const run=button('변경안 검토 실행',()=>{const proposal={item:item.value,replacement:replacement.value};for(const [k,v] of Object.entries(flags))proposal[k]=v.checked;execute(null,crypto.randomUUID(),state.current.revision,proposal);},'primary');submissionControl(run,!mutable()||!items.length||!skus.length);card.append(run);
 if(!items.length||!skus.length)card.append(el('p','주문 항목 ID와 상품 옵션 ID 필드 연결을 먼저 승인하세요. 나머지 자료·정책의 실행 가능 여부는 서버에서 검사합니다.','callout'));
 return card;
}
function stashQuestionCursor(){
 const question=document.querySelector('.question-composer textarea'),owner=question?.closest('[data-composer-workspace]')?.dataset.composerWorkspace;
 if(!question||!owner)return;
 state.questionCursors??=new Map();state.questionCursors.set(owner,{value:question.value,start:question.selectionStart,end:question.selectionEnd,direction:question.selectionDirection,scroll:question.scrollTop});
}

function focusPreparationNode(node){
 if(!node)return;
 for(let ancestor=node;ancestor;ancestor=ancestor.parentElement)if(ancestor.tagName==='DETAILS')ancestor.open=true;
 const control=node.matches('button,input,select,textarea,summary')&&!node.disabled?node:node.querySelector('select:not(:disabled),input:not(:disabled),textarea:not(:disabled),button:not(:disabled),summary');
 const target=control||node;if(!control)target.tabIndex=-1;
 target.focus({preventScroll:true});target.scrollIntoView({block:'center'});
}
function preparationNavigation(label,tab,target,entryId=null,sourceName=null){
 const go=button(label,()=>{
  stashQuestionCursor();
  if(sourceName){state.sourceSelections??=new Map();state.sourceSelections.set(state.current.id,sourceName);}
  if(tab==='review'){state.preparationToolsOpen??=new Map();state.preparationToolsOpen.set(state.current.id,true);}
  if(tab==='questions'&&target!=='guide'){state.questionPanels??={};state.questionPanels[state.current.id+':direct']=true;}
  state.tab=tab;render();
  const destination=entryId?[...document.querySelectorAll('[data-review-id]')].find(n=>n.dataset.reviewId===entryId):[...document.querySelectorAll('[data-preparation-target]')].find(n=>n.dataset.preparationTarget===target);
  if(tab!=='questions')$('content').prepend(button('질문 준비로 돌아가기',openPreparationGuide,'preparation-return'));
  focusPreparationNode(destination||$('content').querySelector('h2'));
 });
 go.dataset.preparationAction=target;if(entryId)go.dataset.preparationEntry=entryId;return go;
}
function openPreparationGuide(){
 state.area='chat';
 if(state.tab!=='questions'){stashQuestionCursor();state.tab='questions';render();}
 focusPreparationNode($('task-preparation-guide'));
}
function preparationEntryLabel(entry){return entry.kind==='policy'?`${entry.source.file} · 문단 ${entry.source.paragraph}`:entry.kind==='relation'?`${entry.source.file} · ${entry.source.column} → ${entry.target?.file||'연결 대상 미정'} · ${entry.target?.column||''}`:`${entry.source.file} · ${entry.source.column}`;}
function preparationEntryLinks(entries,label='해당 항목 검토'){
 const list=el('ul',undefined,'preparation-entry-list');
 for(const entry of entries){const row=el('li');row.append(el('span',`${preparationEntryLabel(entry)} · ${labels[entry.status]||entry.status}`),preparationNavigation(label,'review','review_entry',entry.id));list.append(row);}
 return list;
}
function preparationEntryChoice(region,entries,task){
 if(!entries.length)return;
 const choice=select([['','실제 검토 항목 선택'],...entries.map(entry=>[entry.id,`${preparationEntryLabel(entry)} · ${labels[entry.status]||entry.status}`])],'');choice.setAttribute('aria-label','안내할 검토 항목');
 const selected=el('div',undefined,'preparation-entry-detail');
 choice.addEventListener('change',()=>{
  selected.replaceChildren();delete selected.dataset.preparationEntryState;const entry=entries.find(e=>e.id===choice.value);if(!entry)return;selected.dataset.preparationEntryState=entry.status;
  selected.append(el('p',`${preparationEntryLabel(entry)} · 저장된 상태: ${labels[entry.status]||entry.status}`,'muted'),preparationNavigation(task==='source_document'?'해당 문단 검토':task==='relation_rows'?'해당 연결 검토':'조회할 열 검토','review','review_entry',entry.id));
  if(task==='relation_rows'){
   const endpoints=[entry.source,entry.target];
   if(!entry.interpretation?.trim())selected.append(el('p','이 연결의 검토한 해석이 비어 있습니다. 관계 설명과 양쪽 열을 따로 확인하세요.','muted'));
   for(const ref of endpoints){
    const mapped=state.current.draft.entries.filter(e=>e.kind==='mapping'&&ref&&e.source.file===ref.file&&e.source.column===ref.column&&e.source.sha256===ref.sha256);
    selected.append(el('p',ref?`${ref.file} · ${ref.column} · 해당 열의 승인 ${mapped.filter(e=>e.status==='approved').length}개 / 검토 항목 ${mapped.length}개`:'연결 대상이 지정되지 않았습니다.','muted'));
    if(mapped.length)selected.append(preparationEntryLinks(mapped,'해당 열 검토'));
    else selected.append(el('p','이 연결 끝점의 열 검토 항목을 찾지 못했습니다. 원본과 연결 대상을 확인하세요.','muted'),preparationNavigation('연결 원본 확인','library','sources',null,ref?.file||null));
   }
  }
 });
 region.append(field('검토할 원본 항목',choice),selected);
}
function selectedPreparation(task){
 const w=state.current,d=w.draft,entries=d.entries,report=w.task_readiness,region=el('div',undefined,'selected-preparation');region.dataset.preparationTask=task;region.dataset.preparationState='needs_review';
 const tables=d.sources.filter(s=>s.kind==='table'),documents=d.sources.filter(s=>s.kind==='document');
 const actions=el('div',undefined,'actions');
 const sources=()=>preparationNavigation('원본 자료 확인','library','sources');
 const replacement=()=>preparationNavigation('자료 묶음 교체 안내','changes','source_replacement');
 const describeScopes=(catalog,kind)=>{
  const scopes=el('details');scopes.append(el('summary',`승인한 조회 범위 ${catalog.length}개`));
  const list=el('ul');for(const scope of catalog){const item=el('li',kind==='relation_rows'?`${scope.source.file} · ${scope.source.column} ↔ ${scope.target.file} · ${scope.target.column}`:kind==='source_document'?`${scope.file} · 문단 ${scope.paragraph}`:`${scope.file} · ${scope.column}`);list.append(item);}scopes.append(list);region.append(scopes);
 };
 if(task==='source_rows'||task==='source_document'){
  const isRow=task==='source_rows',sourcesForTask=isRow?tables:documents,catalog=(isRow?w.row_lookup_catalog:w.document_catalog)||[],candidates=entries.filter(e=>e.kind===(isRow?'mapping':'policy'));
  region.append(el('p',isRow?'승인한 열과 정확히 찾을 값을 선택합니다. 원문 조회용 필드도 사용할 수 있으며, 같은 값의 모든 행을 표시합니다.':'승인한 원문 문단을 읽습니다. 참고·맥락 용도도 사용할 수 있으며 정책 적용이나 승인 규칙 실행을 뜻하지 않습니다.'));
  region.append(el('p',isRow?'다른 정책의 승인이나 대체 상품 검토 준비는 필요하지 않습니다. 값이 없거나 여러 행이 나올 수 있습니다.':'날짜·금액 계산 규칙을 정하지 않아도 참고 문단을 읽을 수 있습니다. 다른 문단과의 충돌·우선순위는 확인하지 않습니다.','muted'));
  if(catalog.length){region.dataset.preparationState='ready';describeScopes(catalog,task);actions.append(preparationNavigation(isRow?'원본 행 조회 도구 열기':'문서 문단 조회 도구 열기','questions',task));}
  else if(!sourcesForTask.length){region.dataset.preparationState='no_source';region.append(el('p',isRow?'현재 묶음에는 CSV 표가 없습니다. 다른 곳에도 정보가 없다는 뜻은 아닙니다.':'현재 묶음에는 TXT/MD 문서가 없습니다. 표나 다른 곳에 관련 정보가 없다는 뜻은 아닙니다.','callout'));actions.append(replacement());}
  else{region.append(el('p',`승인한 조회 범위 0개 · 원본은 있지만 조회할 ${isRow?'열':'문단'}의 승인이 필요합니다. 제외된 항목은 사용자가 정한 검토 상태이며 원본 부재가 아닙니다.`,'muted'));actions.append(sources());}
  if(candidates.length)preparationEntryChoice(region,candidates,task);
  if(catalog.length)actions.append(sources());
 }else if(task==='relation_rows'){
  const catalog=w.relation_catalog||[],relations=entries.filter(e=>e.kind==='relation');
  region.append(el('p','서로 다른 두 CSV의 연결 설명과 양쪽 열을 승인한 뒤, 공백이 아닌 같은 문자열을 대조합니다. 중복 행은 모두 남으며 같은 업무 객체임을 보증하지 않습니다.'));
  if(catalog.length){region.dataset.preparationState='ready';describeScopes(catalog,task);actions.append(preparationNavigation('두 CSV 대조 도구 열기','questions',task));}
  else if(tables.length<2){region.dataset.preparationState='no_source';region.append(el('p','현재 묶음의 CSV 표가 2개 미만입니다. 이 도구는 서로 다른 두 파일의 열을 사용합니다.','muted'));actions.append(sources(),replacement());}
  else{region.append(el('p','승인한 조회 범위 0개 · 연결의 해석, 연결 상태, 양쪽 열의 승인을 확인하세요. 정보가 없다는 판정은 아닙니다.','muted'));actions.append(preparationNavigation('관계 직접 추가 안내','review','manual_relation'),sources());}
  if(relations.length)preparationEntryChoice(region,relations,task);
 }else if(task==='stock_check'){
  const targets=['skus.id','skus.available'],candidates=entries.filter(e=>e.kind==='mapping'&&targets.includes(e.target)),ready=report?.capabilities?.stock_check===1;
  region.append(el('p','같은 CSV에서 SKU ID와 가용 수량을 각각 하나씩 승인합니다. 질문에는 정확한 SKU와 1~1,000,000,000 범위의 정수 요청 수량을 적으세요.'));
  region.append(el('p','기록 수량만 비교합니다. 다른 정책 승인은 필요하지 않으며 창고 합산·예약·최신 재고 보장·대체 상품 승인 기능은 아닙니다. 같은 SKU가 여러 행이거나 수량이 비어 있으면 판단을 보류할 수 있습니다.','muted'));
  const roles=el('ul');for(const target of targets){const matches=candidates.filter(e=>e.target===target),approved=matches.filter(e=>e.status==='approved');roles.append(el('li',`${target} · 승인 ${approved.length}개 / 이 역할로 지정된 항목 ${matches.length}개${!matches.length?' · 원본을 보고 역할을 검토하세요. 자료 부재를 뜻하지 않습니다.':''}`));}region.append(roles);
  const approved=candidates.filter(e=>e.status==='approved');if(new Set(approved.map(e=>e.source.file)).size>1)region.append(el('p','두 재고 역할의 승인 열이 여러 파일에 걸쳐 있습니다. 이 비교에는 같은 CSV의 두 열이 필요합니다.','callout'));
  if(candidates.length){const details=el('details');details.append(el('summary','재고 필드 검토'),preparationEntryLinks(candidates,'해당 재고 필드 검토'));region.append(details);}else actions.append(preparationNavigation('재고 역할 검토','review','review_overview'));
  if(ready&&w.model_questions?.enabled){region.dataset.preparationState='ready';region.append(el('p','재고 조회 범위 준비됨 · 질문에 SKU와 요청 수량을 적으세요. 모델이 도구를 선택하며 탐색이 필요한 질문은 최대 4회 유료 호출할 수 있습니다. 전송은 질문 보내기에서 직접 선택합니다.','muted'));if(mutable())actions.append(button('질문 입력란으로 이동',()=>focusPreparationNode(document.querySelector('.question-composer textarea'))));else region.append(el('p','현재 활성 버전에서만 질문을 보낼 수 있습니다. 이 화면에서는 저장된 준비 정보를 확인합니다.','muted'));}
  else if(!w.model_questions?.enabled){region.dataset.preparationState=ready?'model_disabled':'needs_review';region.append(el('p','현재 자유 질문 모델이 비활성화되어 재고 비교 질문 도구를 사용할 수 없습니다. 별도의 직접 재고 비교 양식은 없습니다. 원본 행을 확인할 수 있습니다.','callout'));}
  else region.append(el('p','두 역할을 각각 하나씩 승인하고 같은 파일인지 확인하세요. 재고 필드가 이 역할로 검토되기 전에는 원본 행을 직접 확인할 수 있습니다.','muted'));
  actions.append(w.row_lookup_catalog?.length?preparationNavigation('원본 행 조회 도구 열기','questions','source_rows'):sources());
 }else if(task==='replacement_proposal'){
  const contract=report?.replacement;
  region.append(el('p','정해진 주문·상품·재고·정책 구조와 KRW 기준으로 대체 상품 변경안을 검토합니다. 실제 주문을 변경하지 않습니다.'));
  if(!contract){region.dataset.preparationState='unavailable';region.append(el('p','이 자료 버전의 대체 상품 준비 보고서를 확인할 수 없습니다. 실행 가능하다고 판단하지 않습니다.','callout'));actions.append(sources());}
  else{
   const issues=contract.issues||[],codes={currency:'현재 계산 통화는 KRW만 지원',pending:'승인 또는 제외할 항목',policy_missing:'정책 역할의 승인 필요',policy_multiple:'정책 승인 중복',field_missing:'필드 역할의 승인 필요',field_multiple:'필드 승인 중복',collection_split:'한 CSV로 준비할 자료 묶음',policy_scope:'정책 날짜·적용 범위 확인',policy_agreement:'정책과 계산 기준 대조'};
   region.dataset.preparationState=issues.length?'needs_review':'ready';
   region.append(el('p',issues.length?`저장된 준비 보고서의 확인 항목 ${issues.length}건`:'준비 보고서의 확인 항목 0건 · 실행 시 입력 값·식별자·참조와 선택한 변경안을 다시 검사합니다.','muted'));
   const issueList=(items,withActions)=>{const list=el('ul');for(const issue of items){const row=el('li',`${codes[issue.code]||issue.code}: ${issue.subject}`);if(withActions){const ids=issue.entry_ids||[],actual=entries.filter(e=>ids.includes(e.id)||!ids.length&&e.target===issue.subject);if(actual.length)row.append(preparationEntryLinks(actual));else if(issue.code==='policy_agreement')row.append(preparationNavigation('정책 문서와 표 대조 안내','review','policy_agreement'));else if(issue.code==='policy_scope')row.append(preparationNavigation('정책 검토 항목 보기','review','review_overview'));else row.append(sources(),replacement());}list.append(row);}return list;};
   if(issues.length){region.append(issueList(issues.slice(0,3),false));const all=el('details');all.append(el('summary','전체 준비 항목'),issueList(issues,true));region.append(all);}
   const hasTarget=target=>entries.some(e=>e.kind==='mapping'&&e.target===target&&e.status!=='excluded');
   if(!issues.length&&hasTarget('items.id')&&hasTarget('skus.id'))actions.append(preparationNavigation('대체 상품 검토 도구 열기','questions',task));
   else actions.append(preparationNavigation('필드와 정책 검토','review','review_overview'));
   region.append(el('p','준비 안내는 변경안 승인이나 자료의 사실성·완전성 확인이 아닙니다. 역할 미승인은 원본 정보 부재를 뜻하지 않습니다.','muted'));
  }
 }
 region.append(actions);return region;
}
function taskPreparationGuide(){
 const w=state.current,guide=el('details',undefined,'task-preparation-guide');guide.id='task-preparation-guide';guide.dataset.testid='task-readiness';guide.dataset.preparationTarget='guide';
 guide.append(el('summary','질문 준비 안내 · 필요한 자료와 지원 범위'));
 state.preparationTasks??=new Map();
 const options=[['','작업을 선택해 준비 사항 확인'],['source_rows','원본 행 찾기'],['source_document','문서 문단 읽기'],['relation_rows','두 CSV의 같은 값 대조']];
 if(w.draft.adapter==='commerce-csv-1')options.push(['stock_check','기록된 재고 수량 비교'],['replacement_proposal','정해진 대체 상품 검토']);
 const previous=state.preparationTasks.get(w.id)||'',choice=select(options,options.some(([key])=>key===previous)?previous:'');choice.setAttribute('aria-label','확인하려는 작업');choice.setAttribute('aria-controls','selected-task-preparation');
 const region=el('div');region.id='selected-task-preparation';
 const notice=el('p',undefined,'muted preparation-announcement');notice.setAttribute('role','status');notice.setAttribute('aria-live','polite');
 const update=announce=>{state.preparationTasks.set(w.id,choice.value);region.replaceChildren();if(choice.value)region.append(selectedPreparation(choice.value));else region.append(el('p','직접 선택한 작업의 준비 사항만 안내합니다. 질문을 자동으로 분류하거나 실행하지 않습니다.','muted'));if(announce)notice.textContent=choice.value?`${choice.selectedOptions[0].textContent} · 표시 중인 자료 버전 ${w.revision}의 준비 안내`:'작업 선택을 해제했습니다.';};
 choice.addEventListener('change',()=>update(true));guide.append(field('확인하려는 작업',choice),el('p',`표시 중인 자료 버전 ${w.revision} · 저장된 검토 기준${!mutable()?' · 이전 버전 또는 보관 자료: 안내와 원본 확인만 가능':''}${state.edited?' · 미저장 검토는 아직 반영되지 않음':''}`,'muted'),region,notice);update(false);
 if(w.draft.adapter==='commerce-csv-1'){
  const refund=el('details',undefined,'refund-scope');refund.append(el('summary','환불 근거와 승인 범위'),el('p','원본 기록과 정책 문구를 확인할 수 있지만 이 도구에는 환불 승인 절차가 없습니다. 배송 완료일과 반품 사유 자료를 추가해도 환불 승인을 실행하는 기능이 생기지는 않습니다.'),el('p','예: shipped는 배송 완료 날짜가 아닙니다. 배송 완료일·반품 사유가 기록되어 있는지는 실제 원본과 검토 항목에서 확인하세요. 이 예시는 현재 자료에 해당 정보가 없다는 판정이 아닙니다.','muted'),el('p','좁힌 질문 예시: 이 주문에 기록된 상품명·분류·배송 상태를 원문 근거와 함께 보여 주세요. 이 예시를 질문란에 자동 입력하거나 실행하지 않습니다.','muted'));
  const actions=el('div',undefined,'actions');actions.append(preparationNavigation('원본 자료 확인','library','sources'),preparationNavigation('자료 묶음 교체 안내','changes','source_replacement'));refund.append(actions);guide.append(refund);
 }
 return guide;
}
function questionForm(){
 const box=el('article',undefined,'card question-composer'),info=state.current.model_questions||{};box.dataset.composerWorkspace=state.current.id;
 box.setAttribute('aria-label','메시지 작성');if(!info.enabled)box.append(el('p','현재 질문 모델이 꺼져 있습니다. 저장된 대화와 직접 조회 도구를 확인할 수 있습니다.','muted'));
 const question=el('textarea');question.maxLength=6000;question.rows=2;question.placeholder='이 저장소에 어떤 자료가 있나요? 또는 확인할 대상과 조건을 적어주세요';question.setAttribute('aria-label','자료에 대한 질문');
 const draftKey='operations-question-draft-'+state.current.id;question.value=state.chatPending?.workspace===state.current.id?'':recalled(draftKey)||'';
 const cursor=state.questionCursors?.get(state.current.id);if(cursor?.value===question.value){question.setSelectionRange(cursor.start,cursor.end,cursor.direction);question.scrollTop=cursor.scroll;}
 question.addEventListener('input',()=>remember(draftKey,question.value));
 const run=button('질문 보내기',()=>{
  if(!question.value.trim())return;
  if(window.confirm('질문과 조회에 필요한 식별자·근거를 외부 모델에 보냅니다. 공유 예산에서 질문에 따라 최대 4회 호출하며 자동 재시도하지 않습니다. 진행할까요?'))askQuestion(question.value,crypto.randomUUID());
 },'primary');submissionControl(run,!mutable()||!info.enabled);question.disabled=!mutable();
 question.addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();if(!run.disabled)run.click();}});
 box.append(field('메시지',question));
 const examples=el('div',undefined,'question-examples');examples.setAttribute('aria-label','질문 예시 · 입력만 합니다');
 for(const [title,text] of [['자료 개요','이 저장소에 어떤 자료가 있는지 구조와 샘플을 살펴보고 설명해 주세요.'],['가능한 질문','이 저장소에서 지금 답할 수 있는 질문과 추가 검토가 필요한 질문을 알려 주세요.'],['검토 대기','아직 검토하거나 승인해야 할 항목과 그 이유를 알려 주세요.']]){
  const example=button(title,()=>{if(question.value.trim()&&question.value!==text&&!window.confirm('작성 중인 질문을 이 예시로 바꿀까요?'))return;question.value=text;remember(draftKey,text);question.focus();question.setSelectionRange(text.length,text.length);});example.disabled=!mutable();examples.append(example);
 }
 const composerActions=el('div',undefined,'chat-composer-actions');composerActions.append(el('span','Enter 전송 · Shift+Enter 줄바꿈','muted'),run);box.prepend(examples);box.append(composerActions,el('p',`질문마다 독립 실행 · 이전 대화는 모델에 자동 전달되지 않습니다.${info.enabled?' · '+info.model:''}`,'chat-composer-note'));const scope=el('details',undefined,'question-scope');scope.append(el('summary','자료 탐색과 업무 조회의 범위'),el('p','자료 구조·샘플·검토 상태는 승인 전에도 탐색할 수 있습니다. 탐색 결과가 업무 조회의 승인이나 원본의 사실성·완전성 확인을 뜻하지는 않습니다.','muted'),el('p',isDatabaseWorkspace()?'모델이 한 번에 최대 4개, 전체 최대 8개의 탐색·승인한 열의 조건 조회·승인된 질의를 선택합니다. SQL이나 새 질의를 만들지 않습니다. 질문 해석과 답변의 정확성은 별도 검토가 필요합니다.':'승인한 필드로 원본을 조회하거나 지원하는 고정 검토를 실행합니다. 주문·환불 등의 업무 처리는 수행하지 않습니다.','muted'));box.append(scope);if(!isDatabaseWorkspace())box.append(taskPreparationGuide());return box;
}
function operationProgressText(p){
 const terminal={completed:'실행 완료 · 저장된 결과 확인 중',failed:'실행 실패 · 저장된 기록 확인 중',cancelled:'실행 취소됨 · 저장된 기록 확인 중',interrupted:'서버 중단으로 실행이 끝났습니다. 저장된 기록을 확인하세요. 자동으로 다시 호출하지 않습니다.'};
 if(Object.hasOwn(terminal,p.state))return cancellableExecutionKinds.has(p.kind)?({completed:'실행 완료 · 저장된 결과를 확인하세요.',failed:'실행 실패 · 저장된 오류와 남은 근거를 확인하세요.',cancelled:'실행 중지됨 · 저장된 기록과 부분 근거를 확인하세요.',interrupted:'실행 중단 · 저장된 기록을 확인하세요. 자동으로 다시 실행하지 않습니다.'})[p.state]:terminal[p.state];
 if(cancellableExecutionKinds.has(p.kind)){
  if(p.cancel_requested)return '중지 요청됨 · 서버가 실행을 멈추고 기록을 저장할 때까지 기다립니다. 완료와 중지가 겹치면 실제 종료 상태를 표시합니다.';
  if(p.state==='not_recorded')return '서버 접수 대기 중 · 같은 요청의 상태를 확인하고 있습니다.';
  return `${p.kind==='database_query_execute'?'승인된 질의':'로컬 OO 추론'} 처리 중 · 원본 준비 단계는 즉시 멈추지 않을 수 있습니다.`;
 }
 if(p.cancel_requested)return '취소 요청됨 · 진행 중인 응답을 기다립니다. 이미 시작한 호출은 과금될 수 있습니다.';
 if(p.state==='not_recorded')return '서버 접수 기록을 기다리는 중';
 if(p.kind==='model_suggestions')return '초안 생성 처리 중 · 완료 여부를 확인하고 있습니다. 승인 내용은 바뀌지 않습니다.';
 const phases={planning:'질문 해석 · 조회 선택 중',exploring:'저장소 구조·샘플·검토 상태 탐색 중',replanning:'탐색 근거를 바탕으로 다음 조회 선택 중',retrieving:'선택한 도구로 근거 조회 중',answering:'조회 근거로 답변 작성 중',completed:'답변 저장 중'};
 return `${Object.hasOwn(phases,p.phase)?phases[p.phase]:'실행 접수 · 자료 버전 준비 중'} · 조회 완료 ${p.tools_completed||0}개 / 실패 ${p.tools_failed||0}개`;
}
function setQuestionProgressMessage(message){$('notice').textContent=message;const live=document.querySelector('.chat-live-label');if(live)live.textContent=message;}
function watchQuestionProgress(id,requestKey,kind=null){
 let stopped=false,timer;state.foregroundRequest={id,requestKey};renderRecovery();
 const update=p=>{const record=[...recoveries.values()].find(r=>r.id===id&&r.request?.request_key===requestKey);if(record){acceptRecoveryStatus(record,p);renderRecovery();}};
 const cancel=el('button',cancellableExecutionKinds.has(kind)?'실행 중지 요청':'실행 취소');cancel.type='button';cancel.onclick=async()=>{cancel.disabled=true;try{const raw=await api({action:'cancel',id,request_key:requestKey}),p={...raw,kind:raw.kind||kind};if(!stopped){update(p);cancel.disabled=p.state!=='running'||Boolean(p.cancel_requested);if(cancellableExecutionKinds.has(kind))cancel.textContent=p.cancel_requested?'중지 요청됨':'실행 중지 요청';setQuestionProgressMessage(operationProgressText(p));}}catch(e){if(!stopped){setQuestionProgressMessage(e.message);cancel.disabled=false;}}};
 cancel.disabled=true;cancel.dataset.testid='operation-cancel';$('notice').setAttribute('role','status');$('notice').setAttribute('aria-live','polite');setQuestionProgressMessage(operationProgressText({state:'not_recorded',kind}));const liveActions=document.querySelector('.chat-pending .chat-assistant');if(liveActions)liveActions.append(cancel);else $('notice').insertAdjacentElement('afterend',cancel);
 const poll=async()=>{try{const raw=await api({action:'progress',id,request_key:requestKey}),p={...raw,kind:raw.kind||kind};if(stopped)return;update(p);cancel.disabled=p.state!=='running'||p.cancel_requested;if(cancellableExecutionKinds.has(kind))cancel.textContent=p.cancel_requested?'중지 요청됨':'실행 중지 요청';setQuestionProgressMessage(operationProgressText(p));}catch{if(!stopped)setQuestionProgressMessage('진행 상태를 확인하지 못했습니다. 실행 결과를 기다리고 있으며 다시 요청하지 않습니다.');}finally{if(!stopped)timer=setTimeout(poll,800);}};
 timer=setTimeout(poll,200);return ()=>{stopped=true;clearTimeout(timer);cancel.remove();if(state.foregroundRequest?.requestKey===requestKey){state.foregroundRequest=null;renderRecovery();}};
}
async function askQuestion(question,requestKey,revision=state.current.revision){
 if(!canLeave())return;
 state.chatPending={workspace:state.current.id,question,revision,requestKey};render();
 await task(async()=>{
  const key='operations-request-'+state.current.id,pending=recalled(key);
  assertRequestAllowed(key,requestKey);
  if(!pending)remember(key,JSON.stringify({question,request_key:requestKey,revision}));
  collectRecovery(state.current.id);renderRecovery();
  $('notice').textContent='질문을 처리하고 있습니다. 완료 전에는 자동으로 다시 보내지 않습니다.';
  const stopProgress=watchQuestionProgress(state.current.id,requestKey);
  try{
   const result=await api({action:'ask',id:state.current.id,revision,request_key:requestKey,question});
   stopProgress();
   resolveSubmitted(key,requestKey,result.operation);
   const draftKey='operations-question-draft-'+state.current.id;
   if(recalled(draftKey)===question)remember(draftKey,null);
   state.chatPending=null;
   await showExecution(result.operation);
   document.querySelector('.chat-turn:last-child')?.scrollIntoView({block:'start',behavior:'smooth'});
   $('notice').textContent=result.operation.state==='completed'?'답변과 근거를 저장했습니다.':'현재 실행 상태와 남은 근거를 확인하세요.';
  }catch(error){state.chatPending=null;render();throw error;}finally{stopProgress();}
 });
 if(state.chatPending?.requestKey===requestKey){state.chatPending=null;render();}
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
/* Saved operation provenance only: no current-draft enrichment or entity inference. */
function questionEvidenceGraphData(op){
 const result=op.result||{},evidence=Array.isArray(result.evidence)?result.evidence:[],citations=Array.isArray(result.citations)?result.citations:[];
 const data={nodes:[],edges:[],branches:[],limitations:[],counts:{attempted:evidence.length,cited:0}};
 const text=value=>typeof value==='string'?value:'기록 없음';
 const node=(id,type,label,note='')=>{const value={id,type,label,note};data.nodes.push(value);return value;};
 const edge=(from,to,label,note='')=>{const value={from:from.id,to:to.id,label,note};data.edges.push(value);return value;};
 const root=node('question','question',text(op.request?.question),`저장된 자료 버전 ${op.revision??'기록 없음'}`);
 const names={explore_repository:'저장소 구조·샘플 탐색',source_lookup:'식별자로 원본 조회',source_rows:'원본 열로 행 조회',relation_rows:'두 열의 같은 문자열 대조',source_document:'원문 문단 조회',stock_check:'기록 수량 비교',replacement_proposal:'고정 변경안 검토',saved_case:'저장된 질문 실행'};
 const occurrences=new Map();
 for(const item of evidence)if(typeof item?.id==='string')occurrences.set(item.id,(occurrences.get(item.id)||0)+1);
 const lookupNodes=evidence.map((item,index)=>node(`lookup-${index}`,'lookup',`${text(item?.id)} · ${names[item?.tool]||text(item?.tool)}`));
 for(const [index,saved] of evidence.entries()){
  const item=saved&&typeof saved==='object'?saved:{},lookup=lookupNodes[index],cited=typeof item.id==='string'&&citations.includes(item.id);
  const branch={index,lookup:lookup.id,state:text(item.state),cited,edges:[],limitations:[],notes:[]};data.branches.push(branch);
  if(cited)data.counts.cited++;
  const addEdge=(from,to,label,note='')=>{const value=edge(from,to,label,note);branch.edges.push(value);return value;};
  addEdge(root,lookup,'조회 시도',`${labels[item.state]||text(item.state)} · ${cited?'답변에서 참조':'답변에서 참조하지 않음'}`);
  if(typeof item.id!=='string'||occurrences.get(item.id)!==1)branch.limitations.push('근거 ID가 없거나 중복되어 저장된 참조를 명확히 연결할 수 없습니다.');
  if(item.binding){
   const binding=item.binding,prior=evidence.findIndex(entry=>entry?.id===binding.from_evidence);
   if(item.failure_kind!=='unresolved_binding'&&occurrences.get(item.id)===1&&occurrences.get(binding.from_evidence)===1&&prior>=0&&prior<index&&evidence[prior]?.state==='completed'&&evidence[prior]?.tool==='source_rows'&&evidence[prior]?.result?.lookup_kind==='source_rows'&&typeof binding.column==='string'&&typeof binding.value==='string'){
    addEdge(lookupNodes[prior],lookup,`열 ${binding.column}의 정확한 값 전달`,`전달 값: ${binding.value} · 모델이 선택한 조회 의존 관계이며 업무상 관계나 동일 객체임을 검증하지 않았습니다.`);
   }else branch.limitations.push('저장된 값 연결의 앞선 근거·열·값을 명확히 확인할 수 없어 의존 연결을 표시하지 않았습니다.');
  }
  if(item.failure_kind==='unresolved_binding'){
   const reference=item.arguments?.value;
   branch.limitations.push(`값 연결 미해결${reference&&typeof reference==='object'?` · 요청한 앞선 근거: ${text(reference.from_evidence)} · 열: ${text(reference.column)}`:''}. 성공한 값 전달 연결이 아닙니다.`);
  }
  if(item.state!=='completed'){
   branch.limitations.push(item.error?`저장된 오류: ${text(item.error)}`:'조회가 완료된 상태가 아니므로 성공한 원본 연결을 표시하지 않았습니다.');continue;
  }
  const output=item.result;
  if(!output||typeof output!=='object'){branch.limitations.push('완료 상태이지만 저장된 결과 구조가 없습니다.');continue;}
  const status=typeof output.status==='string'?`저장된 결과 상태: ${output.status}`:'';
  if(status){branch.resultStatus=output.status;branch.notes.push(status);}
  const addScope=(from,scope,records,label,limitation)=>{
   if(!scope||typeof scope.file!=='string'){branch.limitations.push('선택한 원본 파일 정보가 기록되지 않아 해당 원본 연결을 표시하지 않았습니다.');return;}
   const count=Array.isArray(records)?records.length:null;
   const location=count===null?'반환 행 수 기록 없음':`${count}개 레코드`;
   const scopeLabel=`${scope.file}${typeof scope.column==='string'?` · ${scope.column}`:''} · ${location}`;
   const scopeNode=node(`scope-${index}-${data.nodes.length}`,'scope',scopeLabel,`원본 해시: ${text(scope.sha256)}`);
   addEdge(from,scopeNode,label,`${limitation}${count===0?' 선택한 범위에 일치하는 기록이 없습니다. 다른 자료의 부재를 뜻하지 않습니다.':''}`);
   if(count===null)branch.limitations.push('원본 레코드 목록이 기록되지 않아 개수를 추정하지 않았습니다.');
  };
  if(output.mode==='repository_exploration'){
   const scope=node(`exploration-${index}`,'scope',output.provenance?.file||'저장된 저장소 자료 목록',`탐색 작업: ${text(output.action)}`);
   addEdge(lookup,scope,'구조·샘플·검토 상태 탐색','저장된 탐색 결과의 범위입니다. 업무 조회 승인·원본의 사실성·완전성 확인이 아닙니다.');
   if(output.truncated)branch.limitations.push('일부 항목 또는 샘플만 반환되었습니다. 전체 자료를 확인한 결과가 아닙니다.');
  }else if(output.mode==='source_lookup'){
   const scope=output.scope,records=output.records;
   branch.notes.push(output.lookup_kind==='source_rows'?`선택한 원본 열: ${text(scope?.column)} · 정확한 필터 값: ${text(scope?.value)}`:'승인된 표준 필드 연결을 사용한 식별자 조회입니다. 원본 열 대응과 레코드 위치는 근거 상세에 보관됩니다.');
   if(Array.isArray(records)&&records.length){
    const groups=new Map();
    for(const record of records){const source=record?.source;if(!source||typeof source.file!=='string'){branch.limitations.push('일부 반환 레코드의 원본 파일 정보가 기록되지 않았습니다.');continue;}const key=JSON.stringify([source.file,source.sha256??null]);if(!groups.has(key))groups.set(key,{scope:{file:source.file,sha256:source.sha256,...(output.lookup_kind==='source_rows'?{column:scope?.column}:{})},records:[]});groups.get(key).records.push(record);}
    for(const group of groups.values())addScope(lookup,group.scope,group.records,`원본 ${group.records.length}개 레코드 반환`,'레코드를 원본 파일·해시별로 묶었습니다. 정책 적용·동일 객체·원본의 완전성은 검증하지 않았습니다.');
   }else addScope(lookup,scope,records,'선택한 원본 범위 조회','선택한 범위만 조회했습니다.');
  }else if(output.mode==='source_document'){
   const source=output.source;
   if(source&&typeof source.file==='string'){
    const paragraph=node(`paragraph-${index}`,'paragraph',`${source.file} · 문단 ${source.paragraph??'기록 없음'}`,`원문 행: ${source.line_start??'기록 없음'}–${source.line_end??'기록 없음'} · 원본 해시: ${text(source.sha256)}`);
    addEdge(lookup,paragraph,'선택한 원문 문단 읽기','사용자가 승인한 참고 문단이며 질문에 대한 정책 적용·우선순위·충돌·완전성을 확인한 결과가 아닙니다.');
   }else branch.limitations.push('저장된 문단의 원본 파일 정보가 없습니다.');
  }else if(output.mode==='reviewed_relation_rows'){
   const comparison=node(`comparison-${index}`,'comparison','선택한 두 열의 정확한 문자열 대조',`대조한 값: ${text(output.value)}`);
   addEdge(lookup,comparison,'저장된 문자열 대조 결과','같은 업무 객체나 관계의 사실성을 검증한 연결이 아닙니다.');
   if(typeof output.relation?.reviewed_interpretation==='string')comparison.description=output.relation.reviewed_interpretation;
   for(const side of ['source','target']){
    const endpoint=output.sides?.[side],scope=endpoint?.scope;
    addScope(comparison,scope,endpoint?.records,'정확한 문자열 대조',`${side==='source'?'기준':'상대'} 열의 일치 레코드입니다. 행 쌍 확장·업무 객체 동일성·관계의 사실성은 확인하지 않았습니다.`);
   }
  }else if(output.mode==='recorded_stock_check'){
   branch.notes.push(`기록 수량과 요청 수량 비교 · SKU: ${text(output.request?.sku)} · 요청 수량: ${output.request?.quantity??'기록 없음'}`);
   addScope(lookup,output.scope,output.records,'기록 수량과 요청 수량 비교에 조회한 범위','재고 예약·최신성·대체 적합성·배송·주문 승인은 확인하지 않았습니다.');
  }else{
   const generic=node(`result-${index}`,'result',`저장된 도구 결과 · ${text(output.mode)}`);
   addEdge(lookup,generic,'완료된 결과 보관','이 결과 형식의 내부 관계는 펼치지 않았습니다. 기존 근거 상세에서 확인하세요.');
  }
 }
 if(!evidence.length)data.limitations.push('이 실행에 저장된 조회 시도가 없습니다. 원본이나 업무 관계를 추정해 추가하지 않았습니다.');
 for(const id of citations)if(typeof id!=='string'||!occurrences.has(id))data.limitations.push('저장된 답변 참조 중 조회 근거와 연결되지 않는 ID가 있습니다.');
 return data;
}
function questionEvidenceGraph(op,evidenceTargets){
 const data=questionEvidenceGraphData(op),panel=el('details',undefined,'question-evidence-graph');
 const excerpt=(value,limit=86)=>{const characters=Array.from(value);return characters.length>limit?characters.slice(0,limit).join('')+'…':value;};
 panel.append(el('summary',`질문 근거 연결 · 조회 시도 ${data.counts.attempted}개 · 답변에서 참조 ${data.counts.cited}개`),el('p','저장된 조회와 값 전달입니다. 답변의 사실성·근거의 충분성·업무 객체의 동일성을 검증한 연결이 아닙니다.','muted'));
 const nodes=new Map(data.nodes.map(node=>[node.id,node]));
 const visual=el('div',undefined,'evidence-graph-visual');visual.setAttribute('aria-hidden','true');
 const root=nodes.get('question'),rootNode=el('div',undefined,'evidence-graph-root');rootNode.append(el('strong','질문'),el('p',excerpt(root.label)),el('small',root.note));visual.append(rootNode);
 const branches=el('div',undefined,'evidence-graph-branches');
 for(const branch of data.branches){
  const row=el('div',undefined,'evidence-graph-branch'),lookup=nodes.get(branch.lookup),lookupNode=el('div',undefined,'evidence-graph-lookup');
  lookupNode.append(el('span','조회 시도','evidence-edge-label'),el('strong',lookup.label),badge(branch.state),el('small',branch.cited?'답변에서 참조':'답변에서 참조하지 않음'));
  row.append(lookupNode);const scopes=el('div',undefined,'evidence-graph-scopes');
  for(const edge of branch.edges.filter(item=>item.from!=='question')){
   const from=nodes.get(edge.from),to=nodes.get(edge.to),scope=el('div',undefined,'evidence-graph-scope');
   if(from.type==='comparison')scope.append(el('small','출발: 두 열 문자열 대조','evidence-edge-origin'));
   scope.append(el('span',edge.label,'evidence-edge-label'),el('strong',to.label));
   if(to.type==='comparison'&&to.description)scope.append(el('small',`사용자 검토 설명 · 검증된 사실 아님: ${excerpt(to.description,70)}`,'evidence-relation-description'));
   if(edge.to===branch.lookup)scope.append(el('small',`앞선 근거: ${from.label}`));
   scopes.append(scope);
  }
  if(!scopes.children.length)scopes.append(el('p',branch.state==='completed'?'저장된 범위는 텍스트 연결에서 확인하세요.':'완료된 원본 연결 없음','muted'));
  row.append(scopes);branches.append(row);
 }
 visual.append(branches);panel.append(visual);
 const fallback=el('section',undefined,'evidence-graph-text');fallback.append(el('h4','텍스트 연결'));
 const context=el('details',undefined,'evidence-graph-context');context.append(el('summary',`질문 원문 · ${root.note}`),el('p',root.label));fallback.append(context);
 for(const limitation of data.limitations)fallback.append(el('p',limitation,'muted'));
 const list=el('ol');
 for(const branch of data.branches){
  const item=el('li'),lookup=nodes.get(branch.lookup);
  item.append(el('strong',lookup.label),el('p',`조회 시도 · ${labels[branch.state]||branch.state} · ${branch.cited?'답변에서 참조':'답변에서 참조하지 않음'}${branch.resultStatus?` · 결과: ${branch.resultStatus}`:''}`,'evidence-branch-status'));
  const connections=el('ul');
  for(const edge of branch.edges.filter(value=>value.from!=='question')){
   const from=nodes.get(edge.from),to=nodes.get(edge.to),connection=el('li');
   connection.append(el('p',`${from.label} → ${edge.label} → ${to.label}`));
   if(from.type==='comparison')connection.append(el('p','출발: 두 열 문자열 대조 · 같은 업무 객체나 관계의 사실성을 확인한 연결이 아닙니다.','muted'));
   if(to.type==='comparison'&&to.description)connection.append(el('p',`사용자 검토 설명 · 검증된 사실 아님: ${excerpt(to.description,86)}`,'evidence-relation-description'));
   connections.append(connection);
  }
  item.append(connections);
  if(branch.state!=='completed')item.append(el('p','완료된 원본 연결 없음','muted'));
  for(const limitation of branch.limitations)item.append(el('p',excerpt(limitation,110),'evidence-branch-limitation'));
  const provenance=el('details',undefined,'evidence-branch-provenance');provenance.append(el('summary','출처·전달 값·제한 상세'));
  for(const edge of branch.edges){
   const from=nodes.get(edge.from),to=nodes.get(edge.to),entry=el('div',undefined,'evidence-provenance-entry');
   entry.append(el('p',`${from.type==='question'?'질문':from.label} → ${edge.label} → ${to.label}`));
   if(to.note)entry.append(el('p',to.note,'muted'));
   if(edge.note)entry.append(el('p',edge.note,'muted'));
   if(to.type==='comparison'&&to.description)entry.append(el('p',`사용자가 검토한 관계 설명 원문: ${to.description} · 원본 사실로 검증된 관계명이 아닙니다.`));
   provenance.append(entry);
  }
  for(const note of branch.notes)provenance.append(el('p',note,'muted'));
  for(const limitation of branch.limitations)provenance.append(el('p',limitation,'callout'));
  provenance.append(el('p','원본 레코드는 범위별로 묶었습니다. 전체 행·문단과 저장된 위치는 아래 근거 상세에서 확인하세요.','muted'));item.append(provenance);
  item.append(button('이 조회의 근거 상세 열기',()=>{const target=evidenceTargets[branch.index];if(!target)return;target.open=true;const summary=target.querySelector('summary');summary?.focus();summary?.scrollIntoView({block:'nearest'});}));list.append(item);
 }
 fallback.append(list);panel.append(fallback);return panel;
}


function databaseQuestionResult(op){
 const r=op.result||{},card=el('article',undefined,'card question-answer');
 card.append(el('h3',op.request.question),badge(op.state),el('p',`자료 버전 ${op.revision} · 자료 탐색·승인한 열 또는 질의 조회`, 'muted'));
 if(r.answer)card.append(answerNode(r.answer));
 if(op.error)card.append(operationError(op.error));
 if(r.requirement_resolutions?.length)card.append(requirementResolutionReview(r));
 if(r.unresolved?.length){card.append(el('h4','답하지 못한 요구'));const list=el('ul');for(const v of r.unresolved)list.append(el('li',v));card.append(list);}
 card.append(el('p','모델이 자료 탐색, 승인한 열의 조건 조회 또는 승인된 질의와 조건을 선택했습니다. 구조·샘플 탐색은 업무 조회 승인이 아니며, 실행 성공·근거 참조가 질문 해석이나 답변의 정확성을 보증하지 않습니다.','callout'));
 for(const e of r.evidence||[]){const exploration=e.tool==='explore_repository'||e.result?.mode==='repository_exploration';const title=e.approval_operation_id?(r.catalog||[]).find(item=>item.approval_operation_id===e.approval_operation_id)?.title:null;const block=el('details');block.append(el('summary',`${e.id} · ${exploration?'저장소 탐색':e.tool==='query_source'?'승인한 열 조건 조회':title||e.approval_operation_id||'저장된 조회'} · ${labels[e.state]||e.state}${r.citations?.includes(e.id)?' · 답변에서 참조':''}`),detail('모델이 선택한 조건',e.arguments||e.parameters||{}));
  if(e.error)block.append(el('p',e.error,'callout'));
  if(e.result?.mode==='repository_exploration')block.append(repositoryExplorationResult(e.result));
  else if(e.result?.mode==='approved_source_query'){const rows=e.result.records||[];if(rows.length){const columns=Object.keys(rows[0]);block.append(table(columns,rows.map(row=>columns.map(c=>row[c]))));}block.append(el('p',`전체 일치 ${e.result.total_matching_rows}행 · 반환 ${e.result.returned_count}행${e.result.truncated?' · 일부만 표시':''} · 자료형 조건에서 제외 ${e.result.excluded_by_filter_type_rows}행`,'muted'),el('p','저장된 수량·값의 조건 조회입니다. 실제 주문 승인이나 최신 재고를 확인한 것은 아닙니다.','muted'),detail('실제 조회 결과 · 원본과 승인 버전',e.result));}
  else if(e.result)block.append(detail('실제 조회 결과 · 원본과 승인 버전',e.result));
  const oid=e.result?.execution_operation_id||(r.child_operations||[]).find(c=>c.evidence_id===e.id)?.operation_id;if(oid)block.append(button('이 조회의 저장된 실행 열기',()=>task(()=>openSavedOperation(state.current.id,oid))));
  card.append(block);
 }
 card.append(detail('공급자·원본·조회 목록·실행 기록',r),button('이 질문의 저장된 실행 확인',()=>task(()=>openSavedOperation(state.current.id,op.id))));return card;
}
function requirementResolutionReview(result){
 const box=el('details');box.append(el('summary',`모델이 답변 완료로 분류한 항목 ${result.requirement_resolutions.length}개`),el('p','중간 계획의 확인 항목을 모델이 근거와 대조한 기록입니다. 시스템이 답변의 사실성을 검증한 결과는 아닙니다.','muted'),table(['확인 항목','모델의 판단 근거','근거 ID'],result.requirement_resolutions.map(item=>[item.requirement,item.explanation,item.citations.join(', ')])));return box;
}
function repositoryExplorationResult(result){
 const panel=el('section',undefined,'repository-exploration');
 const value=v=>v===null||v===undefined?'미확인':typeof v==='object'?JSON.stringify(v):String(v);
 const review=a=>labels[a?.review_status]||a?.review_status||'기록 없음';
 const countText=counts=>Object.entries(counts||{}).map(([key,n])=>`${labels[key]||key} ${n}개`).join(' · ')||'필드 검토 기록 없음';
 const fieldRows=items=>items.map(item=>[item.column,review(item.annotations),value(item.annotations?.interpretation),value(item.declared_schema||item.observed_profile)]);
 panel.append(el('h4',({overview:'저장소 자료 개요',list:'선택한 자료의 필드',detail:'선택한 필드와 샘플',relationships:'저장된 관계 후보와 선언',policies:'저장된 정책 문단과 검토 기록'})[result.action]||'저장소 탐색 근거'),el('p','저장된 자료의 구조·샘플·검토 기록입니다. 탐색 결과는 업무 조회 승인이나 사실성·최신성·완전성 확인이 아닙니다.','muted'));
 if(result.provenance?.file)panel.append(el('p',`출처: ${result.provenance.file}`,'source-quote'));
 if(result.action==='overview'){
  panel.append(kv({'전체 자료 수':result.source_count,'전체 필드 수':result.field_count}));
  panel.append(table(['자료','형식','필드','저장 당시 전체 행','저장된 표본 행','표본 밖의 행','필드 검토 상태'],(result.items||[]).map(item=>[item.source,({table:'CSV',database_table:'DB 표',document:'문서'})[item.kind]||item.kind,item.field_count,item.total_source_rows,item.saved_sample_rows,item.rows_outside_saved_sample,countText(item.review_counts)])));
 }else if(result.action==='list')panel.append(table(['원본 열','검토 상태','검토자가 작성한 해석','선언 스키마 / 관측 프로필'],fieldRows(result.items||[])));
 else if(result.action==='relationships'){
  panel.append(table(['관계 출처','자료·열 / 선언','검토 상태','검토자가 작성한 해석'],(result.items||[]).map(item=>[item.origin==='database_declared_foreign_key'?'DB 외래 키 선언':'저장된 관계 후보',item.endpoints?item.endpoints.map(e=>`${e.provenance?.file??'미확인'} · ${e.column??'미확인'}`).join(' ↔ '):`${(item.source_names||[]).join(' ↔ ')} · ${value(item.declaration)}`,review(item.annotations),value(item.annotations?.interpretation)])),el('p','관계 후보·외래 키 선언을 확인한 결과입니다. 조인을 실행하거나 업무상 같은 객체인지 검증하지 않았습니다.','muted'));
 }else if(result.action==='policies'){
  for(const item of result.items||[]){const entry=el('article',undefined,'source-quote');entry.append(el('h4',item.provenance?.file||'저장된 정책 문단'),badge(item.annotations?.review_status||'unknown'),el('p',item.content_withheld?'제외한 문단의 본문은 공개하지 않았습니다.':!item.source_paragraph_found?'저장된 원본 문단을 찾지 못했습니다.':value(item.snippet)),el('p',`원본 위치: ${value(item.locator)}`,'muted'),el('p',`검토자가 작성한 해석: ${value(item.annotations?.interpretation)}`));panel.append(entry);}
  panel.append(el('p','문단과 검토 설명의 탐색 결과입니다. 이 질문에 적용할 정책인지 자동 판정하지 않았습니다.','muted'));
 }else if(result.action==='detail'){
  panel.append(table(['원본 열','검토 상태','검토자가 작성한 해석','선언 스키마 / 관측 프로필'],fieldRows([result])));
  if(result.samples_withheld)panel.append(el('p','제외한 필드의 샘플은 공개하지 않았습니다.','muted'));
  else panel.append(table(['저장 샘플 값','원본 위치 / 저장 샘플 위치'],(result.samples||[]).map(sample=>[value(sample.value),value(sample.locator)])));
  panel.append(el('p',`반환 샘플 ${result.returned_sample_rows??0}행 · 표시하지 않은 저장 샘플 ${result.omitted_saved_sample_rows??'미확인'}행`,'muted'));
 }
 if(result.action!=='overview'&&result.total_source_rows!==undefined)panel.append(kv({'원본 행 수':result.total_source_rows,'저장 샘플 행 수':result.saved_sample_rows,'저장 샘플 밖의 행 수':result.rows_outside_saved_sample}));
 if(result.profile_scope)panel.append(el('p',({'saved_bounded_database_sample':'관측 범위: 저장된 DB 샘플. 원본 DB 질의를 새로 실행하지 않았으며, 표 전체의 유일성이나 부재를 판단할 수 없습니다.','complete_uploaded_csv':'관측 범위: 업로드한 CSV. 열 값의 유일성이 업무 식별자라는 뜻은 아닙니다.','document_not_tabular':'문서 구조의 개요입니다. 이 탐색은 문서 본문을 읽은 결과가 아닙니다.'})[result.profile_scope]||result.profile_scope,'muted'));
 if(result.unfiltered_items!==undefined&&(result.name_filter||result.review_status_filter))panel.append(el('p',`필터 전 ${result.unfiltered_items}개 · 이름 포함 조건: ${result.name_filter||'없음'} · 검토 상태: ${result.review_status_filter||'전체'} · 조건에 맞는 ${result.total_items}개`,'muted'));
 if(result.total_items!==undefined)panel.append(el('p',`전체 ${result.total_items}개 중 ${result.returned_count??0}개 반환 · 이 응답에 없는 항목 ${result.omitted_items??'미확인'}개 · 시작 위치 ${result.offset??0}${result.next_offset!==null&&result.next_offset!==undefined?' · 다음 위치 '+result.next_offset:''}`,'muted'));
 if(result.truncated)panel.append(el('p','일부 자료·필드·샘플만 반환했습니다. 표시되지 않은 항목이 없다는 뜻은 아닙니다.','muted'));
 panel.append(detail('탐색 범위·출처·샘플 원본 기록',result));return panel;
}
function questionResult(op){
 if(op.result?.mode==='database_question')return databaseQuestionResult(op);
 const r=op.result||{},card=el('article',undefined,'card question-answer');card.append(el('h3',op.request.question),badge(op.state),el('p',`자료 버전 ${op.revision} · ${op.revision===state.current.revision?'현재 선택한 버전':'과거 버전의 결과'} · ${r.model||'모델 실행 정보 없음'}`,'muted'));
 if(r.answer)card.append(answerNode(r.answer));
 if(op.error)card.append(operationError(op.error));
 if(r.failure?.kind==='context_limit')card.append(el('p',`${r.failure.phase==='answering'?'조회 결과를 답변으로 작성':'질문에 사용할 조회를 선택'}하기 전에 입력 크기 한도를 넘었습니다 (${r.failure.message_bytes.toLocaleString()} / ${r.failure.limit_bytes.toLocaleString()}바이트). 이 단계의 모델 요청은 보내지 않았습니다. ${r.failure.phase==='answering'?'조회한 근거는 아래에서 확인할 수 있습니다. 조회 대상이 줄어들도록 질문을 구체화할 수 있지만 입력 한도 내 실행을 보장하지는 않습니다.':'조회 목록 자체가 큰 경우 질문을 짧게 바꿔도 해결되지 않습니다. 모델 조회는 시작하지 않았습니다. 질문 화면의 원본 열로 행 찾기를 이용해 필요한 기록을 직접 확인하세요.'} 새 질문 실행은 새 모델 호출을 사용할 수 있습니다. 동일 요청 기록 확인은 모델을 다시 호출하지 않습니다.`,'callout'));
 if(r.requirement_resolutions?.length)card.append(requirementResolutionReview(r));
 if(r.unresolved?.length){card.append(el('h4','아직 답하지 못한 요구'));const list=el('ul');r.unresolved.forEach(text=>list.append(el('li',text)));card.append(list,button('자료 준비와 지원 범위 보기',openPreparationGuide),el('p',`표시 중인 자료 버전 ${state.current.revision}의 준비 안내를 엽니다. 위 저장된 답변의 버전과 요구 해석은 바꾸지 않습니다.`,'muted'));}
 card.append(el('p','모델의 해석과 답변은 별도 검토가 필요합니다. 근거 ID 일치나 제약 통과가 답변의 사실성을 보증하지 않습니다.','muted'));
 const evidenceTargets=[];card.append(questionEvidenceGraph(op,evidenceTargets));
 for(const evidence of r.evidence||[]){const block=el('details');evidenceTargets.push(block);block.append(el('summary',`${evidence.id} · ${evidence.tool} · ${labels[evidence.state]||evidence.state}${r.citations?.includes(evidence.id)?' · 답변에서 참조':''}`));
  block.append(el('p',evidence.parameter_origin==='model_selected_source_binding'?'모델이 앞선 조회의 열을 선택하고, 그 결과에서 확인한 값을 다음 조회에 전달했습니다.':evidence.parameter_origin==='model_interpretation'?'조회 조건은 모델이 질문을 해석해 선택했습니다. 사용자가 각 값을 확인한 것은 아닙니다.':'이 기록에는 조회 조건의 출처가 별도로 저장되지 않았습니다. 실행 요청을 확인하세요.','muted'),detail('사용한 조회 조건',evidence.arguments||{}));
  if(evidence.binding||evidence.failure_kind==='unresolved_binding')block.append(questionBinding(evidence));
  if(evidence.error)block.append(el('p',evidence.error,'callout'));
  const result=evidence.result;if(result?.mode==='repository_exploration'){block.append(repositoryExplorationResult(result));}else if(result?.mode==='source_document'){block.append(el('p','승인한 문서 원문 · 정책 적용 여부는 확인하지 않았습니다.','callout'),el('p',result.source.text,'source-quote'),el('p',`${result.source.file} · 원문 ${result.source.line_start}–${result.source.line_end}행`,'muted'),detail('검토한 해석 · 날짜 역할',result.review));}else if(result?.mode==='source_lookup'){block.append(el('p',result.notice),reviewedFieldMeaning(result));for(const record of result.records)block.append(table(['필드','원본 값'],Object.entries(record.values)),el('p',`${record.source.file} · CSV 레코드 ${record.record}`,'muted'));}
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
  else if(result?.mode==='query_catalog'){
   block.append(el('h4','조회 도구 목록 탐색'),el('p','조회 조건을 선택하기 위한 목록입니다. 원본 조회나 정책·제약 검사를 실행한 결과가 아닙니다.','muted'),kv({'도구':result.tool,'전체 항목':result.total,'반환 항목':result.items?.length??0,'시작 위치':result.offset,'다음 위치':result.next_offset??'없음','이후 미반환 항목':result.omitted_count}),detail('저장된 조회 도구 설명',result.items||[]));
   if(result.oversized_descriptor)block.append(el('p','도구 설명이 크기 한도를 넘어 반환되지 않았습니다.','muted'));
  }else if(result){block.append(detail('조회한 근거',result.facts||result.evidence||result));if(result.shacl)block.append(detail('제약 검토',result.shacl));if(result.owl)block.append(detail('분류·추론',result.owl));}
  block.append(detail('실행 요청과 원본 기록',evidence));card.append(block);
 }
 card.append(button('이 질문의 저장된 실행 확인',()=>task(()=>openSavedOperation(state.current.id,op.id))),detail('실행 단계·모델 응답·자료 연결',r));return card;
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
function reviewNavigation(entryIds=[]){return button(entryIds.length?'해당 항목 검토':'데이터 정리로 이동',()=>{state.tab='review';render();const target=[...document.querySelectorAll('[data-review-id]')].find(n=>entryIds.includes(n.dataset.reviewId));if(target){for(let node=target.parentElement;node;node=node.parentElement)if(node.tagName==='DETAILS')node.open=true;target.querySelector('select,input,textarea,button')?.focus();target.scrollIntoView({block:'center'});}else document.querySelector('[data-tab="review"]')?.focus();});}
function operationError(error){
 const box=el('div',undefined,'callout');
 const messages={
  'Review the source column before querying its rows':'이 실행에서 선택한 열은 승인된 조회 대상이 아닙니다. 현재 자료의 열 의미와 승인 상태를 확인한 뒤 새로 조회하세요.',
  'Approve exactly one identifier field for this table first':'조회할 자료의 식별자 연결이 확정되지 않았습니다. 데이터 정리에서 해당 ID 필드 연결을 확인하세요.'
 };
 const bindingFailure=typeof error==='string'?error.match(/unresolved_binding:([^:]+):(absent|multiple|null_value|invalid_type)/):null;
 if(bindingFailure){box.append(el('p',`단일 값 선택 실패 · ${bindingFailure[1]}: ${{absent:'일치하는 행이 없습니다.',multiple:'일치하는 행이 둘 이상입니다.',null_value:'선택한 값이 NULL입니다.',invalid_type:'선택한 값의 자료형이 정의와 다릅니다.'}[bindingFailure[2]]}`),el('p','질의 결과를 구하지 못했습니다. 조건에 맞는 결과가 0건이라는 뜻이 아닙니다.'),detail('원래 오류 기록',error));}
 else if(Object.hasOwn(messages,error))box.append(el('p',messages[error]),reviewNavigation(),detail('원래 오류 기록',error));
 else box.append(el('p',error));
 return box;
}
function taskReadinessPanel(){
 const report=state.current.task_readiness;if(!report)return el('div');
 const card=el('article',undefined,'card');card.dataset.testid='task-readiness-summary';
 card.append(el('h3','현재 자료로 할 수 있는 일'));
 const labels={source_rows:'승인한 열로 원본 행 찾기',source_document:'승인한 문단 읽기',relation_rows:'승인한 관계의 양쪽 자료 대조',stock_check:'기록된 재고와 요청 수량 비교'};
 for(const [key,label] of Object.entries(labels)){const count=report.capabilities[key]||0;card.append(el('p',`${label} · ${count?`${count}개 조회 범위 준비됨`:'먼저 관련 자료를 승인하세요'}`));}
 card.append(el('p','조회 범위가 준비되어도 원하는 값이 없거나 모호할 수 있습니다. 문단 조회는 정책 적용 여부를 검사하지 않습니다.','muted'));
 if(report.replacement){const replacement=report.replacement,details=el('details');
 details.append(el('summary',replacement.issues.length?`대체 상품 검토 · 준비 항목 ${replacement.issues.length}건 확인`:'대체 상품 검토 · 실행 시 값과 참조 확인 필요'));
 details.append(el('p','대체 상품 검토는 정해진 주문·상품·재고·정책 구조를 요구합니다. 아래 안내만으로 변경안이 승인되거나 실행되지는 않습니다.','muted'));
 const codes={currency:'현재 변경안 계산은 KRW만 지원',pending:'승인 또는 제외할 항목',policy_missing:'해석·승인이 필요한 정책',policy_multiple:'적용할 원문을 선택할 정책',field_missing:'연결·승인이 필요한 필드',field_multiple:'중복 연결을 정리할 필드',collection_split:'한 CSV로 준비해야 하는 자료 묶음',policy_scope:'정책의 날짜·적용 범위 확인',policy_agreement:'정책과 계산 기준 대조'};
 const list=el('ul');for(const issue of replacement.issues){const title=Object.hasOwn(codes,issue.code)?codes[issue.code]:issue.code;const item=el('li',`${title}: ${issue.subject}${issue.entry_ids.length?` (${issue.entry_ids.length}개 항목)`:''}`);if(issue.entry_ids.length)item.append(reviewNavigation(issue.entry_ids));list.append(item);}details.append(list,reviewNavigation());
 details.append(el('p','입력 값 형식, 식별자 중복, 자료 간 참조와 선택한 변경안은 실행할 때 다시 검사합니다. 원본의 진실성과 완전성은 보장하지 않습니다.','muted'));card.append(details);
 }
 return card;
}
function chatTurnIds(id,runs=state.current.operations){
 state.chatSessions??=new Map();
 if(!state.chatSessions.has(id))state.chatSessions.set(id,runs.filter(o=>o.kind==='question').slice(0,3).map(o=>o.id));
 return state.chatSessions.get(id);
}
function includeChatTurn(id,operationId){const ids=chatTurnIds(id);if(!ids.includes(operationId))ids.push(operationId);if(ids.length>6)ids.splice(0,ids.length-6);}
async function hydrateChatTurns(row){
 const ids=chatTurnIds(row.id,row.operations),missing=row.operations.filter(o=>o.kind==='question'&&o.summary_only&&ids.includes(o.id)).slice(0,6);
 // The local server serializes even read-only operations under one lock.
 for(const op of missing){try{const full=await api({action:'operation',id:row.id,operation_id:op.id});if(full.id===op.id){const at=row.operations.findIndex(o=>o.id===op.id);if(at>=0)row.operations[at]=full;}}catch{/* Keep the summary and explicit load button; never retry automatically. */}}
}
function chatTurn(op){
 const turn=el('article',undefined,'chat-turn');turn.dataset.chatTurn=op.id;
 const user=el('section',undefined,'chat-message chat-user');user.setAttribute('aria-label','내 질문');user.append(el('div','나','chat-role'),el('p',op.request?.question||op.result?.question||'저장된 질문','chat-user-text'));
 const assistant=el('section',undefined,'chat-message chat-assistant');assistant.setAttribute('aria-label','자료실 답변');assistant.append(el('div','자료실','chat-role'));
 if(op.summary_only){assistant.append(el('p','저장된 답변을 불러와 확인하세요.','muted'),button('답변 불러오기',()=>task(()=>openSavedOperation(state.current.id,op.id))));}
 else{
  const result=op.result||{};
  const meta=el('div',undefined,'chat-answer-meta');meta.append(el('span',`자료 버전 ${op.revision}${op.revision!==state.current.revision?' · 과거 버전':''}`),badge(op.state));assistant.append(meta);
  if(result.answer)assistant.append(answerNode(result.answer));
  else if(op.error)assistant.append(operationError(op.error));
  else assistant.append(el('p',op.state==='completed'?'이 실행에는 저장된 답변이 없습니다. 근거와 실행 기록을 확인하세요.':'답변이 완료되지 않았습니다. 실행 기록에서 상태와 남은 근거를 확인하세요.','muted'));
  if(result.unresolved?.length){const unresolved=el('details',undefined,'chat-unresolved');unresolved.append(el('summary',`답하지 못한 항목 ${result.unresolved.length}개`));const list=el('ul');for(const item of result.unresolved)list.append(el('li',item));unresolved.append(list);assistant.append(unresolved);}
  const evidenceCount=result.evidence?.length||0,citationCount=result.citations?.length||0;
  const trace=el('details',undefined,'chat-trace');trace.append(el('summary',`근거 ${evidenceCount}개 · 참조 ${citationCount}개 · 검토·실행 상세`));
  // Reuse the original record renderer unchanged: raw answer, errors, validation,
  // graph, source scope and historical identifiers remain inspectable here.
  trace.append(operationCard(op));assistant.append(trace);
 }
 turn.append(user,assistant);return turn;
}
function fitChatViewport(){
 const shell=document.querySelector('.chat-shell');if(!shell)return;
 const top=shell.getBoundingClientRect().top+window.scrollY;
 shell.style.height=Math.max(360,window.innerHeight-top-12)+'px';shell.style.minHeight='0';
}
window.addEventListener('resize',fitChatViewport);
function renderConversation(root,runs){
 const questions=runs.filter(o=>o.kind==='question'),ids=chatTurnIds(state.current.id,runs),visible=questions.filter(o=>ids.includes(o.id)).sort((a,b)=>a.created===b.created?a.id.localeCompare(b.id):(a.created<b.created?-1:1));
 const shell=el('section',undefined,'chat-shell');shell.dataset.testid='chat-conversation';
 const toolbar=el('div',undefined,'chat-toolbar');toolbar.append(el('span','내 자료와 대화','chat-toolbar-title'));
 const reset=button('새 대화',()=>{if(state.chatPending||state.busy)return;if(!canLeave())return;const draftKey='operations-question-draft-'+state.current.id;if(recalled(draftKey)?.trim()&&!window.confirm('작성 중인 질문을 비우고 새 대화를 시작할까요? 저장된 실행 기록은 남습니다.'))return;remember(draftKey,null);state.chatSessions.set(state.current.id,[]);render();document.querySelector('.question-composer textarea')?.focus();});submissionControl(reset,false);toolbar.append(reset);shell.append(toolbar);
 const thread=el('div',undefined,'chat-thread');thread.setAttribute('aria-label','질문과 답변');
 if(!visible.length&&!state.chatPending){const empty=el('div',undefined,'chat-welcome');empty.append(el('div','자료에서 답을 찾아보세요.','chat-welcome-title'),el('p','어떤 자료가 있는지 묻거나, 확인할 대상과 조건을 적어주세요.'));thread.append(empty);}
 for(const op of visible)thread.append(chatTurn(op));
 if(state.chatPending?.workspace===state.current.id){const pending=el('article',undefined,'chat-turn chat-pending');const user=el('section',undefined,'chat-message chat-user');user.append(el('div','나','chat-role'),el('p',state.chatPending.question,'chat-user-text'));const assistant=el('section',undefined,'chat-message chat-assistant');assistant.append(el('div','자료실','chat-role'));const live=el('div',undefined,'chat-live');live.setAttribute('role','status');live.append(el('span',undefined,'chat-spinner'),el('span','질문을 접수하고 있습니다.','chat-live-label'));assistant.append(live);pending.append(user,assistant);thread.append(pending);}
 shell.append(thread,questionForm());root.append(shell);state.chatLayoutObserver?.disconnect();state.chatLayoutObserver=new ResizeObserver(()=>fitChatViewport());for(const node of [$('chat-context'),$('notice'),$('request-recovery'),document.querySelector('.sidebar')])if(node)state.chatLayoutObserver.observe(node);requestAnimationFrame(()=>{fitChatViewport();if(thread.isConnected&&!thread.contains(document.activeElement))thread.scrollTop=thread.scrollHeight;});
 if(recalled('operations-request-'+state.current.id))root.append(el('p','요청 복구에서 서버 상태를 먼저 확인하세요. 자동으로 다시 전송하지 않습니다.','callout'));
 const older=runs.filter(op=>!ids.includes(op.id)),history=el('details',undefined,'card run-history');history.open=state.historyOpen?.get(state.current.id)||false;history.addEventListener('toggle',()=>{if(history.isConnected)setHistoryOpen(history.open);});
 history.append(el('summary',`저장된 질문·실행 기록 · 불러온 ${older.length}개`));for(const op of older)history.append(operationCard(op));appendHistoryMore(history);if(older.length||state.current.operations_next)root.append(history);
}
function renderQuestions(root){
 renderConversation(root,state.current.operations.filter(op=>op.kind!=='model_suggestions'));
 const readiness=el('details',undefined,'card readiness-disclosure');readiness.append(el('summary','조회 준비 상태와 필요한 자료'),taskReadinessPanel());root.append(readiness);
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
 if(pending)templates.append(el('p',`검토할 항목이 ${pending}개 남았습니다. 데이터 정리에서 승인 또는 제외한 뒤 실행하세요.`,'callout'));if(!cases.length)templates.append(el('div',state.current.draft.adapter==='commerce-csv-1'?'저장된 예제 질문이 없습니다. 직접 조회 · 변경안 검토에서 질문 파일 없이 조회하거나 변경안을 검토할 수 있습니다.':'저장된 예제 질문이 없습니다. 자료의 질문 항목을 확인하거나 직접 조회 도구를 이용하세요.','empty'));for(const c of cases){const card=el('article',undefined,'card');card.append(el('h3',c.label||c.id),el('p',c.question||'질문 내용 없음'),el('p',`질문 ID: ${c.id} · 자료 버전 ${state.current.revision}`,'muted'));const run=button('이 질문 실행',()=>execute(c.id,crypto.randomUUID()),'primary');submissionControl(run,!mutable()||pending>0||state.current.readiness?.ready===false);card.append(run);templates.append(card);}if(cases.length&&!Array.isArray(state.current.cases))templates.append(el('p','승인한 CSV 연결에서 읽은 질문 목록입니다. 전체 자료의 실행 가능 여부는 실행 시 서버가 검사합니다.','muted'));
 root.append(templates);
}
async function withdrawPending(record){
 if(record.status.state!=='not_recorded'||record.generation&&!recoveryPayload(record).draft_digest)return;
 if(!window.confirm('접수되지 않은 원래 요청을 철회할까요? 이미 실행 중이면 취소하지 않고 현재 상태를 표시합니다.'))return;
 await task(async()=>{
  const response=await api({action:'withdraw_pending',id:record.id,revision:record.request.revision,request_key:record.request.request_key,kind:recoveryKind(record),request:recoveryPayload(record)});
  acceptRecoveryStatus(record,response.operation);announceRecovery(record);renderRecovery();
 });
}
async function execute(caseId,requestKey,revision=state.current.revision,proposal=null,selection=null){if(!canLeave())return;await task(async()=>{try{const key='operations-request-'+state.current.id;const pending=recalled(key);assertRequestAllowed(key,requestKey);if(!pending)remember(key,JSON.stringify({revision,request_key:requestKey,case_id:caseId,proposal,selection}));collectRecovery(state.current.id);renderRecovery();const response=await api(selection?{action:'lookup',id:state.current.id,revision,request_key:requestKey,selection}:proposal?{action:'propose',id:state.current.id,revision,request_key:requestKey,proposal}:{action:'execute',id:state.current.id,revision,request_key:requestKey,case_id:caseId});resolveSubmitted(key,requestKey,response.operation);await showExecution(response.operation);$('notice').textContent=response.reused?'동일한 요청의 기존 실행 기록을 불러왔습니다.':'실행 기록을 저장했습니다.';}catch(error){/* An error does not establish whether an earlier same-key request committed. */render();throw error;}});}
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
function invocationAssociationResult(op){
 const card=el('article',undefined,'card'),r=op.result||{};
 card.append(badge(op.state),el('h3','외부 실행과 가져온 제안의 출처 연결'),el('p',`버전 ${op.revision} · ${new Date(op.created).toLocaleString('ko-KR')}`,'muted'));
 card.append(el('p',r.local_source_link_verified?'운영자가 보관한 실행 기록과 현재 원본·내보내기 파일의 일치를 확인했습니다.':'원본과 외부 실행 기록의 연결을 확인하지 못했습니다.','callout'));
 card.append(el('p','이 기록은 제안의 정확성이나 사람의 승인을 뜻하지 않습니다. 공급자의 신원 인증과도 별개입니다.','muted'));
 card.append(kv({'연결 상태':r.status||op.state,'원본 식별자':r.source_id||'미확인','원본 해시':r.source_sha256||'미확인','내보내기 해시':r.export_sha256||'미확인'}));
 const original=r.import_operation_id||op.request?.import_operation_id;
 if(original)card.append(button('가져온 제안 열기',()=>task(()=>openSavedOperation(state.current.id,original))));
 if(op.error)card.append(operationError(op.error));
 card.append(detail('연결 검사와 원본 실행 기록',r),detail('저장된 요청',{id:op.id,request_key:op.request_key,request:op.request}));
 return card;
}
function operationCard(op){const card=operationContent(op);card.dataset.operationId=op.id;card.tabIndex=-1;return card;}
function operationContent(op){if(op.kind==='database_source_query'&&!op.summary_only){const card=el('article',undefined,'card');card.append(el('h3','승인한 열의 조건 조회'),badge(op.state));if(op.error)card.append(operationError(op.error));card.append(detail('원본 버전·조회 조건·반환 행',op.result||{}));return card;}if(op.kind==='extension_localize'){const card=el('article',undefined,'card');card.append(el('h3','한국어 번역 초안'),badge(op.state));if(op.error)card.append(operationError(op.error));if(op.result)card.append(el('p','번역 초안만 저장했습니다. 원본 제안과 기존 승인은 바꾸지 않았습니다. 같은 버전의 비교 표에서 확인하세요.'),detail('번역·모델·원본 연결',op.result));return card;}if(['database_shapes_propose','database_shapes_validate'].includes(op.kind))return databaseShapesOperation(op);if(op.kind==='extension_generation')return nativeGenerationCard(op);if(op.summary_only){const card=el('article',undefined,'card operation-summary');const names={extension_invocation_association:'외부 실행의 출처 연결',database_question_scope:'미해결 질문 · 운영자 판단',database_external_relation_propose:'외부 후보의 관계 제안',database_external_relation_reject:'외부 관계 후보 선택 제외',local_reasoning:'업로드한 RDF의 로컬 추론',extension_import:'외부 온톨로지 제안',extension_review:'외부 제안의 사람 승인',question:'자유 질문',source_lookup:'원본 조회',model_suggestions:'자료 해석 제안',replacement_proposal:'주문 변경안',fixed_case:'예제 질문'};card.append(badge(op.state),el('h3',names[op.kind]||op.kind),el('p',`버전 ${op.revision} · ${new Date(op.created).toLocaleString('ko-KR')}`,'muted'));if(op.error)card.append(operationError(op.error));card.append(button('결과와 근거 열기',()=>task(async()=>{const full=await api({action:'operation',id:state.current.id,operation_id:op.id});if(state.tab==='questions')setHistoryOpen(true);retainOperation(full);render();focusOperation(full.id);})));return card;}if(op.kind==='extension_invocation_association')return invocationAssociationResult(op);if(reviewedActions.has(op.kind))return reviewedOperation(op);if(op.kind==='source_lookup'&&(op.result?.source_version||isDatabaseWorkspace()))return databaseLookupResult(op);if(op.kind==='local_reasoning')return reasoningResult(op);if(op.kind==='extension_import'||op.kind==='extension_review')return extensionResult(op);if(op.kind==='question')return questionResult(op);if(op.kind==='model_suggestions')return proposalResult(op);const card=el('article',undefined,'card');card.append(badge(op.state),el('h3',op.result?.question||op.request.case_id||(op.request.selection?.relation_id?'두 CSV의 같은 값 대조':null)||(op.request.selection&&Object.keys(op.request.selection).length===1&&'entry_id' in op.request.selection?'승인한 문단 조회':'주문 변경안 검토')),el('p',`버전 ${op.revision} · ${new Date(op.created).toLocaleString('ko-KR')}`,'muted'));if(op.state==='completed'&&op.result){const r=op.result;if(r.mode==='reviewed_relation_rows'){card.append(relationResult(r),button('동일 요청 기록 확인',()=>task(()=>openSavedOperation(state.current.id,op.id))));return card;}if(r.mode==='source_document'){card.append(el('p','승인한 문서 원문 · 정책 적용 여부는 확인하지 않았습니다.','callout'),el('p',r.source.text,'source-quote'),el('p',`${r.source.file} · 원문 ${r.source.line_start}–${r.source.line_end}행`,'muted'),detail('검토한 해석 · 날짜 역할',r.review),detail('조회 범위 · 출처',r),button('동일 요청 기록 확인',()=>task(()=>openSavedOperation(state.current.id,op.id))));return card;}if(r.mode==='source_lookup'){card.append(el('p',r.answer),el('p',r.notice,'callout'),el('p',`기준일 ${r.metadata.as_of} · 미검토 필드: ${r.unreviewed_fields.join(', ')||'없음'}`,'muted'));for(const record of r.records){card.append(table(['필드','원본 값'],Object.entries(record.values)),el('p',`${record.source.file} · CSV 논리 레코드 ${record.record}${record.source.line_start?' · 원문 '+record.source.line_start+'–'+record.source.line_end+'행':''}`,'muted'));}card.append(reviewedFieldMeaning(r),detail('조회 범위 · 출처',r),button('동일 요청 기록 확인',()=>task(()=>openSavedOperation(state.current.id,op.id))));return card;}card.append(answerNode(r.answer||'실행 완료'));if(r.calculations)card.append(kv({'변경 전 상품 금액':r.calculations.before_subtotal,'변경 후 상품 금액':r.calculations.after_subtotal,'할인':r.calculations.discount,'배송비':r.calculations.shipping_fee,'합계':r.calculations.total}));card.append(el('h3','1. 조회한 근거'));if(r.facts){for(const [name,fact] of Object.entries(r.facts)){const block=el('details');block.append(el('summary',name));if(Array.isArray(fact)){if(fact.length){const columns=Object.keys(fact[0]);block.append(table(columns,fact.map(row=>columns.map(k=>row[k]))));}else block.append(el('p','이 조회 범위에서 일치하는 기록이 없습니다.','muted'));}else block.append(kv(fact));card.append(block);}}if(r.evidence){for(const evidence of r.evidence){const rows=evidence.rows||[];card.append(el('p',`${evidence.tool||evidence.query_id||'선택 근거'} · ${rows.length}행`,'muted'));if(rows.length){const columns=Object.keys(rows[0]);card.append(table(columns,rows.map(row=>columns.map(k=>row[k]))));}}}card.append(el('h3','2. 제약 점검'));const checks=r.shacl?.checks;if(checks)card.append(table(['점검 항목','결과','관측 값 또는 제약 수'],checks.map(c=>[c.label||c.candidate||c.shape||'선택 근거 점검',labels[c.status]||c.status,Object.hasOwn(c,'value')?(c.value===null?'미확인':c.value):`${c.constraints?.length??0}개 제약 · ${c.results?.length??0}개 위반`])));if(r.owl){card.append(el('h3','3. OWL 분류'),el('p',`추가된 규칙 적용 결과 ${r.owl.inferred_count??0}개 · 직접 상위 분류 근거 ${r.owl.witnesses?.length??0}개`,'muted'));if(r.owl.witnesses?.length)card.append(table(['전제','적용 공리','결론'],r.owl.witnesses.map(w=>[w.premise.join(' '),w.axiom.join(' '),w.conclusion.join(' ')])));}card.append(el('p','자료 조회, 제약 점검, OWL 분류는 서로 다른 단계입니다. 제약 통과나 분류 결과가 원본의 사실성을 보증하지 않습니다.','muted'),detail('조회한 근거 · 원본 기록',r.facts||r.evidence||r.query),detail('제약 점검 · SHACL',r.shacl),detail('분류 결과 · OWL',r.owl),detail('자료 버전 · 실행 상세',r));}else if(op.error){card.append(operationError(op.error));}else card.append(el('p','서버의 실행 완료 여부를 확인하세요. 자동 재시도하지 않습니다.','muted'));const actions=el('div',undefined,'actions');actions.append(button('동일 요청 기록 확인',()=>task(()=>openSavedOperation(state.current.id,op.id))));if(['failed','interrupted','cancelled'].includes(op.state)){const retry=button('새 요청으로 다시 실행',()=>{if(window.confirm('실패 기록을 보존하고 현재 버전으로 새 요청을 실행할까요?'))execute(op.request.case_id,crypto.randomUUID(),state.current.revision,op.request.proposal,op.request.selection);});submissionControl(retry,!mutable());actions.append(retry);}card.append(actions,detail('요청 식별 정보',{id:op.id,request_key:op.request_key,revision:op.revision,request:op.request}));return card;}
function decisionDiff(changes){
 const box=el('section');box.append(el('h3','검토 내용 변경'));
 if(!changes.length){box.append(el('p','필드 연결·검토 상태·해석·메모 변경이 없습니다.','muted'));return box;}
 const fieldNames={target:'연결 또는 규칙',status:'검토 상태',interpretation:'해석·적용 범위',note:'메모',temporal:'날짜 역할'};
 const value=(d,f)=>{
  if(d==null)return '항목 없음';const v=d[f];
  if(v==null||v==='')return '(없음)';
  if(f==='status')return labels[v]||String(v);
  if(f==='target'&&!Array.isArray(v)&&typeof v==='object'&&typeof v.file==='string'&&typeof v.column==='string')return `${v.file} · ${v.column}`;
  return typeof v==='object'?JSON.stringify(v):String(v);
 };
 for(const c of changes){const card=el('article',undefined,'card');card.append(el('h4',`${c.source.file} · ${c.source.column||'문단 '+c.source.paragraph}`));
 if(c.kind==='relation')card.append(el('p','연결 후보에 대한 검토 기록입니다. 실행되는 조회 연결의 변경을 뜻하지 않습니다.','muted'));
 card.append(table(['항목','변경 전','변경 후'],c.changed_fields.map(f=>[fieldNames[f]||f,value(c.before,f),value(c.after,f)])));box.append(card);}
 return box;
}
function renderChanges(root){const w=state.current;heading(root,'자료 변경과 재검토','변경 전후 버전을 비교하고, 새로 확인할 항목을 살펴보세요.');const card=el('article',undefined,'card');const replacementHeading=el('h3','자료 묶음 교체');replacementHeading.dataset.preparationTarget='source_replacement';replacementHeading.tabIndex=-1;card.append(replacementHeading,el('p','새 원본 묶음을 저장하면 검토 상태를 다시 확인해야 합니다. 파일을 교체하려면 새 버전에 포함할 전체 묶음을 선택하세요. 묶음에서 빠진 파일은 새 버전에서 제거됩니다. 파일을 선택하지 않으면 기존 원문을 유지하고 기준 정보만 바꿉니다. 이전 원본과 실행 기록은 보존됩니다.','callout'));const files=input('','file');files.multiple=true;files.accept='.csv,.txt,.md';const snapshot=input(w.draft.metadata.snapshot_id),asof=input(w.draft.metadata.as_of,'date');snapshot.maxLength=80;const currency=input(w.draft.metadata.currency);currency.maxLength=14;currency.disabled=w.draft.adapter!=='commerce-csv-1';card.append(field('자료의 통화 · 3자리 코드 또는 unknown / mixed / not_applicable',currency));card.append(field('새 버전의 전체 파일 · 선택하지 않으면 기존 파일 유지',files),field('자료 버전 이름',snapshot),field('자료 기준일',asof));const refresh=button('교체 내용 확인',()=>task(async()=>{const selected=files.files.length?await readFiles(files):w.draft.sources.map(s=>({name:s.name,content:s.content}));previewRefresh(selected,{...w.draft.metadata,snapshot_id:snapshot.value,as_of:asof.value,currency:currency.value.trim()});}));refresh.disabled=!mutable();card.append(refresh);root.append(card);const compare=el('article',undefined,'card');compare.append(el('h3','버전 비교'));const options=w.versions.map(v=>[String(v.number),`버전 ${v.number} · ${new Date(v.created).toLocaleString('ko-KR')}`]);const before=select(options,String(w.versions[1]?.number||w.revision)),after=select(options,String(w.revision));const controls=el('div',undefined,'form-grid');controls.append(field('변경 전',before),field('변경 후',after));const output=el('div');compare.append(controls,button('차이 확인',()=>task(async()=>{const diff=await api({action:'diff',id:w.id,before:Number(before.value),after:Number(after.value)});output.replaceChildren(table(['구분','파일 또는 항목'],[['추가',diff.added.join(', ')||'없음'],['변경',diff.changed.join(', ')||'없음'],['제거',diff.removed.join(', ')||'없음'],['기준일',diff.metadata_before.as_of+' → '+diff.metadata_after.as_of],['자료 버전 이름',diff.metadata_before.snapshot_id+' → '+diff.metadata_after.snapshot_id],['통화',currencyLabel(diff.metadata_before.currency)+' → '+currencyLabel(diff.metadata_after.currency)],['재검토 필요',`${diff.review_required.length}개`]]),el('p','자료 변경에 따른 검토 범위를 보수적으로 잡습니다. 모든 원본 변경은 재검토 대상입니다.','muted'),decisionDiff(diff.decision_changes||[]),detail('재검토 항목과 과거 실행',diff));})),output);root.append(compare);const history=el('article',undefined,'card');history.append(el('h3','저장된 버전'));w.versions.forEach(v=>history.append(button(`버전 ${v.number} 열기 · ${new Date(v.created).toLocaleString('ko-KR')}`,()=>{if(canLeave())task(async()=>show(await api({action:'get',id:w.id,revision:v.number})));})));history.append(button('현재 버전으로 돌아가기',()=>{if(canLeave())task(async()=>show(await api({action:'get',id:w.id,revision:null})));}));root.append(history,detail('검토 결정 이력',w.draft.review_history||[]));}
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
registeredDatabaseStart();
document.querySelector('#welcome .hero h1').textContent='내 자료를 연결하고, 근거를 확인하세요.';
$('import-draft').onclick=()=>{if(!state.busy)openImport();};
$('area-repositories').onclick=()=>{if(!state.busy&&!hasPending())task(()=>navigateArea('repositories'));};
$('area-chat').onclick=()=>{if(!state.busy&&!hasPending())task(()=>navigateArea('chat'));};
$('chat-review-repository').onclick=()=>{if(!state.busy&&state.current&&canLeave())task(async()=>{const row=await api({action:'get',id:state.current.id,revision:null});state.area='repositories';state.tab='review';remember('operations-library-tab','review');await show(row);});};
$('chat-repository-select').onchange=()=>{const id=$('chat-repository-select').value;if(state.busy||hasPending()||!canLeave()){renderChatPicker();return;}task(async()=>{try{if(id){const row=await api({action:'get',id,revision:null});state.area='chat';state.tab='questions';await show(row);}else{state.current=null;remember('operations-chat-repository',null);$('content').replaceChildren();}}finally{applyArea();}});};
$('new').onclick=()=>{if(state.busy||hasPending()||!canLeave())return;state.edited=false;state.current=null;state.area='repositories';state.tab='library';remember('operations-workspace-id',null);remember('operations-library-repository',null);applyArea();$('welcome').hidden=false;$('workspace').hidden=true;$('notice').textContent='';};
$('reload').onclick=()=>task(list);$('archived').onchange=()=>{repositorySelection.clear();task(list);};
$('manage-workspaces').onclick=()=>{repositoryManaging=!repositoryManaging;renderRepositoryList();};$('repository-search').oninput=renderRepositoryList;
for(const domain of ['commerce','factory'])$(domain+'-example').onclick=()=>task(async()=>{state.area='repositories';state.tab='library';await show(await api({action:'example',domain}));});
$('create').onsubmit=e=>{e.preventDefault();task(async()=>{const domain=$('domain').value;state.tab='library';await show(await api({action:'create',title:$('title').value,domain,files:await readFiles($('files')),metadata:{snapshot_id:$('snapshot').value,as_of:$('asof').value,currency:domain==='commerce'?$('currency').value.trim():'not_applicable'}}));});};
$('export').onclick=()=>task(async()=>download(await api({action:'export',id:state.current.id,revision:state.current.revision})));
$('archive').onclick=()=>{if(!canLeave())return;task(async()=>{const archived=!Boolean(state.current.archived);await show(await api({action:'archive',id:state.current.id,archived}));$('archived').checked=archived;await list();});};
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{if(state.busy)return;state.tab=b.dataset.tab;render();});
window.addEventListener('beforeunload',e=>{if(state.edited||extensionVolatile()||(state.current&&reviewedDirty())){e.preventDefault();e.returnValue='';}});
task(async()=>{
 const r=await fetch('/api/config');if(!r.ok)throw Error('서버에 연결할 수 없습니다. 페이지를 다시 열어 주세요.');state.csrf=(await r.json()).csrf;
 state.area=recalled('operations-area')==='chat'?'chat':'repositories';state.tab=state.area==='chat'?'questions':'library';applyArea();const id=recalled(state.area==='chat'?'operations-chat-repository':'operations-library-repository')||recalled('operations-workspace-id'),records=collectRecovery(id);renderRecovery();
 if(records.length){$('welcome').hidden=true;for(const record of records)if(!record.malformed)await readRecovery(record);
  if(records.some(record=>record.malformed||['unknown','running'].includes(record.status.state))){$('workspaces').append(el('p','요청 상태를 먼저 확인하세요.','muted'));return;}
 }
 if(id){await show(await api({action:'get',id,revision:null}));for(const record of records)await prepareRecoveryDigest(record);renderRecovery();}else await list();
});

const compactNavigation=window.matchMedia('(max-width:700px)');
function adaptNavigation(){ $('workspace-navigation').open=!compactNavigation.matches; }
compactNavigation.addEventListener('change',adaptNavigation);adaptNavigation();

function nativeGenerationCard(op){
 const r=op.result||{},mode=r.mode||op.request?.mode,card=el('article',undefined,'card');
 card.append(badge(op.state),el('h3',mode==='catalog'?'NVIDIA · 카탈로그 실행 기록':'NVIDIA · 의미 생성 실행 기록'),el('p',`버전 ${op.revision} · ${new Date(op.created).toLocaleString('ko-KR')}`,'muted'));
 if(op.summary_only){card.append(button('실행 결과와 출처 열기',()=>task(()=>openSavedOperation(state.current.id,op.id))));return card;}
 const a=r.native_model_execution;
 if(mode==='semantic'&&(!a||a.internal_model_error_observed||!(a.new_provider_attempts||a.new_cache_hits)))card.append(el('p','이 실행의 모델 작업이 확인되지 않았거나 내부 호출 오류가 있습니다. upstream의 완료 반환이나 내보낸 파일만으로 LLM 생성 성공을 판단하지 않습니다.','callout'));
 else if(a)card.append(el('p',`이번 실행에서 새 공급자 요청 ${a.new_provider_attempts}회 · 저장 응답 재사용 ${a.new_cache_hits}회. 생성 결과는 승인 대기입니다.`,'callout'));
 else card.append(el('p','스키마 메타데이터를 가져온 실행입니다. LLM 의미 생성은 수행하지 않습니다.','callout'));
 if(op.error)card.append(operationError(op.error));
 if(r.import_operation_id)card.append(button('가져온 제안 검토',()=>task(()=>openSavedOperation(state.current.id,r.import_operation_id))));
 card.append(detail('실행 범위 · 원본과 공급자 출처',r));return card;
}

document.addEventListener('factory-review-open',event=>{const detail=event.detail;if(!detail||typeof detail.workspace!=='string'||typeof detail.operation!=='string'||!canLeave())return;task(async()=>{state.area='repositories';await show(await api({action:'get',id:detail.workspace,revision:null}));await openSavedOperation(detail.workspace,detail.operation);});});
