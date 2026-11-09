"""Posthoc XML source check; never imported by runtime. No repair."""
from pathlib import Path
import json,hashlib,xml.etree.ElementTree as ET
N='{http://opcfoundation.org/UA/2011/03/UANodeSet.xsd}'
BASE='http://opcfoundation.org/UA/'
MT=BASE+'MachineTool/'
IA=BASE+'IA/'

def expected(path):
 raw=Path(path).read_bytes();root=ET.fromstring(raw)
 uris=[BASE]+[n.text for n in root.find(N+'NamespaceUris')]
 aliases={a.get('Alias'):a.text for a in root.find(N+'Aliases')}
 def resolve(text):
  seen=set()
  while text in aliases:
   if text in seen:raise ValueError('alias_cycle')
   seen.add(text);text=aliases[text]
  parts=dict(v.split('=',1) for v in text.split(';'))
  if set(parts)-{'ns','i'} or 'i' not in parts:raise ValueError('unsupported_nodeid')
  return [uris[int(parts.get('ns','0'))],'i='+str(int(parts['i']))]
 def key(t):return json.dumps(t,separators=(',',':'))
 def name(node):
  rawname=node.attrib['BrowseName'];prefix,sep,label=rawname.partition(':')
  return [uris[int(prefix)],label] if sep and prefix.isdigit() else [BASE,rawname]
 nodes={key(resolve(n.attrib['NodeId'])):n for n in root if 'NodeId' in n.attrib}
 node=nodes[key([MT,'i=5025'])]
 refs=[[key(resolve(ref.attrib['ReferenceType'])),ref.get('IsForward','true') in ('true','1'),key(resolve(ref.text.strip()))] for ref in node.find(N+'References')]
 targets=sorted({r[2] for r in refs});targetdefs=[]
 for target in targets:
  targetdefs.append({'target':target,'status':'defined_in_selected_file' if target in nodes else 'not_defined_in_selected_file','browse':[name(nodes[target])] if target in nodes else []})
 results={'browse':[name(node)],'parent':[key(resolve(node.attrib['ParentNodeId']))] if 'ParentNodeId' in node.attrib else [],'references':refs,'target_definitions':targetdefs,'alias':[key(resolve('SignalColor'))],'required_ia':[r.attrib for m in root.find(N+'Models') for r in m if r.get('ModelUri')==IA]}
 # Runtime declares set semantics for serialized references. Preserve this explicitly.
 results={k:sorted({json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')):v for v in vs}.values(),key=lambda v:json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'))) for k,vs in results.items()}
 return hashlib.sha256(raw).hexdigest(),results

def score(run,xmlpaths):
 run=Path(run);sources=json.loads((run/'sources.json').read_text());rows=[json.loads(s) for s in (run/'rows.jsonl').read_text().splitlines()];expectations={};sourcechecks=[]
 for i,p in enumerate(xmlpaths):
  try:
   sha,values=expected(p);matches=sha==sources[i].get('sha256');sourcechecks.append({'source_index':i,'xml':str(p),'sha256':sha,'projected_source_hash_matches':matches,'status':'completed'})
   if matches:expectations[i]=values
  except Exception as e:sourcechecks.append({'source_index':i,'xml':str(p),'status':'scorer_source_failed','error':type(e).__name__+': '+str(e)})
 checks=[]
 for r in rows:
  e=expectations.get(r['source_index']);q=r['question'];checks.append({'backend':r['backend'],'source_index':r['source_index'],'question':q,'runtime_status':r['status'],'scorable':e is not None,'values_equal_to_selected_xml':r['values']==e[q] if e is not None else None})
 return {'source_checks':sourcechecks,'rows':checks,'limits':['Posthoc selected fields only; not complete XML semantic verification','Does not verify hashes of intermediate projection JSON or every node','Independent implementation over XML, same declared contracts; no runtime repair','Not external truth, plant validity or natural-language interpretation']}
if __name__=='__main__':
 import sys
 result=score(sys.argv[1],sys.argv[2:4]);Path(sys.argv[4]).write_text(json.dumps(result,indent=2)+'\n');print({'rows':len(result['rows']),'scorable':sum(r['scorable'] for r in result['rows']),'equal':sum(r['values_equal_to_selected_xml'] is True for r in result['rows'])})
