# Actual published manufacturing model definition projection
Two OPCFoundation UA-Nodeset MachineTool published files pinned f484a8ddf9153d3f7b6819f71de0de799ba2b45b (Version1.01.1,July4 2022) and3cb33cebbf5feff4432f9174ed3acdd8c81909b8 (Version1.02.0,Nov1 2024). OriginalXML headers MIT1.00 preserved;385880/435148bytes hashes849b29895d096867856642c777b1f6b1c9854c9932354b10a45089d3af7f6e74 / ada2158cf4b307e571a243d5944422496cc80e93d33831ae92c4162505e3b2c0. FailedhistoricalREADME404retained. Publishedschemas notphysicaloperatinghistory, no defect/compatibility/efficacy claim. Initialsourceinspection552/589nodes,2206/2375referenceoccurrences. Same rawns1i5025 differentBrowseName InitializingToRunning vsFileSystem; observeddefinitiondifference notassumedinvalidstandard. Namespace4IA old vsJobs new,IA newnamespace6. Imports notloaded; unresolvedexternaldefinitions notsourceabsence. Consumeasdevelopment.
Plan: parse onlynumericNodeIds, resolvealiases+namespaceURI, preserve qualifiedBrowseName,direction, class,explicitParentNodeId andDataType. KeeprawIDs alongsidecanonicals. Compare commonkeys forchangedselectedfields; listnew/removedkeys; alias rawchanges withstablecanonicalidentity. Theseareprojectionchanges NOTfullsemanticdiffs (values,otherattrs,descriptions omitted). No inference/SHACL/DB/model calls. Preservebothsourceoutcomes onparsefailure; comparisononlyifbothcomplete; diskfailureoutsideguarantee. No goldrepair. Five software checks described below. Sourceomitted independentlyunverified. Runonlyafterbothreviews ready; no newinfra/paidcalls.
Questions: What definition is recorded at a locator in each release? Which imported namespace an index denotes? Does the same alias retainidentitydespiteindexchange? What dependencies aredeclared, and which areunloaded? These are sourceinspectionquestions, notnewheldoutQA.

```python
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

```

```python
import tempfile
from pathlib import Path
import projection as p
prefix='<UANodeSet xmlns="http://opcfoundation.org/UA/2011/03/UANodeSet.xsd"><NamespaceUris>{}</NamespaceUris><Models/><Aliases>{}</Aliases>{}</UANodeSet>'
def parse(tmp,uris,aliases,nodes):
 f=tmp/'x.xml';f.write_text(prefix.format(''.join('<Uri>'+u+'</Uri>' for u in uris),aliases,nodes));return p.parse(f)
with tempfile.TemporaryDirectory() as d:
 tmp=Path(d)
 a=parse(tmp,['urn:a','urn:b'],'<Alias Alias="T">ns=2;i=4</Alias>','<UAVariable NodeId="ns=1;i=2" BrowseName="1:X" DataType="T"><References><Reference ReferenceType="i=47" IsForward="false">ns=2;i=4</Reference></References></UAVariable>')
 b=parse(tmp,['urn:b','urn:a'],'<Alias Alias="T">ns=1;i=4</Alias>','<UAVariable NodeId="ns=2;i=2" BrowseName="2:X" DataType="T"><References><Reference ReferenceType="i=47" IsForward="0">ns=1;i=4</Reference></References></UAVariable>')
 assert not p.compare(a,b)['changed_definitions'];assert a['aliases']==b['aliases']
 for aliases,nodes in [('<Alias Alias="X">X</Alias>',''),('','<UAObject NodeId="ns=4;i=1" BrowseName="X"/>'),('','<UAObject NodeId="i=1" BrowseName="X"/><UAObject NodeId="i=1" BrowseName="Y"/>'),('','<UAObject NodeId="s=unsupported" BrowseName="X"/>')]:
  try:parse(tmp,['urn:a'],aliases,nodes)
  except ValueError:pass
  else:raise AssertionError('invalid accepted')
print('namespace permutation/direction equivalence plus four invalid input checks pass')

```

```python
import json,sys
from pathlib import Path
from projection import parse,compare

def run(sources,out):
 out=Path(out);out.mkdir(exist_ok=False,parents=True);results=[];parsed=[]
 for index,source in enumerate(sources):
  try:
   result=parse(source);parsed.append(result)
   (out/f'snapshot-{index}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
   results.append({'source':str(source),'status':'completed','sha256':result['sha256'],'nodes':len(result['nodes'])})
  except Exception as exc:results.append({'source':str(source),'status':'failed','error':type(exc).__name__+':'+str(exc)})
 (out/'outcomes.json').write_text(json.dumps(results,indent=2)+'\n')
 comparison=compare(*parsed) if len(parsed)==2 else {'status':'not_run','reason':'source_failure'}
 (out/'comparison.json').write_text(json.dumps(comparison,ensure_ascii=False,indent=2)+'\n')
 return results
if __name__=='__main__':run(sys.argv[1:3],sys.argv[3])

```
