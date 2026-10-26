"""Handcrafted ablation checks; no study references or baseline reruns."""
from check_industrial_question_python import packet
from industrial_question_direct import evaluate
from run_industrial_questions import execute
p = packet()
out = execute(evaluate, p)
assert out['status'] == 'ok'
assert out['raw_output']['products'][0]['candidate'] == 'no'
assert out['raw_output']['products'][0]['recheck'] == 'not_required'
assert out['raw_output']['receipt'] == 'accept'
p['tables']['component_edge'][0]['parent_item'] = 'p'
out = execute(evaluate, p)['raw_output']
assert out['products'][0]['candidate'] == 'yes' and out['products'][0]['witness'] == ['component_edge:0']
p['tables']['component_edge'][0]['active'] = False
p['coverage'][0]['complete'] = False
out = execute(evaluate,p)['raw_output']
assert out['products'][0]['candidate'] == 'unknown' and out['products'][0]['recheck'] == 'unknown'
print('PASS: direct-only capability, unchanged receipt, explicit witness, partial coverage; no study execution')
