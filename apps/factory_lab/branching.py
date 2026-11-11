"""Freeze a real chat draft once; build isolated advisory final-answer arms."""
import hashlib
import json
from .store import dumps
from .review import review
from .evidence import CONTRACT, canonical, model_evidence

ARMS = ('self', 'python', 'shacl')

def freeze_bundle(question, draft, evidence, system, snapshot_meta, previous_question=None, request_context=None):
    # JSON round trip detaches mutable tool result objects; no evaluator inputs.
    bundle = json.loads(dumps({'question': question, 'draft': draft, 'evidence': evidence,
        'system': system, 'snapshot': snapshot_meta,
        'previous_question_context_only': previous_question, 'request_context': request_context,
        'model_evidence_contract': CONTRACT}))
    raw = dumps(bundle)
    return {'sha256': hashlib.sha256(raw.encode()).hexdigest(), 'bundle': bundle}

def final_packet(frozen, arm):
    if arm not in ARMS:
        raise ValueError('Invalid arm')
    bundle = json.loads(dumps(frozen['bundle']))
    if hashlib.sha256(dumps(bundle).encode()).hexdigest() != frozen['sha256']:
        raise ValueError('Frozen bundle changed')
    contract = bundle.get('model_evidence_contract')
    if contract not in (None, CONTRACT):
        raise ValueError('Unsupported model evidence contract')
    report = review(bundle['evidence'], arm)
    # Engine identity stays in the audit event, not in the model prompt.
    normalized = {k: v for k, v in report.items() if k != 'engine'}
    payload = {k: bundle[k] for k in
        ('question', 'previous_question_context_only', 'draft', 'evidence')}
    payload.update(request_context=bundle.get('request_context'), review_report=normalized)
    if contract == CONTRACT:
        payload['evidence'] = [model_evidence(e) for e in bundle['evidence']]
    # Previously saved bundles retain their original serialization and evidence.
    serialize = canonical if contract == CONTRACT else dumps
    messages = [{'role': 'system', 'content': bundle['system'] +
        '\nFinal review stage. No tools available. Revise only when supported; report is advisory, not truth or a mandatory veto.'},
        {'role': 'user', 'content': serialize(payload)}]
    return report, messages
