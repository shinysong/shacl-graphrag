from pathlib import Path
from functools import partial
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from threading import Thread
import json
from playwright.sync_api import sync_playwright
class Handler(SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
root=Path('_workspace/manufacturing-continuation-20261107');data=json.loads((root/'demo-data.json').read_text())
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory='docs'));Thread(target=server.serve_forever,daemon=True).start();errors=[];count=0;screens=[]
try:
 with sync_playwright() as p:
  b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
  assert page.goto(f'http://127.0.0.1:{server.server_port}/experiments/seminar/manufacturing-trace.html').status==200
  for q in data['questions']:
   for backend in ['sqlite_python','rdflib_offline','neo4j_cypher','neptune_sparql']:
    page.select_option('#question-select',q['id']);page.select_option('#backend-select',backend)
    assert page.locator('#question-text').inner_text()==q['question']
    assert page.locator('#obligations tr').count()==len(data['contracts']['questions'][q['id']]['obligations'])
    pack=next((r for r in data['cards'] if r['question_id']==q['id'] and r['backend']==backend),None)
    assert page.locator('#source-cards article').count()==len(pack['cards'] if pack else [])
    old=next(r for r in data['old'] if r['case_id']==q['id'] and r['backend']==backend)
    assert json.loads(page.locator('#old-bindings').inner_text())==old.get('bindings',old.get('error',old.get('reason')))
    count+=1
  for policy,groups in [('name_only',1),('location_equipment',2),('location_equipment_device',6)]:
   page.select_option('#identity-policy',policy);assert page.locator('#identity-groups tr').count()==groups
  assert page.locator('#identity-records tr').count()==35
  for item in data['modelComparison']['changed_definitions']:
   page.select_option('#model-node',item['key']);assert json.loads(page.locator('#model-before').inner_text())==item['before'];assert json.loads(page.locator('#model-after').inner_text())==item['after']
  assert page.locator('#model-aliases tr').count()==3
  for i,item in enumerate(data['scopeExamples']):
   page.select_option('#scope-example',str(i));assert json.loads(page.locator('#scope-before').inner_text())==item['row']['before'];assert json.loads(page.locator('#scope-after').inner_text())==item['row']['after']
  page.select_option('#question-select','Q8');page.select_option('#backend-select','sqlite_python')
  for width,mode in [(390,'light'),(1280,'dark')]:
   page.set_viewport_size({'width':width,'height':950});page.emulate_media(color_scheme=mode)
   assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
   page.screenshot(path=str(root/f'trace-{width}-{mode}.png'));screens.append({'width':width,'mode':mode,'overflow':False})
  b.close()
finally:server.shutdown()
result={'selections_checked':count,'identity_controls':3,'model_definitions':49,'scope_examples':5,'errors':errors,'screens':screens,'scope':'display tests only'};(root/'demo-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(result);assert not errors
