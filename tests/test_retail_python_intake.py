import base64
import hashlib
import pytest
from scripts.retail_python_intake import inspect_python,MAX_BYTES

@pytest.mark.parametrize('raw,status',[
 (b'def evaluate(packet):\n return {"decisions": []}\n','syntax_valid_pending_execution_review'),
 (b'raise RuntimeError("must not execute")','syntax_valid_pending_execution_review'),
 (b'def broken(','artifact_parse_error'),
 (b'```python\nx=1\n```','artifact_parse_error'),
 (b'\xff','artifact_parse_error'),
 (b' \n','generation_empty_or_truncated'),
 (b'#'+b'x'*MAX_BYTES,'artifact_unsupported_or_isolation_rejected'),
])
def test_preserve_and_classify(raw,status):
    out=inspect_python(raw)
    assert out['status']==status
    assert base64.b64decode(out['raw_base64'])==raw
    assert out['raw_sha256']==hashlib.sha256(raw).hexdigest()
    assert not out['executed'] and not out['execution_authorized']
    assert not out['semantics_checked'] and not out['interface_checked']

def test_file_effect_not_executed(tmp_path):
    marker=tmp_path/'marker'
    raw=f'from pathlib import Path\nPath({str(marker)!r}).write_text("bad")'.encode()
    assert inspect_python(raw)['status']=='syntax_valid_pending_execution_review'
    assert not marker.exists()

def test_bytes_required():
    with pytest.raises(TypeError):inspect_python('x=1')
