import tempfile,shutil,json
from pathlib import Path
import build
root=Path('research/manufacturing-measurement-1/answer-001')
x=build.bundle(root);assert len(x['rows'])==18 and x['summary']['reported_cost_usd']=='0.646692400'
with tempfile.TemporaryDirectory() as td:
 p=Path(td)/'run';shutil.copytree(root,p)
 (p/'responses/000.request.json').unlink()
 try:build.bundle(p)
 except ValueError as e:assert str(e)=='completed_artifacts_missing'
 else:raise AssertionError('missing artifact allowed')
 shutil.copy2(root/'responses/000.request.json',p/'responses/000.request.json')
 q=p/'responses/000.result.json';r=json.loads(q.read_text());r['contract']['nominal_idc_a']=999;q.write_text(json.dumps(r))
 try:build.bundle(p)
 except ValueError as e:assert str(e)=='contract_binding'
 else:raise AssertionError('changed contract allowed')
print('saved18 and missingcompleted artifact/changedcontract controls passed')
