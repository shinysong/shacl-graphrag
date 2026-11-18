'use strict';
const $=id=>document.getElementById(id);
let token='', session=null, busy=false, lastResult=null;
function node(tag,text){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;}
function lock(value){busy=value;document.querySelectorAll('button').forEach(b=>b.disabled=value);$('status').textContent=value?'처리 중…':'';}
async function api(body){const r=await fetch('/api/preparation',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':token},body:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw Error(data.error||'처리에 실패했습니다.');return data;}
async function task(fn){if(busy)return;lock(true);$('error').textContent='';try{await fn();}catch(e){$('error').textContent=e.message;}finally{try{await sessions();}catch(e){$('error').textContent=e.message;}lock(false);}}
async function files(){const selected=[...$('files').files];if(!selected.length)throw Error('자료 파일을 선택하세요.');if(selected.length>24||selected.reduce((n,f)=>n+f.size,0)>4000000||selected.some(f=>f.size>1000000))throw Error('파일 수 또는 크기 한도를 초과했습니다.');return Promise.all(selected.map(async f=>({name:f.name,content:new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(await f.arrayBuffer())})));}
function download(name,value){const u=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const a=node('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}
function clearResult(){lastResult=null;$('answer').textContent='';$('result').textContent='';$('export-result').hidden=true;}
function show(data){clearResult();session=data;$('adapter').value=data.draft.adapter;$('currency').value=data.draft.metadata.currency;$('case').value=data.draft.adapter==='commerce-csv-1'?'approval':'qualification';$('review').hidden=false;$('finish').hidden=false;render();}
function render(){
 const d=session.draft;const counts={};d.entries.forEach(e=>counts[e.status]=(counts[e.status]||0)+1);$('counts').textContent=JSON.stringify(counts);
 $('sources').textContent=JSON.stringify({generator:d.generator,metadata:d.metadata,sources:d.sources,ontology:d.ontology,review_history:d.review_history||[],retired_entries:d.retired_entries||[]},null,2);
 $('entries').replaceChildren();
 d.entries.filter(e=>e.kind===$('filter').value).forEach(e=>{
  const box=node('article');box.className='entry';box.append(node('h3',e.id),node('p',e.reason),node('pre',JSON.stringify({source:e.source,extraction:e.extraction,previous_decision:e.previous_decision},null,2)));
  let target;
  if(e.kind==='policy'){
   target=node('select');[['','선택 필요'],['context','문맥만 보존 — 실행 안 함'],['unsupported','지원하지 않는 정책'],...Object.keys(session.contracts).map(k=>[k,k])].forEach(([v,t])=>{const o=node('option',t);o.value=v;target.append(o);});target.value=e.target;
   const meaning=node('pre');const update=()=>meaning.textContent=JSON.stringify(session.contracts[target.value]||{notice:'실행되는 계약이 없습니다.'},null,2);target.onchange=update;update();box.append(meaning);
  }else{target=node('input');target.value=e.kind==='relation'?JSON.stringify(e.target):e.target;}
  const tl=node('label','연결할 필드 또는 실행 계약');tl.append(target);box.append(tl);
  const interpretation=node('textarea');interpretation.value=e.interpretation;const il=node('label','검토한 해석 · 적용 대상 · 예외 · 시점');il.append(interpretation);box.append(il);
  const note=node('textarea');note.value=e.note;const nl=node('label','검토 메모 · 제외 이유');nl.append(note);box.append(nl);
  const status=node('select');[['pending','검토 대기'],['approved','승인'],['excluded','제외'],['insufficient','정보 부족']].forEach(([v,t])=>{const o=node('option',t);o.value=v;status.append(o);});status.value=e.status;
  const sl=node('label','검토 상태');sl.append(status);box.append(sl);
  const save=node('button','이 항목 저장');save.onclick=()=>task(async()=>show(await api({action:'change',id:session.id,entry_id:e.id,status:status.value,target:e.kind==='relation'?JSON.parse(target.value):target.value,note:note.value,interpretation:interpretation.value})));box.append(save);$('entries').append(box);
 });
}
$('filter').onchange=()=>{if(session)render();};
$('example').onclick=()=>task(async()=>show(await api({action:'example',adapter:$('adapter').value})));
$('analyze').onclick=()=>task(async()=>show(await api({action:'analyze',adapter:$('adapter').value,files:await files(),metadata:{snapshot_id:$('snapshot').value,as_of:$('asof').value,currency:$('currency').value}})));
$('refresh').onclick=()=>task(async()=>show(await api({action:'refresh',id:session.id,files:await files()})));
$('approve-mappings').onclick=()=>task(async()=>{clearResult();if($('filter').value!=='mapping')throw Error('필드 매핑 목록에서 사용하세요.');const entries=session.draft.entries.filter(e=>e.kind==='mapping'&&e.target&&e.status==='pending');for(const e of entries)session=await api({action:'change',id:session.id,entry_id:e.id,status:'approved',target:e.target,note:'사용자가 정확 일치 매핑 목록을 승인함',interpretation:''});render();});
$('save').onclick=()=>task(async()=>download('approved-data-bundle.json',(await api({action:'freeze',id:session.id})).bundle));
$('execute').onclick=()=>task(async()=>{clearResult();lastResult=(await api({action:'execute',id:session.id,case_id:$('case').value})).result;$('answer').textContent=lastResult.answer;$('result').textContent=JSON.stringify(lastResult,null,2);$('export-result').hidden=false;});
$('close').onclick=()=>task(async()=>{await api({action:'close',id:session.id});session=null;clearResult();$('review').hidden=true;$('finish').hidden=true;$('result').textContent='';});
$('import').onchange=()=>task(async()=>{const f=$('import').files[0];if(!f||f.size>32000000)throw Error('번들 크기를 확인하세요.');show(await api({action:'import',bundle:JSON.parse(await f.text())}));});
fetch('/api/config').then(r=>r.json()).then(c=>{token=c.csrf;return sessions();}).catch(e=>$('error').textContent=e.message);

$('adapter').onchange=()=>{$('currency').value=$('adapter').value==='commerce-csv-1'?'KRW':'not_applicable';};
$('export-result').onclick=()=>{if(lastResult)download('prepared-execution.json',lastResult);};

$('entries').addEventListener('input',clearResult);
$('entries').addEventListener('change',clearResult);
$('case').addEventListener('input',clearResult);

async function sessions(){const data=await api({action:'list'});$('sessions').replaceChildren();for(const row of data.sessions){const o=node('option',row.metadata.snapshot_id+' · '+row.adapter);o.value=row.id;$('sessions').append(o);}if(session)$('sessions').value=session.id;}
$('resume').onclick=()=>task(async()=>{clearResult();show(await api({action:'get',id:$('sessions').value}));});
$('reload-sessions').onclick=()=>task(sessions);
