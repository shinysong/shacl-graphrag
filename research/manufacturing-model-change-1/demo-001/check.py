import importlib.util,json,re,tempfile
from pathlib import Path
spec=importlib.util.spec_from_file_location('builder',Path(__file__).with_name('build.py'));b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
base=Path('docs/experiments/seminar/manufacturing-trace.html')
with tempfile.TemporaryDirectory(dir='_workspace') as tmp:
 out=Path(tmp)/'out.html';b.build(base,out)
 text=out.read_text();d=json.loads(re.search(r'<script id="hd-data" type="application/json">(.*?)</script>',text,re.S)[1]);assert len(d['rows'])==744 and len(d['witnesses'])==248 and len(d['cases'])==6
 try:b.build(out,out)
 except ValueError as e:assert str(e)=='already_extended'
 else:raise AssertionError('duplicate_extension_accepted')
 broken=Path(tmp)/'bad.html';broken.write_text('no body')
 try:b.build(broken,out)
 except ValueError as e:assert str(e)=='body_contract'
 else:raise AssertionError('missing_body_accepted')
 live=Path(tmp)/'live';live.mkdir();(live/'rows.jsonl').write_text('');(live/'plan.json').write_text('[]')
 try:b.build(base,out,live)
 except ValueError as e:assert str(e)=='live_denominator'
 else:raise AssertionError('bad_live_denominator_accepted')
 print('offline matrix and duplicate extension/body/live-denominator controls passed')
