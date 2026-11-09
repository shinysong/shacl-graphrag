import tempfile,json
from pathlib import Path
import runtime as r

def fixture():
 k=r.key(r.MT,5025);ext=r.key(r.IA,3004)
 return {'sha256':'a'*64,'models':[],'aliases':{'SignalColor':ext},'nodes':{k:{'browse':[r.MT,'old'],'parent':None,'references':[[r.key(r.transport.BASE,1),True,ext]]}}}
for Store in (r.transport.SQLStore,r.transport.RDFStore):
 a=fixture();b=fixture();b['sha256']='b'*64;b['nodes'][r.key(r.MT,5025)]['browse']=[r.MT,'new']
 s=Store();s.load(r.triples(a)+r.triples(b))
 assert r.query(s,a['sha256'],'browse')['values']==[[r.MT,'old']]
 assert r.query(s,b['sha256'],'browse')['values']==[[r.MT,'new']]
 assert r.query(s,'missing','browse')['status']=='snapshot_not_loaded'
 assert r.query(s,a['sha256'],'browse',r.IA,5025)['status']=='node_not_defined_in_selected_file'
 target=r.query(s,a['sha256'],'target_definitions')['values'][0]
 assert target['status']=='not_defined_in_selected_file' and target['browse']==[]
 s.cleanup()
with tempfile.TemporaryDirectory(dir='_workspace/manufacturing-continuation-20261107') as tmp:
 p=Path(tmp);(p/'good.json').write_text(json.dumps(fixture()));(p/'bad.json').write_text('{broken')
 summary=r.run([p/'good.json',p/'bad.json'],p/'out')
 assert summary['planned']==summary['emitted']==24 and summary['statuses']=={'completed':12,'source_failed':12}
print('two backends x five semantic controls; one-source failure preserves24planned/12failed')
