"""Syntax-only intake; never imports or executes submitted Python."""
import ast
import base64
import hashlib

MAX_BYTES=65536

def inspect_python(raw):
    if not isinstance(raw,bytes):raise TypeError('Expected original bytes')
    result={'raw_base64':base64.b64encode(raw).decode('ascii'),
            'raw_sha256':hashlib.sha256(raw).hexdigest(),'byte_count':len(raw),
            'executed':False,'execution_authorized':False,
            'interface_checked':False,'semantics_checked':False}
    if len(raw)>MAX_BYTES:
        return dict(result,status='artifact_unsupported_or_isolation_rejected',reason='artifact_byte_limit')
    try:text=raw.decode('utf-8',errors='strict')
    except UnicodeDecodeError as exc:
        return dict(result,status='artifact_parse_error',reason='invalid_utf8',error=str(exc))
    if not text.strip():
        return dict(result,status='generation_empty_or_truncated',reason='empty_content')
    try:ast.parse(text,mode='exec')
    except (SyntaxError,ValueError,RecursionError) as exc:
        return dict(result,status='artifact_parse_error',reason='python_syntax',error_type=type(exc).__name__,error=str(exc))
    return dict(result,status='syntax_valid_pending_execution_review',reason='no_execution_or_semantic_assurance')
