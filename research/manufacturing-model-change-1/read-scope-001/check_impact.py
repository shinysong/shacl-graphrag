from impact import answer,changed_scope
base={'nodes':{'x':{'class':'Object','browse':['urn:a','X'],'parent':None,'datatype':None,'references':[]}}}
import copy
ref=copy.deepcopy(base);ref['nodes']['x']['references']=[['r',True,'y']]
assert answer(base,'x','browse')==answer(ref,'x','browse')
assert changed_scope(base,ref,'x',['references']) and not changed_scope(base,ref,'x',['browse'])
new=copy.deepcopy(base);new['nodes']['y']=copy.deepcopy(base['nodes']['x'])
assert changed_scope(base,new,'y',['browse']) and answer(base,'y','browse')['status']=='not_defined_in_selected_file'
assert changed_scope(new,base,'y',['references'])
assert not changed_scope(base,ref,'missing',['browse'])
print('reference-only change, addition, removal and both-absent checks passed')
