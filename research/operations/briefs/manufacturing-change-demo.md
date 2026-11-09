# Saved manufacturing change example UI
Extend prior1736row/248offlinewitness/6advisory demo with124storedquery-footprint cases. Observedposthoc one ObligationTypemembership1to2addition; priorpositivepaths remain. Not freshbenchmark/LLMeffect/physicalequipment. UIallflagsreadfromstoredresults; no goldruntime repair. Equalfullsnapshots/manualtypedqueries, positivepath-onlydeliberatelyincompletecontrol. Existingbasefrozenpublicbase-welding-demo.html. Fixpubliccheckbaseline nowexplicitfrozenbaseinsteadextendedHTML. Exact builder/fragment/probe supplied; rawartifacts andquerycalculations omitted/unverifiedbythisreview. Previousprobespassed248selectors277paths6cases each390light1280dark. Newchange124selectors/1to2case/layoutpending. Review<=150words.

## build.py
```python
import hashlib,json,sys
from pathlib import Path
ROOT=Path('research/manufacturing-model-change-1')
def build(base,out,live_run=None):
 source=Path(base).read_text()
 if 'id="hierarchy-demo"' in source:raise ValueError('already_extended')
 cfg=json.loads((ROOT/'subtype-offline-001/config.json').read_text())
 for item in cfg['sources']:
  if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()!=item['projection_sha256']:raise ValueError('projection_hash_mismatch')
 nodes=[json.loads(Path(s['path']).read_text())['nodes'] for s in cfg['sources']]
 rows=[json.loads(l) for l in (ROOT/'subtype-offline-001/rows.jsonl').read_text().splitlines()]
 identity=lambda r:(r['source_index'],r['kind'],r['target'],r['arm'])
 expected={(q['source_index'],q['kind'],q['target'],arm) for q in cfg['questions'] for arm in ('asserted','python_transitive','owlrl_transitive')}
 if len(rows)!=744 or len({identity(r) for r in rows})!=744 or {identity(r) for r in rows}!=expected:raise ValueError('offline_denominator')
 if live_run:
  p=Path(live_run);live_rows=[json.loads(l) for l in (p/'rows.jsonl').read_text().splitlines()];plan=json.loads((p/'plan.json').read_text())
  identity=lambda r:(r['source_index'],r['kind'],r['target'],r['arm'])
  if len(live_rows)!=992 or len({identity(r) for r in live_rows})!=992 or {identity(r) for r in live_rows}!={identity(r) for r in plan}:raise ValueError('live_denominator')
  rows+=live_rows
 d={'sources':cfg['sources'],'nodes':[{k:{'class':n['class'],'browse':n['browse']} for k,n in ns.items()} for ns in nodes],'rows':rows,'witnesses':[r for r in json.loads((ROOT/'witness-001/offline-witnesses.json').read_text())['reports'] if r['arm']=='owlrl_transitive'],'cases':json.loads((ROOT/'advisory-metadata-001/fixtures.json').read_text()),'advisory':[json.loads(l) for l in (ROOT/'advisory-metadata-001/rows.jsonl').read_text().splitlines()],'live_run':str(live_run) if live_run else None}
 change=json.loads((ROOT/'query-footprint-001/results.json').read_text())
 if len(change['rows'])!=124 or len({(r['kind'],r['target']) for r in change['rows']})!=124:raise ValueError('change_denominator')
 d['change']=change
 data=json.dumps(d,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
 fragment=Path(__file__).with_name('fragment.html').read_text().replace('__HD_DATA__',data)
 if source.count('</body>')!=1:raise ValueError('body_contract')
 Path(out).parent.mkdir(parents=True,exist_ok=True)
 Path(out).write_text(source.replace('</body>',fragment+'\n</body>'))
 print({'rows':len(rows),'witnesses':len(d['witnesses']),'cases':len(d['cases']),'live_run':d['live_run']})
if __name__=='__main__':build(sys.argv[1],sys.argv[2],sys.argv[3] if len(sys.argv)>3 else None)

```

## check.py
```python
import importlib.util,json,re,tempfile
from pathlib import Path
spec=importlib.util.spec_from_file_location('builder',Path(__file__).with_name('build.py'));b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
base=Path('research/manufacturing-model-change-1/demo-001/base-welding-demo.html')
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

```

## browser.py
```python
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).parent;results=[];errors=[]
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox'])
 for width,mode in [(390,'light'),(1280,'dark')]:
  page=b.new_page(viewport={'width':width,'height':950},color_scheme=mode);page.on('pageerror',lambda e:errors.append(str(e)));page.goto((root/'preview.html').resolve().as_uri());page.wait_for_selector('#hd-type option',state='attached')
  assert page.locator('#hd-type option').count()==62
  result=page.evaluate('''()=>{let cases=0,paths=0;const e=id=>document.getElementById(id),change=id=>e(id).dispatchEvent(new Event('change'));for(const version of ['0','1']){e('hd-version').value=version;change('hd-version');for(const t of [...e('hd-type').options].map(o=>o.value)){for(const k of ['ancestors','model_object_members']){e('hd-type').value=t;e('hd-kind').value=k;change('hd-type');if(e('hd-results').children.length!==7)throw Error('arm_count');for(const v of [...e('hd-value').options].map(o=>o.value)){e('hd-value').value=v;change('hd-value');const proof=JSON.parse(e('hd-proof').textContent);if(!proof.answer.one_support_path.length)throw Error('empty_path');if(!e('hd-path').querySelector('rect'))throw Error('missing_svg');paths++}cases++}}}for(const c of [...e('hd-case').options].map(o=>o.value)){e('hd-case').value=c;change('hd-case');if(!e('hd-review').textContent.includes('SHACL:'))throw Error('missing_review')}e('hd-version').value='1';change('hd-version');e('hd-type').value=JSON.stringify(['http://opcfoundation.org/UA/MachineTool/','i=24']);change('hd-type');return {cases,paths,arms:7,advisory_cases:6}}''')
  changes=page.evaluate('''()=>{const e=id=>document.getElementById(id);for(const o of e('hd-change').options){e('hd-change').value=o.value;e('hd-change').dispatchEvent(new Event('change'));if(!e('hd-change-flags').textContent.includes('조회한 관계 목록'))throw Error('missingflags');JSON.parse(e('hd-change-old').textContent);JSON.parse(e('hd-change-new').textContent)}const i=[...e('hd-change').options].find(o=>o.textContent.startsWith('변경'));e('hd-change').value=i.value;e('hd-change').dispatchEvent(new Event('change'));if(JSON.parse(e('hd-change-old').textContent).length!==1||JSON.parse(e('hd-change-new').textContent).length!==2)throw Error('changedcasevalues');return e('hd-change').options.length}''')
  assert changes==124
  page.locator('#hd-change-panel').screenshot(path=str(root/f'change-{width}-{mode}.png'))
  assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
  page.locator('#hierarchy-demo').screenshot(path=str(root/f'demo-{width}-{mode}.png'));results.append({'width':width,'mode':mode,**result,'overflow':False,'change_selections':changes});page.close()
 b.close()
(root/'browser-checks.json').write_text(json.dumps({'results':results,'errors':errors,'prior_failure':'Initial manual browser check waited for option visible; native collapsed select options are not visible. Exit1 timeout retained, changed only browser waiter to attached.'},indent=2)+'\n');print(results,errors);assert not errors

```
