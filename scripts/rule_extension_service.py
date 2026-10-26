"""Explicit composition, three local consumers and pinned shared policy.
No legacy classes, normalizer or configuration globals are modified.
"""
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def call(arm,consumer,packet,version,legacy=None):
    if consumer not in ('A','B','C') or version not in ('v1','v2'):
        raise ValueError('unsupported request')
    policy_path = ROOT/'research/rule-extension'/f'policy-{version}.json'
    policy = json.loads(policy_path.read_text())
    if arm == 'python':
        from rule_extension_python import evaluate
    elif arm == 'rdf':
        from rule_extension_rdf import evaluate
    else:
        raise ValueError('unsupported arm')
    result = dict(consumer=consumer,policy_version=version,
                  policy_sha256=hashlib.sha256(policy_path.read_bytes()).hexdigest(),
                  answer=evaluate(packet,policy))
    if legacy is not None:
        result['legacy_answer'] = legacy.query()
    return result
