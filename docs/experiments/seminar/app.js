'use strict';
const payload = JSON.parse(document.getElementById('deck-data').textContent);
const slides = [...document.querySelectorAll('.slide')];
const select = document.getElementById('slide-select');
let current = 0, showNotes = false;
function go(index, updateHash=true){
  current=Math.max(0,Math.min(index,slides.length-1));
  slides.forEach((slide,i)=>{slide.hidden=i!==current;slide.querySelector('.speaker').hidden=!(showNotes&&i===current);});
  select.value=String(current);document.getElementById('progress').style.width=`${(current+1)/slides.length*100}%`;
  document.getElementById('prev').disabled=current===0;document.getElementById('next').disabled=current===slides.length-1;
  if(updateHash) history.replaceState(null,'',`#${current+1}`);
  window.scrollTo(0,0);
}
function hashIndex(){const n=Number(location.hash.slice(1));return Number.isInteger(n)&&n>=1&&n<=slides.length?n-1:0;}
function showCase(index){
  const record=payload.examples.mini_cases[index];
  document.getElementById('demo-input').textContent=JSON.stringify(record.input,null,2);
  const output={conforms:record.conforms,results:record.results.map(r=>({focusNode:r.focusNode.split('/').pop(),resultPath:r.resultPath.split('/').pop(),value:r.value,constraint:r.constraint}))};
  document.getElementById('demo-output').textContent=JSON.stringify(output,null,2);
  document.querySelectorAll('[data-case]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.case)===index)));
}
document.querySelectorAll('[data-case]').forEach(b=>b.onclick=()=>showCase(Number(b.dataset.case)));
if(document.getElementById('discount-demo'))showCase(0);
// These controls select stored local runner outputs; the browser runs no inference.
document.querySelectorAll('[data-saved-demo]').forEach(demo=>{
  const inference=demo.dataset.savedDemo==='inference';
  const records=payload.semantics[inference?'queries':'shape_cases'];
  const result=demo.querySelector('.saved-result');
  function showRecord(index){
    const record=records[index];
    result.replaceChildren();
    const table=document.createElement('table');
    const caption=table.createCaption();caption.textContent='저장된 실행 결과 · 브라우저에서 Python을 실행하지 않음';
    const header=table.createTHead().insertRow();
    ['항목','결과'].forEach(label=>{const cell=document.createElement('th');cell.scope='col';cell.textContent=label;header.append(cell);});
    const rows=inference?[
      ['조회 범위',record.mode],
      ['P1 a Component',record.P1_is_Component?'있음':'없음'],
      ['A1 a Assembly',record.A1_is_Assembly?'있음':'없음'],
      ['A1 hasPart P1',record.A1_hasPart_P1?'있음':'없음'],
      ['제조사 기록',record.manufacturer_recorded?'있음':'없음']
    ]:[['추가한 입력',record.added_fact],['conforms',String(record.conforms)],
       ['위반 조건',record.violations.map(v=>v.component).join(', ')||'없음'],
       ['현실의 사실 확인','미확인 (not_verified)']];
    const body=table.createTBody();
    rows.forEach(values=>{const row=body.insertRow();values.forEach((value,i)=>{const cell=document.createElement(i===0?'th':'td');if(i===0)cell.scope='row';cell.textContent=value;row.append(cell);});});
    result.append(table);
    demo.querySelectorAll('[data-record]').forEach(button=>button.setAttribute('aria-pressed',String(Number(button.dataset.record)===index)));
  }
  demo.querySelectorAll('[data-record]').forEach(button=>button.onclick=()=>showRecord(Number(button.dataset.record)));
  showRecord(0);
});
// HTML only reveals outputs already executed and stored in the shared notebook.
document.querySelectorAll('.nb-run').forEach(button=>{
  button.onclick=()=>{
    const output=document.getElementById(button.getAttribute('aria-controls'));
    output.classList.add('shown');output.setAttribute('aria-hidden','false');
    button.setAttribute('aria-expanded','true');
  };
});
document.querySelectorAll('.nb-output').forEach(output=>output.setAttribute('aria-hidden','true'));
document.querySelectorAll('.nb-download').forEach(button=>button.onclick=()=>{
  const name='notebooks/manufacturing-shacl.ipynb';
  const url=URL.createObjectURL(new Blob([payload.assets[name]],{type:'application/x-ipynb+json'}));
  const link=document.createElement('a');link.href=url;link.download='manufacturing-shacl.ipynb';link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
});
const dialog=document.getElementById('asset-dialog'), assetSelect=document.getElementById('asset-select');
Object.keys(payload.assets).forEach(name=>{const o=document.createElement('option');o.value=name;o.textContent=name;assetSelect.append(o);});
function showAsset(){document.getElementById('asset-content').textContent=payload.assets[assetSelect.value];}
assetSelect.onchange=showAsset;showAsset();
document.getElementById('assets').onclick=()=>{dialog.showModal();};
document.getElementById('close-dialog').onclick=()=>dialog.close();
document.getElementById('download-asset').onclick=()=>{const url=URL.createObjectURL(new Blob([payload.assets[assetSelect.value]],{type:'text/plain;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=assetSelect.value.split('/').pop();a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
document.getElementById('prev').onclick=()=>go(current-1);
document.getElementById('next').onclick=()=>go(current+1);
select.onchange=()=>go(Number(select.value));
document.getElementById('notes').onclick=()=>{showNotes=!showNotes;document.getElementById('notes').setAttribute('aria-pressed',String(showNotes));slides[current].querySelector('.speaker').hidden=!showNotes;};
document.getElementById('fullscreen').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch(e){document.getElementById('fullscreen').textContent='전체 화면 제한';}};
document.getElementById('print').onclick=()=>{window.print();};
window.addEventListener('hashchange',()=>go(hashIndex(),false));
document.addEventListener('keydown',e=>{
  if(dialog.open||['SELECT','INPUT','TEXTAREA','BUTTON','A'].includes(e.target.tagName))return;
  if(e.key==='ArrowRight'||e.key==='PageDown'){e.preventDefault();go(current+1);}
  else if(e.key==='ArrowLeft'||e.key==='PageUp'){e.preventDefault();go(current-1);}
  else if(e.key==='Home'){e.preventDefault();go(0);}
  else if(e.key==='End'){e.preventDefault();go(slides.length-1);}
  else if(e.key===' '){e.preventDefault();go(current+1);}
  else if(e.key.toLowerCase()==='n')document.getElementById('notes').click();
  else if(e.key.toLowerCase()==='f')document.getElementById('fullscreen').click();
  else if(e.key.toLowerCase()==='p')document.getElementById('print').click();
});
go(hashIndex(),false);
