"""Complete-snapshot declared read-scope replay, not future change prediction."""
import json,hashlib
from pathlib import Path
FIELDS=('browse','references')
PROJECTED=('class','browse','parent','datatype','references')

def answer(snapshot,key,field):
 node=snapshot['nodes'].get(key)
 return {'status':'not_defined_in_selected_file'} if node is None else {'status':'defined','value':node[field]}

def changed_scope(a,b,key,fields):
 old=a['nodes'].get(key);new=b['nodes'].get(key)
 if old is None or new is None:return (old is None)!=(new is None)
 return any(old[f]!=new[f] for f in fields)

def run(old,new,out):
 a=json.loads(Path(old).read_text());b=json.loads(Path(new).read_text());out=Path(out);out.mkdir(exist_ok=False,parents=True)
 # Inspected union is a declared development query cohort, not a forecast of user queries.
 questions=[{'id':hashlib.sha256((key+'|'+field).encode()).hexdigest(),'key':key,'field':field} for key in sorted(set(a['nodes'])|set(b['nodes'])) for field in FIELDS]
 rows=[]
 for q in questions:
  before=answer(a,q['key'],q['field']);after=answer(b,q['key'],q['field'])
  flags={'whole_file':a['sha256']!=b['sha256'],'node_projected_fields':changed_scope(a,b,q['key'],PROJECTED),'question_field':changed_scope(a,b,q['key'],[q['field']])}
  rows.append({'question':q,'before':before,'after':after,'answer_changed':before!=after,'flags':flags})
 summary={p:{'queries':len(rows),'changed_answers':sum(r['answer_changed'] for r in rows),'flagged':sum(r['flags'][p] for r in rows),'changed_missed':sum(r['answer_changed'] and not r['flags'][p] for r in rows),'unchanged_flagged':sum(not r['answer_changed'] and r['flags'][p] for r in rows)} for p in rows[0]['flags']}
 (out/'questions.json').write_text(json.dumps(questions,indent=2)+'\n');(out/'rows.json').write_text(json.dumps(rows,indent=2)+'\n')
 (out/'summary.json').write_text(json.dumps({'policies':summary,'scope':'Two declared lookup types per key from both inspected snapshots; dependent development queries, not representative user workload','assumptions':['Complete selected definition snapshots and correct declared field dependencies','External imported models excluded; not_defined_in_selected_file is not global absence','Field policy exactness follows construction for these direct lookups, not learned applicability','No repair, paid model calls, SHACL execution, engine performance or human labor measurement']},indent=2)+'\n')
 return summary
if __name__=='__main__':
 import sys
 print(run(*sys.argv[1:]))
