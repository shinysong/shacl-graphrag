import json,tempfile,shutil
from pathlib import Path
import audit
RUN=Path('research/manufacturing-model-change-1/subtype-offline-001')
XML=sorted(Path('research/manufacturing-model-change-1/projection-001/sources').glob('*.xml'))
base=audit.audit(RUN,XML)
assert base['denominator']['same_identity_multiset'] and all(r['values_equal'] for r in base['rows'])
with tempfile.TemporaryDirectory(dir='_workspace/manufacturing-continuation-20261107/subtype-xml') as tmp:
 p=Path(tmp)
 for f in ('config.json','plan.json','rows.jsonl'):shutil.copyfile(RUN/f,p/f)
 rows=[json.loads(l) for l in (p/'rows.jsonl').read_text().splitlines()];rows[0]['values']=['wrong']
 (p/'rows.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
 changed=audit.audit(p,XML);assert sum(r['values_equal'] is False for r in changed['rows'])==1
 rows.append(rows[0]);(p/'rows.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
 assert not audit.audit(p,XML)['denominator']['same_identity_multiset']
missing=audit.audit(RUN,[Path('missing-original.xml'),XML[1]])
assert len(missing['rows'])==744 and sum(r['scorable'] for r in missing['rows'])==372
with tempfile.TemporaryDirectory(dir='_workspace/manufacturing-continuation-20261107/subtype-xml') as tmp:
 p=Path(tmp)
 for f in ('config.json','plan.json','rows.jsonl'):shutil.copyfile(RUN/f,p/f)
 c=json.loads((p/'config.json').read_text());c['sources'][0]['original_xml_sha256']='0'*64;(p/'config.json').write_text(json.dumps(c))
 assert sum(r['scorable'] for r in audit.audit(p,XML)['rows'])==372
print('baseline equality, wrong answer, duplicate row, missing XML, hash mismatch controls pass')
