import runtime as r

def fixture():
 return {'nodes':{'A':{'class':'UAObjectType','references':[[r.standard(45),False,'B']]},'B':{'class':'UAObjectType','references':[[r.standard(45),False,'External']]},'Other':{'class':'UAObjectType','references':[]},'obj':{'class':'UAObject','references':[[r.standard(40),True,'A']]}}}
d=fixture();p=r.project(d);a=r.outputs(p,'asserted');b=r.outputs(p,'python_transitive');c=r.outputs(p,'owlrl_transitive')
assert b==c and a!=b and b['ancestors','A']==['B','External'] and b['model_object_members','B']==['obj'] and b['model_object_members','Other']==[]
d['nodes']['A']['references']=[];p=r.project(d);assert r.outputs(p,'python_transitive')==r.outputs(p,'owlrl_transitive');assert r.outputs(p,'python_transitive')['model_object_members','B']==[]
d=fixture();d['nodes']['B']['references']=[[r.standard(45),False,'A']]
try:r.project(d)
except ValueError:pass
else:raise AssertionError('cycle_not_rejected')
print('chain/membership/boundary/unrelated/removal parity; cycle rejected outside contract')
