import json
from scripts.retail_direct_pilot import paired

def test_only_metadata_differs():
    row={'row_id':'2','data':{'Quantity':'bad','CustomerID':None}}
    pairs=paired(row,[{'name':k} for k in row['data']])
    raw=json.loads(pairs['raw']['user_prompt']);meta=json.loads(pairs['metadata']['user_prompt'])
    normalized=meta.pop('normalized_rows')
    assert raw==meta and normalized[0]['fields']['Quantity']['state']=='invalid'
    assert pairs['raw']['system_prompt']==pairs['metadata']['system_prompt']
    assert raw['rows']==[row] and 'reference_generation' not in raw
