import json,tempfile,copy
from pathlib import Path
import score
x={**score.EXPECTED,'basis':'supported fixture','citations':[{'claim':'nominal','source_id':'S2'}],'review_pointers':['index']}
assert score.assess(x)['four_field_agreement']
y=copy.deepcopy(x);y.update(nominal_idc_a=None,recorded_current_channel=False,verified_defect_interval_mean_a=456.7,applicable_document_version='invented');r=score.assess(y);assert not r['four_field_agreement'] and all(r[k] for k in ('unsupported_verified_mean','unsupported_version','nominal_withheld','channel_denied'))
y=copy.deepcopy(x);y['nominal_idc_a']=True;assert not score.assess(y)['four_field_agreement']
y=copy.deepcopy(x);y['citations'][0]['source_id']='unknown';assert score.assess(y)['citation_ids_unknown']==['unknown']
with tempfile.TemporaryDirectory() as td:
 p=Path(td);(p/'responses').mkdir();plan=[{'id':str(i),'arm':arm,'model':str(i//3)} for i,arm in enumerate(('draft','self_review','shacl_review')*6)];states=[{**s,'state':'completed'} for s in plan]
 (p/'plan.json').write_text(json.dumps(plan));(p/'states.json').write_text(json.dumps(states))
 for i in range(18):(p/'responses'/f'{i:03d}.result.json').write_text(json.dumps({'status':'completed','contract':x}))
 r=score.score(p);assert len(r['rows'])==18 and all(a['four_field_agreement']==6 for a in r['arms'].values())
 (p/'responses/000.result.json').unlink();r=score.score(p);assert len(r['rows'])==18 and r['rows'][0]['score_status']=='score_error'
 states[1]['state']='output_failure';states[2]['state']='not_attempted';(p/'states.json').write_text(json.dumps(states));r=score.score(p);assert len(r['rows'])==18 and r['rows'][1]['score_status']=='unscorable' and r['rows'][2]['score_status']=='unscorable'
 states[3]['id']=states[4]['id'];(p/'states.json').write_text(json.dumps(states));r=score.score(p);assert not r['denominator']['same_id_multiset'] and r['rows'][3]['score_status']=='score_error'
print('typed-field/error/withholding/citation-ID, full18slots, missing result, outputfailure/unattempted, duplicateidentity controls passed')
