"""Handcrafted runner failure and extra RDF boundary checks, no study execution."""
import copy
from check_industrial_question_python import packet
from industrial_question_python import evaluate
from industrial_question_rdf import evaluate as rdf
from run_industrial_questions import execute

p = packet()
assert execute(evaluate,p)['status'] == 'ok'
for mutation in ('missing','enum','identity','duplicate','witness'):
    def bad(q):
        out=evaluate(q)
        if mutation=='missing': del out['receipt']
        if mutation=='enum': out['receipt']='probably'
        if mutation=='identity': out['scene_id']='other'
        if mutation=='duplicate': out['products'][1]=copy.deepcopy(out['products'][0])
        if mutation=='witness': out['products'][0]['witness']=[]
        return out
    result=execute(bad,p)
    assert result['status']=='error' and result['error']['stage']=='output_schema' and result['raw_output'] is not None

def crash(p): raise RuntimeError('injected nonstudy failure')
assert execute(crash,p)['error']['stage']=='execution'
# Semantically wrong but schema-valid decisions must remain outcomes.
def wrong(q):
    out=evaluate(q);out['receipt']='violation';return out
assert execute(wrong,p)['status']=='ok'
p=packet();dup=copy.deepcopy(p['tables']['component_edge'][0]);dup['occurrence_id']='dup'
p['tables']['component_edge'].append(dup)
a,b=evaluate(p),rdf(p)
assert a['products']==b['products'] and b['products'][0]['candidate']=='unknown'
p=packet();p['tables']['product'][1]['id']='c'
p['tables']['component_edge'].append(dict(id='cycle',occurrence_id='cycle',component_item='p',component_revision='1',parent_item='c',parent_revision='1',active=True))
a,b=evaluate(p),rdf(p)
assert a['products']==b['products'] and b['products'][1]['candidate']=='no'
print('PASS: runner error/schema/semantic-nonrepair checks and RDF duplicate-edge/nonreflexive-target checks')
