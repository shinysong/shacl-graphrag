"""Portable demo runtime. Separate from frozen research campaigns and their ledgers."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import httpx

from apps.factory_lab.store import Store, ROOT, dumps
from apps.factory_lab.llm import billing_details
from apps.factory_lab.review import review as qualification_review
from apps.factory_lab.explanation import shacl_trace
from experiments.factory_complexity.tools import Views, RDFStudyTools
from experiments.query_contracts.competing import CompetingTools
from experiments.query_contracts.composition import (
    decomposition_messages, parse_decomposition, planning_packet, parse_plan,
    checked_plan, execute_plan, report, final_messages, parse_answer,
)

EXAMPLES = ROOT / 'examples/factory_lab'
VERSION = '0.1.0-rc1'


def read(path):
    return json.loads(Path(path).read_text())


def verify_examples():
    manifest = read(EXAMPLES / 'manifest.json')
    for name, digest in manifest['files'].items():
        path = (EXAMPLES / name).resolve()
        if not path.is_relative_to(EXAMPLES.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Bundled example hash mismatch')


def schema(views):
    data, digest = views.snapshot('factory-v3')
    return {'snapshot': 'factory-v3', 'source_sha256': digest, 'as_of': data['as_of'],
            'entities': [{'id': n['id'], 'kind': n['kind'], 'name': n.get('name')} for n in data['nodes']],
            'notice': 'Identifiers only. Query relationships before answering.'}


def selected_review(execution, mode):
    evidence = [dict(c['result'], arguments=c['arguments'], tool=c['tool'])
                for c in execution['calls'] if 'result' in c and not c.get('error')]
    # Frozen reviewer uses one canonical qualification-record input name.
    # Preserve actual query provenance in the public report while adapting rows.
    for item in evidence:
        if item['tool'] in ('current_qualification_records', 'expired_qualification_records'):
            item['source_tool'] = item['tool']
            item['tool'] = 'qualification_records'
    result = qualification_review(evidence, mode)
    result['qualification_evidence_tools'] = sorted({x.get('source_tool', x['tool']) for x in evidence if x['tool']=='qualification_records'})
    if mode == 'shacl':
        result['explanation'] = shacl_trace(evidence)
    return result


class PublicGateway:
    """Explicit BYOK only; persistent nonrefunded reservation cap, no retry/fallback."""
    def __init__(self, store, directory, config, key):
        self.store, self.directory, self.config, self.key = store, Path(directory), config, key
        if not key or key == 'your_openrouter_api_key_here':
            raise ValueError('Set OPENROUTER_API_KEY in the server environment')
        if set(config) - {'reasoning_effort'} != {'model', 'provider', 'prompt_per_million', 'completion_per_million',
                          'max_tokens', 'max_calls', 'max_usd', 'hours'}:
            raise ValueError('Use the documented live-config fields')
        if 'reasoning_effort' in config and config['reasoning_effort'] not in ('low', 'medium', 'high'):
            raise ValueError('Unsupported reasoning effort')
        for field in ('model', 'provider'):
            if not isinstance(config[field], str) or not config[field].strip() or '<' in config[field]:
                raise ValueError('Choose a model and provider')
        for field in ('prompt_per_million', 'completion_per_million', 'max_usd'):
            value = Decimal(str(config[field]))
            if not value.is_finite() or value <= 0:
                raise ValueError('Prices and cap must be finite positive numbers')
        for field, low, high in [('max_tokens', 256, 4096), ('max_calls', 1, 100), ('hours', 1, 8)]:
            if type(config[field]) is not int or not low <= config[field] <= high:
                raise ValueError('Invalid limit: ' + field)
        if Decimal(str(config['max_usd'])) > 5:
            raise ValueError('Demo session cap must be at most USD 5')
        session_path = self.directory / 'session.json'
        fingerprint = hashlib.sha256(dumps(config).encode()).hexdigest()
        if session_path.exists():
            session = read(session_path)
            if session.get('config_sha256') != fingerprint:
                raise ValueError('Existing session config differs; use a deliberately new data directory')
        else:
            session = {'config_sha256': fingerprint, 'deadline': (datetime.now(timezone.utc) + timedelta(hours=config['hours'])).isoformat(),
                       'max_attempts': config['max_calls'], 'max_usd': str(config['max_usd'])}
            session_path.write_text(dumps(session))
        self.session = session

    def call(self, rid, messages):
        cfg = self.config
        if self.store.budget()['unresolved']:
            raise RuntimeError('Unresolved billing: inspect the local ledger before another request')
        if (self.directory / 'paid-stop.json').exists():
            raise RuntimeError('Paid execution stopped after a billing anomaly')
        if datetime.now(timezone.utc) + timedelta(seconds=90) >= datetime.fromisoformat(self.session['deadline']):
            raise RuntimeError('Live session expired or within response cutoff')
        raw = dumps(messages).encode()
        if len(raw) > 40000:
            raise ValueError('Context exceeds demo byte limit')
        inp = len(raw) + 4096 + 512 * len(messages)
        amount = 2 * (Decimal(inp) * Decimal(str(cfg['prompt_per_million'])) +
                      Decimal(cfg['max_tokens']) * Decimal(str(cfg['completion_per_million']))) / 1000000
        cid = self.store.reserve(rid, amount, self.session)
        self.store.event(rid, 'llm_request', {'call_id': cid, 'model': cfg['model'], 'reserved_usd': str(amount)})
        payload = {'model': cfg['model'], 'messages': messages, 'temperature': 0,
                   'max_tokens': cfg['max_tokens'], 'stream': False,
                   'provider': {'order': [cfg['provider']], 'allow_fallbacks': False, 'require_parameters': True,
                                'max_price': {'prompt': float(cfg['prompt_per_million']), 'completion': float(cfg['completion_per_million'])}}}
        if 'reasoning_effort' in cfg:
            payload['reasoning'] = {'effort': cfg['reasoning_effort']}
        details = {'cost': None}
        calls = self.directory / 'calls'
        calls.mkdir(mode=0o700, exist_ok=True)
        # Authorization headers are never serialized. Redact the configured key
        # defensively if a provider echoes it in a failure body or user content.
        def retain(suffix, text):
            (calls / (cid + suffix)).write_text(text.replace(self.key, '[REDACTED]'))
        try:
            retain('-request.json', dumps(payload))
            with httpx.Client(timeout=httpx.Timeout(75, connect=10), trust_env=False) as client:
                response = client.post('https://openrouter.ai/api/v1/chat/completions',
                                       headers={'Authorization': 'Bearer ' + self.key}, json=payload)
            retain('-response.txt', response.text)
            body = response.json()
            details, anomaly = billing_details(body, response.status_code, amount)
            if anomaly or details.get('cost') is None:
                (self.directory / 'paid-stop.json').write_text(dumps({'call_id': cid, 'reason': anomaly or 'Missing reported cost'}))
                raise RuntimeError('Billing unavailable or exceeds reservation')
            response.raise_for_status()
            choice = body['choices'][0]
            if choice.get('finish_reason') == 'length':
                raise RuntimeError('Truncated output; no automatic retry')
            message = choice['message']
            if not isinstance(message.get('content'), str):
                raise ValueError('Missing text content')
            self.store.settle(cid, 'completed', details)
            self.store.event(rid, 'llm_response', {'call_id': cid, **details})
            return message
        except Exception as exc:
            self.store.settle(cid, 'failed', details | {'error_type': type(exc).__name__})
            self.store.event(rid, 'llm_failed', {'call_id': cid, 'error_type': type(exc).__name__})
            raise RuntimeError('LLM request failed; retained in ledger; no retry') from None


class Demo:
    def __init__(self, directory, live_config=None, gateway_factory=PublicGateway):
        verify_examples()
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.store = Store(self.directory / 'state.sqlite')
        self.store.recover()
        self.lock = threading.Lock()
        self.cancel_event = threading.Event()
        self.active = None
        self.worker = None
        self.catalog = read(EXAMPLES / 'catalog.json')['catalog']
        self.replays = {x['id']: x for x in read(EXAMPLES / 'replays.json')}
        self.gateway = gateway_factory(self.store, self.directory, live_config, os.environ.get('OPENROUTER_API_KEY')) if live_config else None

    def config(self):
        return {'version': VERSION, 'live_enabled': self.gateway is not None,
                'backend': 'local RDFLib / fixed SPARQL', 'budget': self.store.budget(),
                'session': self.gateway.session if self.gateway else None,
                'model': self.gateway.config['model'] if self.gateway else None,
                'examples': [{'id': x['id'], 'question': x['question']} for x in self.replays.values()]}

    def start(self, body):
        question = body.get('question')
        mode = body.get('review', 'none')
        use_owl = body.get('owl', False)
        if type(use_owl) is not bool:
            raise ValueError('OWL option must be boolean')
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= 2000 or mode not in ('none', 'python', 'shacl'):
            raise ValueError('Question or review mode invalid')
        if not self.gateway:
            raise RuntimeError('Live calls disabled. Open a saved example or configure BYOK on the server.')
        if not self.lock.acquire(blocking=False):
            raise RuntimeError('One run is already active')
        try:
            rid = self.store.create({'question': question, 'review': mode, 'owl': use_owl, 'mode': 'live', 'demo_version': VERSION})
            self.active = rid
            self.cancel_event.clear()
            self.worker = threading.Thread(target=self.run, args=(rid, question, mode, use_owl), daemon=False)
            self.worker.start()
            return rid
        except Exception:
            self.lock.release()
            raise

    def cancel(self, rid):
        if rid != self.active:
            raise ValueError('No such active run')
        self.cancel_event.set()
        self.store.event(rid, 'cancel_requested', {'notice': 'In-flight request may still complete and be charged.'})

    def checkpoint(self):
        if self.cancel_event.is_set():
            raise RuntimeError('Cancelled; no further call started')

    def run(self, rid, question, mode, use_owl=False):
        self.store.status(rid, 'running')
        result = {'question': question, 'mode': 'live', 'requirements': [], 'plan': None,
                  'execution': None, 'review': None, 'answer': None}
        try:
            views = Views(EXAMPLES / 'snapshots')
            tools = CompetingTools(RDFStudyTools(views))
            info = schema(views)
            self.store.event(rid, 'snapshot_fixed', info)
            self.checkpoint()
            reqs = parse_decomposition(self.gateway.call(rid, decomposition_messages(question, info)))
            result['requirements'] = reqs
            self.store.event(rid, 'requirements', reqs)
            self.checkpoint()
            packet = planning_packet(question, reqs, info, self.catalog, 'retrieved')
            self.store.event(rid, 'catalog_retrieved', {'catalog': packet['catalog'], 'rankings': packet['rankings']})
            raw_plan = parse_plan(self.gateway.call(rid, packet['messages']), reqs)
            plan, rejected = checked_plan(raw_plan, packet['visible_tools'])
            result['plan'] = raw_plan
            self.store.event(rid, 'plan_checked', {'raw_plan': raw_plan, 'executed_plan': plan, 'rejections': rejected})
            owner = self
            class EventTools:
                def __init__(self): self.views = views
                def run(self, version, tool, args):
                    owner.checkpoint()
                    owner.store.event(rid, 'query_started', {'tool': tool, 'arguments': args})
                    value = tools.run(version, tool, args)
                    owner.store.event(rid, 'query_completed', value)
                    return value
            execution = execute_plan(plan, EventTools(), packet['visible_tools'])
            result['execution'] = execution
            report_execution = copy.deepcopy(execution)
            # The historical report assumes every raw step has an execution state.
            # Rejected steps have no query result; record that explicitly for this demo.
            for rejection in rejected:
                report_execution['steps'].setdefault(rejection['step']['id'],
                    {'issues': ['connection_rejected'], 'limited': False})
            feedback = report(raw_plan, report_execution, rejected)
            if mode != 'none':
                result['review'] = selected_review(execution, mode)
                # Full raw engine reports are for inspection, not extra model context.
                feedback['selected_qualification_review'] = {k: v for k, v in result['review'].items() if k != 'explanation'}
            if use_owl:
                from .diagnostics import selected_owl
                result['owl'] = selected_owl(execution)
                feedback['authored_ontology_classification'] = {k: result['owl'][k] for k in
                    ('assessment', 'evidence_ids', 'provenance', 'answer_scope', 'witnesses')}
            self.store.event(rid, 'review_completed', feedback)
            self.checkpoint()
            answer = parse_answer(self.gateway.call(rid, final_messages(question, reqs, raw_plan, execution, packet['catalog'], info, feedback)), reqs, execution)
            result['answer'] = answer
            self.store.event(rid, 'completed', result)
            self.store.status(rid, 'completed', dumps(result))
        except Exception as exc:
            result['error'] = {'type': type(exc).__name__, 'message': 'Run stopped. Inspect saved stages; no automatic retry.'}
            status = 'cancelled' if self.cancel_event.is_set() else 'failed'
            self.store.event(rid, status, result)
            self.store.status(rid, status, dumps(result))
        finally:
            self.active = None
            self.lock.release()
