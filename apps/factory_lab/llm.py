"""One bounded OpenRouter request; never retries or silently changes providers."""
import hashlib
import json
from decimal import Decimal
import httpx
from dotenv import dotenv_values
from .store import WORK,ROOT,dumps,now

class Gateway:
    def __init__(self,store):
        self.store=store
        self.session=json.loads((WORK/'session.json').read_text())
        self.config=json.loads((WORK/'model.json').read_text())
        self.key=dotenv_values(ROOT/'.env').get('OPENROUTER_API_KEY')
        if not self.key:raise RuntimeError('OpenRouter key unavailable')

    def call(self,rid,messages,tools=None):
        cfg=self.config
        if (WORK/'paid-stop.json').exists():raise RuntimeError('Campaign stopped; inspect paid-stop record')
        if Decimal(self.session['max_usd'])>5 or self.session['max_attempts']>100:raise RuntimeError('Invalid campaign authorization')
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
        gate=json.loads((WORK/'execution-gate.json').read_text())
        if not gate.get('approved'):raise RuntimeError('Review gate closed')
        for path,sha in gate['files'].items():
            if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=sha:raise RuntimeError('Reviewed files changed: '+path)
        cid=self.store.reserve(rid,amount,self.session)
        self.store.event(rid,'llm_started',{'call_id':cid,'model':cfg['model'],'provider':cfg['provider'],'temperature':0,'max_tokens':maxout,'input_sha256':hashlib.sha256(serialized).hexdigest(),'reserved_usd':str(amount)})
        folder=WORK/'calls';folder.mkdir(exist_ok=True)
        (folder/(cid+'-request.json')).write_text(dumps(payload))
        try:
            with httpx.Client(timeout=httpx.Timeout(75,connect=10),trust_env=False) as client:
                r=client.post('https://openrouter.ai/api/v1/chat/completions',headers={'Authorization':'Bearer '+self.key},json=payload)
            (folder/(cid+'-response.txt')).write_text(r.text)
            r.raise_for_status();body=r.json()
            usage=body.get('usage') or {};cost=usage.get('cost')
            details={'http_status':r.status_code,'model':body.get('model'),'provider':body.get('provider'),'usage':usage,'cost':cost,'generation_id':body.get('id')}
            self.store.settle(cid,'completed' if body.get('choices') else 'invalid_response',details)
            self.store.event(rid,'llm_completed',{'call_id':cid,**details})
            if cost is not None and (not Decimal(str(cost)).is_finite() or Decimal(str(cost))<0 or Decimal(str(cost))>amount):
                (WORK/'paid-stop.json').write_text(dumps({'call_id':cid,'reason':'cost anomaly','at':now()}))
                raise RuntimeError('Reported cost anomaly; campaign stopped')
            if not body.get('choices'):raise RuntimeError('No model choice')
            choice=body['choices'][0]
            if choice.get('finish_reason')=='length':raise RuntimeError('Output truncated; retained without automatic retry')
            return choice['message']
        except Exception as e:
            # Preserve unknown charges after network/provider failures. Never refund the reservation.
            if not isinstance(e,RuntimeError):
                self.store.settle(cid,'failed',{'error_type':type(e).__name__,'cost':None})
            self.store.event(rid,'llm_failed',{'call_id':cid,'error_type':type(e).__name__})
            raise RuntimeError('LLM call failed or truncated; inspect retained call '+cid) from None
