import witness as w
from pathlib import Path
import json,tempfile,hashlib
key=lambda n:json.dumps(['http://opcfoundation.org/UA/','i='+str(n)],separators=(',',':'))
d={'sha256':'declared-test-source','nodes':{'A':{'class':'UAObjectType','references':[[key(45),False,'B']]},'B':{'class':'UAObjectType','references':[[key(45),False,'External']]},'Object1':{'class':'UAObject','references':[[key(40),True,'A']]},'Object2':{'class':'UAObject','references':[[key(40),True,'A']]}}}
classes,objects,edges=w.index(d);assert len(w.path(edges,'Object1','B','model_object_members'))==2;assert w.path(edges,'B','A','ancestors') is None;assert w.reachable_boundary(classes,edges,['A'])==['External']
with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
 p=Path(tmp)/'projection.json';p.write_text(json.dumps(d));cfg={'sources':[{'path':str(p),'projection_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'original_xml_sha256':d['sha256']}]}
 row={'source_index':0,'kind':'model_object_members','target':'B','arm':'test','status':'completed','values':['Object1','Object2','invented']};result=w.build(cfg,[row]);ans=result['reports'][0]['answers'];assert [a['supported_in_selected_projection'] for a in ans]==[True,True,False]
 row['values']=[];r=w.build(cfg,[row])['reports'][0];assert r['witness_status']=='all_returned_values_supported' and r['negative_or_global_completeness']=='not_certified'
 cfg['sources'][0]['projection_sha256']='wrong';assert w.build(cfg,[row])['reports'][0]['witness_status']=='source_unavailable'
print('support direction/type, separate object IDs, unknown value, frontier, empty-answer and hash-failure controls pass')
