import base64
import hashlib
import pytest
from scripts.retail_turtle_intake import inspect_turtle,MAX_BYTES

@pytest.mark.parametrize('raw,status',[
 (b'<urn:s> <urn:p> "x" .','syntax_valid_pending_execution_review'),
 (b'# comment only','syntax_valid_pending_execution_review'),
 (b'@prefix sh: <http://www.w3.org/ns/shacl#> . <urn:s> sh:minCount "wrong type" .','syntax_valid_pending_execution_review'),
 (b'<urn:s> <urn:p>','artifact_parse_error'),
 (b'```turtle\n<urn:s> <urn:p> "x" .\n```','artifact_parse_error'),
 (b'\xff','artifact_parse_error'),
 (b' \n','generation_empty_or_truncated'),
 (b'#'+b'x'*MAX_BYTES,'artifact_unsupported_or_isolation_rejected'),
])
def test_preserve_and_classify(raw,status):
    out=inspect_turtle(raw)
    assert out['status']==status
    assert base64.b64decode(out['raw_base64'])==raw
    assert out['raw_sha256']==hashlib.sha256(raw).hexdigest()
    assert not any(out[k] for k in ('executed','execution_authorized','interface_checked','semantics_checked'))

def test_no_import_query_or_validation_execution(monkeypatch):
    import socket
    import pyshacl
    from rdflib import Graph
    calls=[]
    def forbidden(*args,**kwargs):
        calls.append(True)
        raise AssertionError('Execution not permitted')
    monkeypatch.setattr(socket.socket,'connect',forbidden)
    monkeypatch.setattr(Graph,'query',forbidden)
    monkeypatch.setattr(pyshacl,'validate',forbidden)
    raw=b'''@prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix sh: <http://www.w3.org/ns/shacl#> .
    <urn:s> owl:imports <https://example.invalid/ontology>;
      sh:select "SELECT * WHERE { SERVICE <https://example.invalid/query> {?s ?p ?o} }" .'''
    out=inspect_turtle(raw)
    assert out['status']=='syntax_valid_pending_execution_review'
    assert out['triple_count']==2 and calls==[]

def test_bytes_required():
    with pytest.raises(TypeError):inspect_turtle('')
