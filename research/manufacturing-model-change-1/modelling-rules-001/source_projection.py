"""Bounded numeric NodeId definition projection; not an OPC UA implementation."""
import hashlib,json,re,xml.etree.ElementTree as ET
from pathlib import Path
BASE='http://opcfoundation.org/UA/'
NS={'u':'http://opcfoundation.org/UA/2011/03/UANodeSet.xsd'}

def parse(path):
 raw=Path(path).read_bytes()
 if len(raw)>1000000 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('unsupported_xml')
 root=ET.fromstring(raw)
 if root.tag!='{'+NS['u']+'}UANodeSet':raise ValueError('wrong_root')
 uris=[BASE]+[e.text for e in root.find('u:NamespaceUris',NS)]
 if any(not u for u in uris) or len(set(uris))!=len(uris):raise ValueError('invalid_namespaces')
 aliases={}
 for e in root.find('u:Aliases',NS):
  key=e.attrib['Alias']
  if key in aliases:raise ValueError('duplicate_alias')
  aliases[key]=(e.text or '').strip()
 def resolve(value,seen=()):
  if value in aliases:
   if value in seen:raise ValueError('alias_cycle')
   return resolve(aliases[value],seen+(value,))
  match=re.fullmatch(r'(?:ns=(\d+);)?i=(\d+)',value)
  if not match:raise ValueError('unsupported_nodeid:'+value)
  index=int(match[1] or 0)
  if index>=len(uris):raise ValueError('unknown_namespace')
  return json.dumps([uris[index],'i='+str(int(match[2]))],separators=(',',':'))
 def browse(value):
  match=re.fullmatch(r'(\d+):(.*)',value)
  index=int(match[1]) if match else 0;name=match[2] if match else value
  if index>=len(uris):raise ValueError('unknown_browse_namespace')
  return [uris[index],name]
 models=[{'attributes':m.attrib,'required':[r.attrib for r in m]} for m in root.find('u:Models',NS)]
 nodes={}
 for e in root:
  if not e.tag.rsplit('}',1)[-1].startswith('UA'):continue
  key=resolve(e.attrib['NodeId'])
  if key in nodes:raise ValueError('duplicate_nodeid')
  refs=[];rawrefs=[]
  container=e.find('u:References',NS)
  if container is not None:
   for r in container:
    forward=r.get('IsForward','true')
    if forward not in ('true','false','1','0'):raise ValueError('invalid_direction')
    target=(r.text or '').strip();typ=r.attrib['ReferenceType']
    refs.append([resolve(typ),forward in ('true','1'),resolve(target)])
    rawrefs.append([typ,forward in ('true','1'),target])
  nodes[key]={'key':key,'raw_nodeid':e.attrib['NodeId'],'class':e.tag.rsplit('}',1)[-1],
   'browse':browse(e.attrib['BrowseName']),'raw_browse':e.attrib['BrowseName'],
   'parent':resolve(e.attrib['ParentNodeId']) if 'ParentNodeId' in e.attrib else None,
   'datatype':resolve(e.attrib['DataType']) if 'DataType' in e.attrib else None,
   'references':sorted(refs),'raw_references':sorted(rawrefs)}
 return {'sha256':hashlib.sha256(raw).hexdigest(),'models':models,'namespaces':uris,
         'aliases':{a:resolve(a) for a in aliases},'raw_aliases':aliases,'nodes':nodes,
         'scope':'Numeric NodeId, node class, qualified BrowseName, explicit ParentNodeId/DataType and references only; other attributes/values/descriptions omitted; imports not loaded'}

def compare(a,b):
 common=set(a['nodes'])&set(b['nodes']);changes=[]
 for key in sorted(common):
  old=a['nodes'][key];new=b['nodes'][key]
  fields=[f for f in ('class','browse','parent','datatype','references') if old[f]!=new[f]]
  if fields:changes.append({'key':key,'changed_projected_fields':fields,'before':old,'after':new})
 return {'common_node_keys':len(common),'added_keys':sorted(set(b['nodes'])-set(a['nodes'])),'removed_keys':sorted(set(a['nodes'])-set(b['nodes'])),
         'changed_definitions':changes,'alias_raw_index_is_not_identity':[
          {'alias':name,'resolved_identity':a['aliases'][name]} for name in sorted(set(a['aliases'])&set(b['aliases']))
          if a['aliases'][name]==b['aliases'][name] and a['raw_aliases'][name]!=b['raw_aliases'][name]],
         'limits':['Projection changes only, not complete semantic differences','Same key is a lookup locator, not proof of unchanged meaning','Source versions are real published model snapshots, not deployed plant history','No operational compatibility or defect judgment']}
