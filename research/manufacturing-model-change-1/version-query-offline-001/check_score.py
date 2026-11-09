import json,tempfile,shutil
from pathlib import Path
import score_xml as s
base=Path('research/manufacturing-model-change-1');run=base/'version-query-offline-001';xmls=sorted((base/'projection-001/sources').glob('*.xml'))
assert len(xmls)==2
with tempfile.TemporaryDirectory(dir='_workspace/manufacturing-continuation-20261107') as tmp:
 p=Path(tmp);shutil.copy2(run/'sources.json',p/'sources.json');rows=[json.loads(x) for x in (run/'rows.jsonl').read_text().splitlines()];rows[0]['values']=['wrong_label']
 (p/'rows.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows));result=s.score(p,xmls)
 assert result['rows'][0]['values_equal_to_selected_xml'] is False
 sources=json.loads((p/'sources.json').read_text());sources[0]['sha256']='wrong';(p/'sources.json').write_text(json.dumps(sources));result=s.score(p,xmls)
 assert len(result['rows'])==24 and sum(x['scorable'] for x in result['rows'])==12
 result=s.score(run,[p/'missing.xml',xmls[1]])
 assert len(result['rows'])==24 and sum(x['scorable'] for x in result['rows'])==12
print('wronglabel detected; wrong sourcehash and unavailableXML each retain24rows/12unscorable')
