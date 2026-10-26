"""Pure authored failure checks: no files, models, reservations or containers."""
from datetime import datetime, timezone, timedelta
from scripts.retail_specificity_execute import generation_plan, cost_summary, may_execute, MAP
from scripts.score_retail_decisions import score
inputs = [{'id':'a'}, {'id':'b'}]
first = [{'id':'a','status':'failed','reported_usd':None,'upper_usd':0.1}]
p = generation_plan(inputs, first)
assert p['a'][1]['status'] == 'failed' and p['b'] == (None, {'status':'not_attempted'})
assert cost_summary(first) == {'reported_usd':None,'known_reported_usd':'0','unresolved_cost_count':1,'reserved_usd':0.1}
second = [{'id':'a','status':'completed','reported_usd':0.01,'upper_usd':0.1},
          {'id':'b','status':'failed','reported_usd':None,'upper_usd':0.1}]
assert cost_summary(second)['reported_usd'] is None
assert cost_summary(second)['reserved_usd'] == 0.2
now = datetime.now(timezone.utc)
assert not may_execute('completed',now,now-timedelta(seconds=1))
assert not may_execute('failed',now,now+timedelta(seconds=1))
assert not may_execute('not_attempted',now,now+timedelta(seconds=1))
for n in (72,6,36):
    refs=[{'row_id':str(i),'policy':'customer_analysis','status':'pass'} for i in range(n)]
    errors=[dict(r,status='error') for r in refs]
    m=score(refs,errors)
    assert m['overall']['n'] == n
print('authored interruption/cost/deadline/denominator checks passed')
