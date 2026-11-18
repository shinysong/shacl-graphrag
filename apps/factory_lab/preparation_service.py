"""In-memory review sessions. Durable persistence is explicit bundle download."""
import json
from pathlib import Path
import secrets

from . import preparation as p


class PreparationService:
    def __init__(self):
        self.drafts = {}

    def _save(self, draft):
        if len(self.drafts)>=4:
            raise ValueError('At most four drafts per server; close a draft before importing another')
        key = secrets.token_hex(16)
        self.drafts[key] = draft
        return {'id':key,'draft':draft,'contracts':p.adapter_config(draft['adapter'])[1]}

    def handle(self, body):
        action = body.get('action')
        schemas = {'analyze':{'files','metadata','adapter'},'example':{'adapter'},'import':{'bundle'},
                   'change':{'id','entry_id','status','target','note','interpretation'},
                   'refresh':{'id','files'},'freeze':{'id'},'execute':{'id','case_id'},'close':{'id'},
                   'list':set(),'get':{'id'}}
        if not isinstance(action,str) or action not in schemas or set(body)!={'action'}|schemas[action]:
            raise ValueError('Unknown preparation action or fields')
        if action=='list':
            return {'sessions':[{'id':key,'adapter':draft['adapter'],'metadata':draft['metadata']}
                                for key,draft in self.drafts.items()]}
        if action=='analyze':
            return self._save(p.create(body['files'],body['metadata'],adapter=body['adapter']))
        if action=='example':
            p.adapter_config(body['adapter'])
            domain = 'commerce' if body['adapter']==p.ADAPTER else 'factory'
            root = Path(__file__).resolve().parents[2]/'examples/data_preparation'/domain
            files = [{'name':f.name,'content':f.read_bytes().decode('utf-8')} for f in sorted(root.iterdir()) if f.suffix in ('.csv','.md')]
            metadata = json.loads((root/'snapshot.json').read_text())
            metadata.pop('schema_version',None)
            return self._save(p.create(files,metadata,adapter=body['adapter']))
        if action=='import':
            return self._save(p.restore(body['bundle']))
        key = body['id']
        if not isinstance(key,str) or key not in self.drafts:
            raise ValueError('Unknown preparation session')
        draft = self.drafts[key]
        if action=='close':
            del self.drafts[key]
            return {'closed':True}
        if action=='change':
            draft = p.change(draft,body['entry_id'],body['status'],body['target'],body['note'],body['interpretation'])
            self.drafts[key] = draft
        elif action=='refresh':
            draft = p.refresh(draft,body['files'])
            self.drafts[key] = draft
        elif action=='freeze':
            return {'bundle':p.freeze(draft)}
        elif action=='execute':
            if not isinstance(body['case_id'],str): raise ValueError('Case ID must be text')
            return {'result':p.execute(p.freeze(draft),body['case_id'])}
        return {'id':key,'draft':draft,'contracts':p.adapter_config(draft['adapter'])[1]}
