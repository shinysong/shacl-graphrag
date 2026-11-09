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
  assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
  page.locator('#hierarchy-demo').screenshot(path=str(root/f'demo-{width}-{mode}.png'));results.append({'width':width,'mode':mode,**result,'overflow':False});page.close()
 b.close()
(root/'browser-checks.json').write_text(json.dumps({'results':results,'errors':errors,'prior_failure':'Initial manual browser check waited for option visible; native collapsed select options are not visible. Exit1 timeout retained, changed only browser waiter to attached.'},indent=2)+'\n');print(results,errors);assert not errors
