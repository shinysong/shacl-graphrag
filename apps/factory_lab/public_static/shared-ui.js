/* Shared deployment controls; original workspace owns data review and answers. */
(()=>{'use strict';let csrf='',running=false;
 const node=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
 async function request(path,body){const r=await fetch(path,{credentials:'same-origin',...(body?{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(body)}:{})});const d=await r.json();if(r.status===401){location.assign('/login');throw Error('다시 로그인하세요.');}if(!r.ok)throw Error(d.error||'요청을 완료하지 못했습니다.');return d;}
 const bar=node('section');bar.id='shared-bar';bar.setAttribute('aria-label','공유 테스트 설정');const quota=node('span','이용 한도 확인 중…');quota.className='shared-quota';bar.append(quota);document.querySelector('main').prepend(bar);
 const plugin=node('button','NVIDIA 의미 생성'),reasoner=node('button','OpenOntologies 추론'),logout=node('button','로그아웃');const tools=node('details');tools.className='shared-tools';const toolsSummary=node('summary','확장 도구');const toolMenu=node('div');toolMenu.className='shared-tool-menu';toolMenu.append(node('p','원본에서 의미를 제안하거나, 사실과 규칙으로 추론합니다.'),plugin,reasoner);tools.append(toolsSummary,toolMenu);const info=node('details');info.className='shared-info';info.append(node('summary','공유·이용 안내'),node('p','인증 사용자는 자료와 실행 기록을 공유합니다. 민감한 정보는 올리지 마세요. 하루 10회는 사람의 유료 실행 기준이며, 검증 실행 비용도 승인된 총 $20에 포함됩니다.'));logout.className='shared-logout';bar.append(tools,info,logout);
 const dialog=node('dialog');dialog.id='shared-plugin';dialog.setAttribute('aria-label','NVIDIA auto-ontology 실행');document.body.append(dialog);
 async function refresh(){const s=await request('/api/shared/status');quota.replaceChildren(node('strong',`오늘 사용 ${s.quota.count} / 10`),node('small','사람의 유료 실행 · 한국시간 자정 초기화'));quota.title='검증 실행은 하루 한도에서 제외하며 모든 호출 비용은 총 예산에 포함합니다.';return s;}
 logout.onclick=async()=>{if(!confirm('저장하지 않은 편집 내용이 있다면 먼저 저장하세요. 로그아웃할까요?'))return;await request('/api/shared/logout',{});location.assign('/login');};
 reasoner.onclick=async()=>{dialog.replaceChildren();const close=node('button','닫기');close.onclick=()=>dialog.close();dialog.append(close,node('h2','OpenOntologies · 실제 로컬 추론'),node('p','아래 예제는 M03이 정밀 절삭기이고, 정밀 절삭기가 설비의 하위 분류라는 두 전제로부터 M03이 설비라는 분류를 도출합니다. 업무 승인이나 원본 자료의 사실성 검증은 아닙니다.'));dialog.showModal();
  const out=node('section');out.setAttribute('aria-live','polite');dialog.append(out);
  try{const listing=await request('/api/workspace',{action:'list',archived:false});if(!listing.workspaces.length)throw Error('예제 자료실이나 내 자료실을 먼저 하나 만드세요.');const select=node('select');for(const w of listing.workspaces){const option=node('option',w.title);option.value=w.id;select.append(option);}const label=node('label','추론 기록을 저장할 자료실');label.append(select);dialog.insertBefore(label,out);
   const source=node('textarea');source.rows=7;source.value='@prefix ex: <https://example.org/factory/> .\n@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\nex:PrecisionCutter rdfs:subClassOf ex:Machine .\nex:M03 a ex:PrecisionCutter .';source.setAttribute('aria-label','입력 사실과 분류 공리 Turtle');dialog.insertBefore(source,out);
   const run=node('button','예제 사실과 공리로 추론 실행 · 모델 호출 없음');dialog.insertBefore(run,out);run.onclick=async()=>{run.disabled=true;out.replaceChildren(node('p','입력 보존 → 실제 추론기 실행 → 도출 결과 저장 중…'));try{const w=await request('/api/workspace',{action:'get',id:select.value,revision:null});const bytes=new TextEncoder().encode(source.value);if(bytes.length>65536)throw Error('입력은 64KB 이하로 줄여주세요.');let binary='';for(const b of bytes)binary+=String.fromCharCode(b);const result=await request('/api/workspace',{action:'local_reasoning',id:w.id,revision:w.revision,request_key:crypto.randomUUID(),asserted_base64:btoa(binary),profile:'rdfs'});out.replaceChildren(node('h3',`실행 상태: ${result.operation.state}`),node('p','원본 전제와 도출 결과는 별도로 보존됩니다. 자료실의 데이터 정리에서도 이 실행을 확인할 수 있습니다.'),node('pre',JSON.stringify(result.operation.result,null,2)));if(result.operation.error)out.append(node('p',result.operation.error));}catch(e){out.replaceChildren(node('p',e.message));}finally{run.disabled=false;}};
  }catch(e){out.replaceChildren(node('p',e.message));}
 };
 const pendingKey='factory-shared-extension-job';
 function reviewLink(summary,out){
  if(!summary?.operation_id||!summary.workspace)return;
  const button=node('button',summary.origin==='observed_native_semantic_generation'?'원본과 LLM 제안 비교 표 열기':'원본과 제안 비교 표 열기');button.dataset.testid='native-review-result';button.onclick=()=>{dialog.close();document.dispatchEvent(new CustomEvent('factory-review-open',{detail:{workspace:summary.workspace,operation:summary.operation_id}}));};out.append(button);
 }
 function proposalReceipt(summary,out){
  if(!summary)return;
  out.append(node('h3',summary.origin==='observed_native_semantic_generation'?'저장된 LLM 의미 초안':'저장된 외부 제안'),node('p',`원본 열 ${summary.physical_columns}개 · 의미 용어/개념 ${summary.semantic_concepts}개 · 관계 기록 ${summary.relation_candidates}개 (선언 FK ${summary.declared_relations} · 의미 관계 ${summary.semantic_relations}) · 미지원 ${summary.unsupported}개`),node('p','결과는 서버에 자동 저장됐습니다. 기존 열의 의미·승인·질문 조회는 아직 바꾸지 않았습니다. 비교 표에서 원본 값과 설명을 확인하고 필요한 열을 수정·승인하세요.'));
  reviewLink(summary,out);
 }
 function displayJob(job,out){
  const op=job.result?.operation,failed=['failed','interrupted'].includes(job.state)||op?.state==='failed',active=['queued','running'].includes(job.state);
  const noun=job.mode==='catalog'?'원본 카탈로그':'의미 초안';out.replaceChildren(node('h3',active?noun+' 처리 중':failed?'생성을 완료하지 못했습니다':noun+'을 저장했습니다'));
  if(active){const progress=node('progress');progress.setAttribute('aria-label','외부 의미 초안 생성 진행 중');out.append(progress);const stages={queued:'실행 접수',source_check:'원본·실행 조건 확인',native_processing:job.mode==='catalog'?'원본 스키마 카탈로그 읽는 중':'스키마·표본으로 외부 도구가 의미 초안 생성 중',saving_proposal:'생성 결과 보존·검토 대기 저장 중'};out.append(node('p',stages[job.stage]||'실행기 완료를 기다리는 중'),node('p','이 창을 닫아도 서버 실행은 계속됩니다. 다시 열면 같은 요청의 상태를 확인하며, 새 요청을 자동으로 보내지 않습니다.'));}
  if(job.error)out.append(node('p',job.error));if(op?.error)out.append(node('p',op.error));
  if(!active&&!failed){if(job.summary)proposalReceipt(job.summary,out);else if(op?.result?.import_operation_id){out.append(node('p','생성 결과는 검토 대기로 자동 저장됐습니다. 기존 의미와 조회에는 아직 적용하지 않았습니다.'));reviewLink({operation_id:op.result.import_operation_id,workspace:op.workspace},out);}}
  if(op)out.append(node('p',`저장된 실행 ID ${op.id} · ${op.state}`));
  if(job.result){const details=node('details'),summary=node('summary','출처·실행 결과 상세');details.append(summary,node('pre',JSON.stringify(job.result,null,2)));out.append(details);}
  if(!active){localStorage.removeItem(pendingKey);running=false;const reload=node('button','자료실 새로고침');reload.onclick=()=>location.reload();out.append(reload);}
 }
 async function poll(id,out){try{const job=await request('/api/shared/jobs/'+id);displayJob(job,out);await refresh();if(['running','queued'].includes(job.state))setTimeout(()=>poll(id,out),1500);}catch(e){out.replaceChildren(node('p',e.message),node('p','자동으로 다시 실행하지 않습니다. 외부 확장 실행 창을 다시 열어 저장된 상태를 확인하세요.'));running=false;}}
 async function openPlugin(preferredId){dialog.replaceChildren();const close=node('button','닫기');close.onclick=()=>dialog.close();dialog.append(close,node('h2','NVIDIA auto-ontology'),node('p','등록된 DB 스냅샷을 실제 upstream에 전달합니다. 카탈로그는 스키마 메타데이터만, 의미 생성은 표본·스키마를 외부 모델에 전달하며 유료 호출을 사용합니다. 문서 묶음은 이 확장의 입력이 아닙니다.'));
  const out=node('section');out.setAttribute('aria-live','polite');dialog.append(out);dialog.showModal();
  const pending=localStorage.getItem(pendingKey);if(pending){running=true;return poll(pending,out);}
  try{const s=await refresh();if(!s.auto_ontology.configured)throw Error('운영자가 NVIDIA 실행기를 아직 연결하지 않았습니다. 기존 파일 가져오기는 자료실에서 사용할 수 있습니다.');
   if(s.auto_ontology.unavailable_reason){const note=node('p',s.auto_ontology.unavailable_reason);note.setAttribute('role','status');dialog.insertBefore(note,out);}
   const budget=s.auto_ontology.budget;if(budget){const settled=budget.accounting==='settled';dialog.insertBefore(node('p',`${settled?'비용 사용·예약 합계':'내부 예약 누계'} $${budget.reserved_usd} / 한도 $${budget.reservation_cap_usd}. 다음 LLM 호출 최대 예약액 $${budget.next_chat_reservation_usd}. ${settled?'성공 응답의 비용이 확인되면 실제 비용만 남기고 예약 차액을 해제합니다. 실패·비용 미확정분은 예약을 유지합니다.':'전체 실행에 필요한 호출 수는 달라질 수 있습니다.'} 계정 잔액을 표시하는 값은 아닙니다.`),out);}
   const listing=await request('/api/workspace',{action:'list',archived:false}),select=node('select');let eligible=[];
   for(const item of listing.workspaces){const w=await request('/api/workspace',{action:'get',id:item.id,revision:null});if(w.draft?.adapter==='registered-database-1')eligible.push(w);}
   if(!eligible.length)throw Error('등록 DB로 만든 자료실이 없습니다. 자료실 시작 화면의 등록된 원본에서 먼저 자료실을 만드세요. CSV 자료실은 LLM 의미 초안 생성 기능을 따로 사용합니다.');
   for(const w of eligible){const o=node('option',w.title+' · 버전 '+w.revision);o.value=w.id;select.append(o);}if(eligible.some(w=>w.id===preferredId))select.value=preferredId;const field=node('label','실행할 DB 자료실');field.append(select);dialog.insertBefore(field,out);
   const showSaved=()=>{out.replaceChildren();proposalReceipt(eligible.find(w=>w.id===select.value)?.latest_extension,out);};select.addEventListener('change',showSaved);showSaved();
   for(const [mode,label]of[['catalog','스키마 카탈로그 가져오기 · 모델 호출 없음'],['semantic','LLM 의미 계층 생성 · 유료']]){const button=node('button',label);button.disabled=mode==='semantic'&&!s.auto_ontology.semantic_enabled;button.onclick=async()=>{if(running)return;if(!confirm('저장하지 않은 편집 내용은 먼저 저장하세요. 선택한 원본으로 새 외부 실행을 시작할까요?'))return;running=true;out.replaceChildren(node('h3','실행 접수 중'));const progress=node('progress');progress.setAttribute('aria-label','실행 요청 전송 중');out.append(progress);dialog.querySelectorAll('select,button').forEach(b=>{if(b!==close)b.disabled=true;});try{const w=eligible.find(w=>w.id===select.value),job=await request('/api/shared/extensions',{id:w.id,revision:w.revision,request_key:crypto.randomUUID(),mode});localStorage.setItem(pendingKey,job.id);await poll(job.id,out);}catch(e){running=false;out.replaceChildren(node('p',e.message));}};dialog.insertBefore(button,out);}
  }catch(e){out.replaceChildren(node('p',e.message));}
 };
 plugin.onclick=()=>openPlugin(null);
 document.addEventListener('factory-native-open',e=>openPlugin(e.detail?.workspaceId));
 (async()=>{try{const cfg=await request('/api/config');csrf=cfg.csrf;await refresh();setInterval(()=>refresh().catch(()=>{}),30000);}catch(e){quota.textContent=e.message;}})();
})();
