"""Isolated submitted code invocation; runtime receives no acceptance references."""
import hashlib
import json
import resource
import sys
from pathlib import Path

resource.setrlimit(resource.RLIMIT_AS,(1536*1024*1024,1536*1024*1024))
root,arm,input_file=sys.argv[1:]
sys.path.insert(0,str(Path(root)/'scripts'))
if arm=='python_indexed':
    from technology_selection_python import PythonArm as Arm
    artifact='python-rules-v1.json'
elif arm=='sqlite_recursive':
    from technology_selection_sqlite import SQLiteArm as Arm
    artifact='receipt-query-v1.sql'
elif arm=='rdf_owl_shacl':
    from technology_selection_rdf import RDFArm as Arm
    artifact='receipt-shapes-v1.ttl'
else:raise ValueError('unknown arm')
data=json.loads(Path(input_file).read_text())
# Three explicit callers share the same adapter and live policy artifact.
def consumer_a(packet):return Arm(packet).query()
def consumer_b(packet):return Arm(packet).query()
def consumer_c(packet):return Arm(packet).query()
consumer=data.get('consumer')
answer={'A':consumer_a,'B':consumer_b,'C':consumer_c}[consumer](data['packet']) if consumer else Arm(data['packet']).query()
p=Path(root)/'research/technology-selection'/artifact
print(json.dumps(dict(answer=answer,policy_artifact=str(p),policy_sha256=hashlib.sha256(p.read_bytes()).hexdigest()),sort_keys=True))
