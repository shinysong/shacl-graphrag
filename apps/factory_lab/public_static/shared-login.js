'use strict';
document.getElementById('login').addEventListener('submit',async event=>{
 event.preventDefault();const button=event.target.querySelector('button'),error=document.getElementById('login-error');button.disabled=true;error.textContent='';
 try{const r=await fetch('/api/shared/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pin:document.getElementById('pin').value}),credentials:'same-origin'});const data=await r.json();if(!r.ok)throw Error(data.error||'접속하지 못했습니다.');document.getElementById('pin').value='';location.replace('/workspace');}
 catch(e){error.textContent=e.message;}finally{button.disabled=false;}
});
