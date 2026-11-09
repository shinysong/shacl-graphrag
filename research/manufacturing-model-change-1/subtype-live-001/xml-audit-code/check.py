import json,copy
from pathlib import Path
import audit
root=Path('research/manufacturing-model-change-1');c=json.loads((root/'subtype-offline-001/config.json').read_text());p=root/'subtype-live-001';plan=json.loads((p/'plan.json').read_text());rows=[json.loads(l) for l in (p/'rows.jsonl').read_text().splitlines()];xml=[root/'projection-001/sources'/name for name in ('MachineTool-1.01.1-2022-07-04-Opc.Ua.MachineTool.NodeSet2.xml','MachineTool-1.2.0-2024-11-01-Opc.Ua.MachineTool.NodeSet2.xml')]
a=audit.audit(c,plan,rows,xml);assert all(a['denominator'][k] for k in ('same_identity_multiset','expected_992','source_domain_verified')) and sum(r['values_equal'] is True for r in a['rows'])==868
bad=copy.deepcopy(rows);bad[0]['values']=['wrong'];assert audit.audit(c,plan,bad,xml)['rows'][0]['values_equal'] is False
assert not audit.audit(c,plan,rows+[rows[0]],xml)['denominator']['expected_992']
bad=copy.deepcopy(rows);bad[0]['arm']='unknown';r=audit.audit(c,plan,bad,xml);assert not r['denominator']['same_identity_multiset'] and not r['rows'][0]['scorable']
r=audit.audit(c,plan,rows,['missing.xml',xml[1]]);assert sum(x['values_equal'] is True for x in r['rows'])==434 and not r['denominator']['source_domain_verified']
bad=copy.deepcopy(c);bad['sources'][0]['original_xml_sha256']='0'*64;r=audit.audit(bad,plan,rows,xml);assert sum(x['values_equal'] is True for x in r['rows'])==434
print('live source audit baseline and wrong-value/duplicate/unknownarm/missingXML/hash controls passed')
