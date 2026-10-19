"""Explicit, budgeted experimental OpenRouter generation for the local workbench.

Reuses the repository's reviewed accounting runner. No background calls, retries,
provider fallbacks, source-row transmission or runtime code generation.
"""
from __future__ import annotations
import copy
import fcntl
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '_workspace/rule-workbench-llm'
# Repository runners are standalone scripts, deliberately reused without editing.
if str(ROOT / 'scripts') not in sys.path:
    sys.path.append(str(ROOT / 'scripts'))
from nl2shacl_multimodel import Runner, canonical_digest
from nl2shacl_pair_study import Stop, atomic
from .llm import RESPONSE_SCHEMA, build_prompt, parse_response


def _session(work):
    try:
        config = json.loads((work / 'session.json').read_text())
        if config.get('schema_version') != 1:
            raise ValueError
        # Scope is server-side and cannot be raised by GUI inputs.
        if type(config['max_calls']) is not int or not 0 < config['max_calls'] <= 20:
            raise ValueError
        if not 0 < Decimal(str(config['max_usd'])) <= 2 or not 0 < Decimal(str(config['max_reported_usd'])) <= 2:
            raise ValueError
        return config
    except Exception:
        raise ValueError('서버의 LLM 실행 범위 설정을 확인하세요. 기존 사용 기록은 초기화하지 않습니다.') from None


def available_models():
    try:
        return list(_session(WORK)['models'])
    except ValueError:
        return []


def budget_status():
    if not (WORK / 'session.json').exists():
        return {'configured': False}
    config = _session(WORK)
    reservations = []
    for path in sorted((WORK / 'calls').glob('*/campaign-budget.json')):
        saved = json.loads(path.read_text())
        reservations.extend(saved['reservations'])
    return {'configured': True, 'attempts': len(reservations), 'max_calls': config['max_calls'],
            'reserved_usd': float(sum(Decimal(str(r['upper_usd'])) for r in reservations)),
            'reported_usd': float(sum(Decimal(str(r['reported_usd'] or 0)) for r in reservations)),
            'unknown_cost_attempts': sum(r['reported_usd'] is None for r in reservations),
            'max_usd': config['max_usd'], 'deadline_utc': config['deadline_utc']}


class StructuredRunner(Runner):
    def request(self, row):
        request, _ = super().request(row)
        request['response_format'] = {'type': 'json_schema', 'json_schema': {'name': 'workbench_rules', 'strict': True, 'schema': RESPONSE_SCHEMA}}
        size = len(json.dumps(request, ensure_ascii=False).encode())
        if size > 60000:
            raise Stop('PromptSizeLimit')
        setting = self.config['models'][row['model']]
        upper = ((Decimal(size + 4096) * Decimal(str(setting['input_price_per_million'])) + Decimal(self.config['max_tokens']) * Decimal(str(setting['output_price_per_million']))) / Decimal(1000000)).quantize(Decimal('0.000000000001'), rounding=ROUND_CEILING)
        return request, float(upper)


def generate_candidates(project, documents, model, *, work=None, client=None):
    """One explicit request; identical model/prompt/schema reuses saved output.

    work/client injection is for offline tests. The app uses server-owned config
    and credentials. Failed/consumed requests are never automatically retried.
    """
    work = Path(work) if work is not None else WORK
    session = _session(work)
    if model not in session['models']:
        raise ValueError('허용된 모델을 선택하세요.')
    prompt = build_prompt(project, documents)
    row = {'model': model, 'id': '', 'language': 'ko', **prompt}
    request_id = canonical_digest({'model': model, **prompt, 'response_schema': RESPONSE_SCHEMA})
    row['id'] = request_id
    work.mkdir(parents=True, exist_ok=True)
    with (work / 'generation.lock').open('a') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        directory = work / 'calls' / request_id
        ledger = directory / 'campaign-budget.json'
        cached = ledger.exists()
        if not cached:
            config = {k: copy.deepcopy(session[k]) for k in ['models','max_calls','daily_cap','max_usd','max_reported_usd','max_tokens','deadline_utc','external_ledgers','timeout_seconds']}
            # Fresh discovery includes all historical study ledgers, in addition
            # to the explicit inventory. They contribute to the global daily cap.
            history = {str(Path(p).resolve()) for p in config['external_ledgers']}
            history.update(str(p.resolve()) for p in (ROOT / '_workspace').glob('**/campaign-budget.json') if work.resolve() not in p.resolve().parents)
            previous = sorted((work / 'calls').glob('*/campaign-budget.json'))
            config['external_ledgers'] = sorted(history)
            config['predecessor_ledgers'] = {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in previous}
            config['inputs_sha256'] = canonical_digest([row])
            directory.mkdir(parents=True, exist_ok=True)
            atomic(directory / 'config.json', config)
            atomic(directory / 'input.json', [row])
            own_client = client is None
            if own_client:
                key = os.environ.get('OPENROUTER_API_KEY') or dotenv_values(ROOT / '.env').get('OPENROUTER_API_KEY')
                if not key or key.startswith('your_'):
                    raise ValueError('서버에 OPENROUTER_API_KEY 설정이 필요합니다.')
                client = httpx.Client(transport=httpx.HTTPTransport(retries=0), headers={'Authorization': 'Bearer ' + key})
            try:
                runner = StructuredRunner(config, [row], directory, client)
                runner.run(limit=1)
            except Stop as exc:
                raise ValueError(f'LLM 호출이 중단됐습니다 ({exc}). 자동 재시도하지 않습니다.') from None
            except Exception:
                raise ValueError('LLM 호출을 완료하지 못했습니다. 호출 기록을 보존했으며 자동 재시도하지 않습니다.') from None
            finally:
                if own_client:
                    client.close()
        saved = json.loads(ledger.read_text())
        reservations = saved.get('reservations', [])
        if len(reservations) != 1 or reservations[0]['status'] != 'completed':
            raise ValueError('이 요청은 이미 시도했지만 완료되지 않았습니다. 추가 호출 없이 실패 기록을 유지합니다.')
        attempt = reservations[0]
        response = json.loads((directory / 'call-0000/response.json').read_text())
        if response['choices'][0].get('finish_reason') != 'stop':
            atomic(directory / 'parse-failure.json', {'reason': 'NonStopFinishReason'})
            raise ValueError('모델 출력이 끝까지 생성되지 않았습니다. 부분 결과를 규칙으로 가져오지 않습니다.')
        content = response['choices'][0]['message']['content']
        try:
            parsed = parse_response(content, project, documents, model, request_id)
        except (ValueError, TypeError):
            atomic(directory / 'parse-failure.json', {'reason': 'SchemaOrProvenanceFailure'})
            raise ValueError('모델 결과의 형식 또는 원문 인용을 확인할 수 없습니다. 원본 응답을 보존했고 규칙은 추가하지 않았습니다.') from None
        result = {**parsed, 'model': model, 'request_id': request_id, 'cached': cached, 'cost_usd': attempt['reported_usd']}
        if not (directory / 'parsed.json').exists():
            atomic(directory / 'parsed.json', result)
        return result
