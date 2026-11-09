import copy
import json
import tempfile
from pathlib import Path
import inventory

config = json.loads((inventory.P / 'config.json').read_text())
bad = copy.deepcopy(config)
bad['sources'][0]['sha256'] = '0' * 64
result = inventory.run(bad)
assert len(result['slots']) == 4
assert result['slots'][0]['status'] == 'source_failed'
assert all(s['status'] == 'completed' for s in result['slots'][1:])
with tempfile.TemporaryDirectory(dir='_workspace') as d:
    p = Path(d) / 'test.xml'
    p.write_text('''<UANodeSet xmlns="http://opcfoundation.org/UA/2011/03/UANodeSet.xsd">
    <NamespaceUris/><Aliases/><Models/>
    <UAObject NodeId="i=100" BrowseName="Example"><References>
    <Reference ReferenceType="i=37">i=78</Reference>
    <Reference ReferenceType="i=37">i=78</Reference>
    <Reference ReferenceType="i=37" IsForward="false">i=80</Reference>
    </References></UAObject></UANodeSet>''')
    import hashlib
    x = inventory.run({'scope':'authored fixture', 'sources':[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}]})
    row=x['slots'][0]
    assert row['status']=='completed' and row['marked_nodes']==1
    assert row['rule_occurrences']=={'ModellingRule_Mandatory':1}
with tempfile.TemporaryDirectory(dir='_workspace') as d:
    broken = Path(d) / 'malformed.xml'
    broken.write_text('<UANodeSet><broken>')
    damaged = copy.deepcopy(config)
    damaged['sources'][0] = {'path':str(broken), 'sha256':hashlib.sha256(broken.read_bytes()).hexdigest()}
    preserved = inventory.run(damaged)['slots']
    assert len(preserved) == 4 and preserved[0]['status'] == 'source_failed'
    assert 'ParseError' in preserved[0]['error']
    assert all(row['status']=='completed' for row in preserved[1:])
assert not result['conformance_evaluated']
print('source failure denominator, directed set inventory, no conformance claim: passed')
