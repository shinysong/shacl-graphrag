import json,sys,hashlib
from pathlib import Path
from collections import defaultdict,deque
ROOT=Path('research/manufacturing-model-change-1');P=ROOT/'object-type-context-001'
sys.path.insert(0,str((P/'xml-audit').resolve()));import audit
sys.path.insert(0,str((ROOT/'projection-001').resolve()));import projection

def build(out):
 cfg=json.loads((P/'config.json').read_text());x=json.loads((P/'observed.json').read_text());d={(r['source_index'],r['object'],r['mode'],r['arm']):r for r in x['rows']}
 expected={(q['source_index'],q['object'],m,a) for q in cfg['questions'] for m in ('isolated','with_declared_ia_file') for a in ('python_transitive','owlrl_transitive')}
 if len(d)!=1200 or len(x['rows'])!=1200 or set(d)!=expected or any(r['status']!='completed' for r in d.values()):raise ValueError('observed_scope')
 cases=[];paired=0
 for i,s in enumerate(cfg['sources']):
  main=audit.read(s['main']);ia=audit.read(s['ia']);parents=defaultdict(set);direct=defaultdict(set);names={};classes=main[0]|ia[0]
  for src in (s['main'],s['ia']):names.update({k:v['browse'][1] for k,v in projection.parse(src['path'])['nodes'].items()})
  for a,b in main[2]|ia[2]:parents[a].add(b)
  for o,t in main[3]:direct[o].add(t)
  for q in [q for q in cfg['questions'] if q['source_index']==i]:
   obj=q['object'];a=d[i,obj,'isolated','python_transitive']['types'];b=d[i,obj,'with_declared_ia_file','python_transitive']['types']
   for mode in ('isolated','with_declared_ia_file'):
    if d[i,obj,mode,'python_transitive']['types']!=d[i,obj,mode,'owlrl_transitive']['types']:raise ValueError('algorithm_mismatch')
    paired+=1
   if a==b:continue
   paths=[]
   for target in sorted(set(b)-set(a)):
    queue=deque([[t] for t in sorted(direct[obj])]);seen=set();found=None
    while queue:
     path=queue.popleft();node=path[-1]
     if node==target:found=[obj]+path;break
     if node in seen:continue
     seen.add(node);queue.extend(path+[parent] for parent in sorted(parents[node]))
    if found is None:raise ValueError('no_support_path')
    paths.append({'target':target,'nodes':[{'key':k,'label':names.get(k,json.loads(k)[1]),'definition_loaded':k in classes or k in main[1]} for k in found]})
   cases.append({'source_index':i,'object':obj,'name':names[obj],'before':a,'after':b,'paths':paths,'source_hashes':{key:src['sha256'] for key,src in s.items()}})
 if len(cases)!=4 or paired!=600:raise ValueError('observed_counts')
 data={'cases':cases,'planned':1200,'objects':300,'changed':4,'paired_equal':paired,'offline_only':True,'local_class_query_predecessor':{'queries':248,'changed':0},'raw_observed_sha256':hashlib.sha256((P/'observed.json').read_bytes()).hexdigest()}
 fragment=Path(__file__).with_name('fragment.html').read_text().replace('__IMPORT_DATA__',json.dumps(data,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026'))
 source=Path(__file__).with_name('base-before-import.html').read_text()
 if source.count('</body>')!=1 or 'id="import-context-demo"' in source:raise ValueError('base')
 Path(out).write_text(source.replace('</body>',fragment+'\n</body>'));return data
if __name__=='__main__':print({'cases':len(build(sys.argv[1])['cases'])})
