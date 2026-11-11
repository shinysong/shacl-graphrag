"""One bounded OpenRouter request; never retries or silently changes providers."""
import hashlib
import json
from decimal import Decimal
from datetime import datetime,timezone,timedelta
import httpx
from dotenv import dotenv_values
from .store import WORK,ROOT,dumps,now

class Gateway:
    def __init__(self,store,*,work_dir=WORK):
        self.store=store
        from pathlib import Path
        self.work=Path(work_dir).resolve()
        if not self.work.is_relative_to((ROOT/'_workspace').resolve()):raise ValueError('Private campaign directory required')
        self.session=json.loads((self.work/'session.json').read_text())
        self.config=json.loads((self.work/'model.json').read_text())
        self.key=dotenv_values(ROOT/'.env').get('OPENROUTER_API_KEY')
        if not self.key:raise RuntimeError('OpenRouter key unavailable')

    def call(self,rid,messages,tools=None):
        cfg=self.config
        if (self.work/'paid-stop.json').exists():raise RuntimeError('Campaign stopped; inspect paid-stop record')
        if self.store.budget()['unresolved']:raise RuntimeError('Unresolved billing; no further requests')
        cap=108 if self.session.get('campaign_id')=='factory-complexity-1' else 100
        if Decimal(self.session['max_usd'])>5 or self.session['max_attempts']>cap:raise RuntimeError('Invalid campaign authorization')
        if cap==108 and datetime.now(timezone.utc)+timedelta(seconds=120)>=datetime.fromisoformat(self.session['deadline']):
            raise RuntimeError('Paid launch cutoff reached; reserve time for response and cleanup')
        # Full textual context bytes overestimate typical text token counts; add generous per-message framing.
        serialized=dumps({'messages':messages,'tools':tools or []}).encode()
        if len(serialized)>60000:raise RuntimeError('Context byte limit exceeded')
        inp=len(serialized)+4096+512*len(messages)
        maxout=cfg['max_tokens']
        amount=2*(Decimal(inp)*Decimal(cfg['prompt_price'])+Decimal(maxout)*Decimal(cfg['completion_price'])+Decimal(cfg.get('request_price','0')))
        payload={'model':cfg['model'],'messages':messages,'temperature':0,'max_tokens':maxout,
                 'provider':{'order':[cfg['provider']],'allow_fallbacks':False,'require_parameters':True,
                             'max_price':{'prompt':float(Decimal(cfg['prompt_price'])*1000000),'completion':float(Decimal(cfg['completion_price'])*1000000)}},
                 'stream':False,'reasoning':{'effort':'low','exclude':True}}
        if cfg.get('seed_supported'):payload['seed']=42
        if tools:payload.update(tools=tools,tool_choice='auto')
        # A hash-bound review gate is created only after native reviews and offline checks.
        gate=json.loads((self.work/'execution-gate.json').read_text())
        if not gate.get('approved'):raise RuntimeError('Review gate closed')
        for path,sha in gate['files'].items():
            if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=sha:raise RuntimeError('Reviewed files changed: '+path)
        cid=self.store.reserve(rid,amount,self.session)
        self.store.event(rid,'llm_started',{'call_id':cid,'model':cfg['model'],'provider':cfg['provider'],'temperature':0,'max_tokens':maxout,'input_sha256':hashlib.sha256(serialized).hexdigest(),'reserved_usd':str(amount)})
        folder=self.work/'calls';folder.mkdir(exist_ok=True)
        (folder/(cid+'-request.json')).write_text(dumps(payload))
        details={'cost':None}
        try:
            with httpx.Client(timeout=httpx.Timeout(75,connect=10),trust_env=False) as client:
                r=client.post('https://openrouter.ai/api/v1/chat/completions',headers={'Authorization':'Bearer '+self.key},json=payload)
            (folder/(cid+'-response.txt')).write_text(r.text)
            details['http_status']=r.status_code
            body=r.json()
            details,anomaly=billing_details(body,r.status_code,amount)
            if details.get('cost') is None:
                anomaly=anomaly or 'Reported cost unavailable; inspect before further requests'
            self.store.settle(cid,'received',details)
            if anomaly:
                (self.work/'paid-stop.json').write_text(dumps({'call_id':cid,'reason':anomaly,'at':now()}))
                raise RuntimeError(anomaly)
            r.raise_for_status()
            if not isinstance(body,dict) or not body.get('choices'):raise RuntimeError('No model choice')
            choice=body['choices'][0]
            if choice.get('finish_reason')=='length':raise RuntimeError('Output truncated; retained without automatic retry')
            message=choice['message']
            if not isinstance(message,dict):raise RuntimeError('Invalid message')
            self.store.settle(cid,'completed',details)
            self.store.event(rid,'llm_completed',{'call_id':cid,**details})
            return message
        except Exception as e:
            # Known costs survive response-schema failures. Unknown costs keep full reservations.
            self.store.settle(cid,'failed',details|{'error_type':type(e).__name__})
            self.store.event(rid,'llm_failed',{'call_id':cid,'error_type':type(e).__name__})
            raise RuntimeError('LLM call failed or truncated; inspect retained call '+cid) from None


def billing_details(body,status,reservation):
    if not isinstance(body,dict):return {'http_status':status,'cost':None},None
    usage=body.get('usage') or {}
    if not isinstance(usage,dict):return {'http_status':status,'cost':None},'Malformed usage'
    raw=usage.get('cost');cost=None;anomaly=None
    if raw is not None:
        try:
            value=Decimal(str(raw))
            if not value.is_finite() or value<0:raise ValueError('Invalid cost')
            cost=str(value)
            if value>reservation:anomaly='Reported cost exceeds reserved amount'
        except Exception:anomaly='Malformed reported cost'
    return {'http_status':status,'model':body.get('model'),'provider':body.get('provider'),
            'usage':usage,'cost':cost,'generation_id':body.get('id')},anomaly
