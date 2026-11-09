# Explicit modelling rule source inventory
Four previously inspected MachineTool/IA XML files, all four source slots retained on source errors. Count only explicit forward namespace-qualified HasModellingRule(UA37), set-dedup per node. Original numeric node source hashes required. Standard rule name facts from pinned OPC Foundation NodeIds.csv six rows,1,205,102bytes source downloaded within2MBcap; rawCSV and3officialspecHTML retained privately, source URLs/hashes in acquisition. CSV license not separately verified; only six numeric-name facts public, XMLoriginalMITnotices preserved. No inferred declaration hierarchy, asset validation, shape execution, compatibility or conformance result. ModellingRule target lack does not certify incompleteness; not all tagged model nodes necessarily full InstanceDeclarations. Manual source audit will independently enumerate raw XML tagged nodes and compare serialized inventory after execution. No source repair/runtimegold. No new paid/DBcalls.
Official specification read: Part3 6.3.3 inherited declaration hierarchy merges BrowsePaths and overrides, not merely class closure;6.4.4.4.1 Mandatory concerns existingBrowsePaths;6.4.4.4.5 MandatoryPlaceholder at leastone typed/reference-matching child, no fixedBrowseName. These are source context, not implemented semantics. No registered checks; manuallyrun check.py (badsource4denominator and authored duplicate/inverse refs) then inventory.py and independent raw audit. Underlying XML omitted: unverified by reviewers.

## inventory.py
```
"""Explicit modelling-rule inventory only; never a conformance checker."""
import hashlib
import json
from collections import Counter
from pathlib import Path
import source_projection as projection

P = Path(__file__).parent
UA = 'http://opcfoundation.org/UA/'


def run(config):
    labels = json.loads((P / 'labels.json').read_text())['labels']
    relation = json.dumps([UA, 'i=37'], separators=(',', ':'))
    slots = []
    for spec in config['sources']:
        slot = {'source': spec, 'status': 'source_failed', 'declarations': []}
        try:
            raw = Path(spec['path']).read_bytes()
            if hashlib.sha256(raw).hexdigest() != spec['sha256']:
                raise ValueError('source_hash_mismatch')
            parsed = projection.parse(spec['path'])
            declarations = []
            for key, node in sorted(parsed['nodes'].items()):
                targets = sorted({target for kind, forward, target in node['references']
                                  if kind == relation and forward})
                if not targets:
                    continue
                declarations.append({
                    'key': key, 'class': node['class'], 'browse': node['browse'],
                    'parent': node['parent'], 'rules': targets,
                    'rule_labels': [labels.get(json.loads(t)[1][2:], 'unmapped')
                                    if json.loads(t)[0] == UA else 'external_unmapped'
                                    for t in targets],
                    'explicit_type_targets': sorted({target for kind, forward, target in node['references']
                        if forward and kind == json.dumps([UA, 'i=40'], separators=(',', ':'))}),
                })
            slot.update(status='completed', declarations=declarations,
                        nodes=len(parsed['nodes']), marked_nodes=len(declarations),
                        rule_occurrences=dict(sorted(Counter(label for d in declarations
                            for label in d['rule_labels']).items())),
                        class_counts=dict(sorted(Counter(d['class'] for d in declarations).items())),
                        multi_rule_nodes=sum(len(d['rules']) != 1 for d in declarations))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            slot['error'] = type(exc).__name__ + ': ' + str(exc)
        slots.append(slot)
    return {'scope': config['scope'], 'planned_source_slots': len(config['sources']),
            'slots': slots, 'conformance_evaluated': False,
            'inherited_declarations_computed': False, 'physical_assets_evaluated': False}


if __name__ == '__main__':
    result = run(json.loads((P / 'config.json').read_text()))
    (P / 'observed.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print([{k: s.get(k) for k in ('status', 'nodes', 'marked_nodes', 'rule_occurrences')}
           for s in result['slots']])

```

## check.py
```
import copy
import json
import tempfile
from pathlib import Path
import inventory

config = json.loads((inventory.P / 'config.json').read_text())
bad = copy.deepcopy(config)
bad['sources'][0]['sha256'] = '0' * 64
result = inventory.run(bad)
assert len(result['slots']) == 4
assert result['slots'][0]['status'] == 'source_failed'
assert all(s['status'] == 'completed' for s in result['slots'][1:])
with tempfile.TemporaryDirectory(dir='_workspace') as d:
    p = Path(d) / 'test.xml'
    p.write_text('''<UANodeSet xmlns="http://opcfoundation.org/UA/2011/03/UANodeSet.xsd">
    <NamespaceUris/><Aliases/><Models/>
    <UAObject NodeId="i=100" BrowseName="Example"><References>
    <Reference ReferenceType="i=37">i=78</Reference>
    <Reference ReferenceType="i=37">i=78</Reference>
    <Reference ReferenceType="i=37" IsForward="false">i=80</Reference>
    </References></UAObject></UANodeSet>''')
    import hashlib
    x = inventory.run({'scope':'authored fixture', 'sources':[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}]})
    row=x['slots'][0]
    assert row['status']=='completed' and row['marked_nodes']==1
    assert row['rule_occurrences']=={'ModellingRule_Mandatory':1}
assert not result['conformance_evaluated']
print('source failure denominator, directed set inventory, no conformance claim: passed')

```

## source_projection.py
```
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

## config.json
```
{
  "sources": [
    {
      "path": "research/manufacturing-model-change-1/projection-001/sources/MachineTool-1.01.1-2022-07-04-Opc.Ua.MachineTool.NodeSet2.xml",
      "sha256": "849b29895d096867856642c777b1f6b1c9854c9932354b10a45089d3af7f6e74",
      "role": "main"
    },
    {
      "path": "research/manufacturing-model-change-1/dependency-metadata-001/IA-1.01.0-2021-07-31-Opc.Ua.IA.NodeSet2.xml",
      "sha256": "8524927d2d75cbf15c10711cd8a463820adaf24a259d4c8a656321c55186f20b",
      "role": "ia"
    },
    {
      "path": "research/manufacturing-model-change-1/projection-001/sources/MachineTool-1.2.0-2024-11-01-Opc.Ua.MachineTool.NodeSet2.xml",
      "sha256": "ada2158cf4b307e571a243d5944422496cc80e93d33831ae92c4162505e3b2c0",
      "role": "main"
    },
    {
      "path": "research/manufacturing-model-change-1/dependency-metadata-001/IA-1.01.2-2024-02-28-Opc.Ua.IA.NodeSet2.xml",
      "sha256": "2a198ed96604eaf473d1ebfb4b29d745a7af8eed74c0f96ab1ac5f1fb71e4de9",
      "role": "ia"
    }
  ],
  "planned_source_slots": 4,
  "scope": "Inventory explicit forward HasModellingRule declarations in four pinned XML files. Not full inherited declaration computation, no conformance, no asset instances, no compatibility judgment. Already inspected development sources."
}

```

## labels.json
```
{
  "source_url": "https://raw.githubusercontent.com/OPCFoundation/UA-Nodeset/f484a8ddf9153d3f7b6819f71de0de799ba2b45b/Schema/NodeIds.csv",
  "source_sha256": "80cbeeb420675790fdefe865e359041fa2d15c8a943f8b007409465aa86e98e7",
  "labels": {
    "37": "HasModellingRule",
    "78": "ModellingRule_Mandatory",
    "80": "ModellingRule_Optional",
    "83": "ModellingRule_ExposesItsArray",
    "11508": "ModellingRule_OptionalPlaceholder",
    "11510": "ModellingRule_MandatoryPlaceholder"
  },
  "scope": "Six numeric-name facts only; no source CSV redistributed. All rule IDs are UA namespace-qualified."
}

```
