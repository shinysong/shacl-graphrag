import policy
base={'selected_hash':'a'*64,'required_hash':'a'*64,'unsupported_count':0,'returned_count':7,'unloaded_count':25,'execution_status':'completed','requires_full_context':False}
for change,expected in [({},[]),({'selected_hash':'b'*64},['snapshot_mismatch']),({'requires_full_context':True},['full_context_unverified']),({'unsupported_count':1},['unsupported_returned_value']),({'execution_status':'query_failed'},['execution_unavailable']),({'returned_count':0},[])]:
 r={**base,**change};assert policy.python_flags(r)==policy.shacl_flags(r)[0]==expected
for change in ({'unsupported_count':True},{'selected_hash':'invalid'},{'unsupported_count':8}):
 for f in (policy.python_flags,policy.shacl_flags):
  try:f({**base,**change})
  except ValueError:pass
  else:raise AssertionError('invalid_input_accepted')
print('six metadata policies and three shared malformed-input controls pass; advisory only')
