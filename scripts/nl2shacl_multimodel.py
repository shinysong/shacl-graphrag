"""Bounded multi-model generation; no gold, scoring, repairs, or retries.

Config: models maps exact request model IDs to input_price_per_million,
output_price_per_million, optional temperature/reasoning/response_aliases.
Other keys: max_calls (<=600), daily_cap (<=1000), max_usd (<=50),
max_reported_usd (<=10), max_tokens (<=8192), deadline_utc, external_ledgers,
optional timeout_seconds (<=180, default 60), predecessor_ledgers (absolute
path -> SHA256 of immutable ledger bytes),
inputs_sha256, optional ledger_path. Input rows contain exactly model, id,
language (en/ko), system_prompt, user_prompt. Hashes use canonical_digest().
External ledgers contribute daily attempt counts; dollar caps cover this shared
campaign across all models, including predecessors.
Opt-in failure_policy="isolate_transient_models" charges unknown failed costs at
full upper_usd in both caps and quarantines newly failed models across resumes.
Only HTTP429, transport timeouts and connection-establishment errors qualify.
predecessor_failure_allowlist entries contain ledger (absolute path),
reservation_sha256 (canonical_digest of the exact failed reservation), and
failure_kind="HTTP429". These are explicit operator attestations after inspecting
old failure artifacts, permitting model re-admission for unconsumed rows only;
predecessor bytes remain pinned. Every consumed row is skipped, never retried. Predecessors also contribute
daily counts, once even when listed as external. Ledgers are never reset/refunded.
"""
import argparse
from contextlib import ExitStack
from datetime import UTC, datetime
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
from pathlib import Path
import time

from dotenv import dotenv_values
import httpx

from nl2shacl_pair_study import ROOT, Stop, atomic, number, utc, Runner as PairRunner


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def money(value):
    return Decimal(str(value))


class Runner:
    locks = PairRunner.locks

    def __init__(self, config, rows, output, client, now=lambda: datetime.now(UTC)):
        self.config = config = json.loads(json.dumps(config))
        self.rows = rows = json.loads(json.dumps(rows))
        self.output, self.client, self.now = Path(output).resolve(), client, now
        for key, maximum in [('max_calls', 600), ('daily_cap', 1000), ('max_tokens', 8192)]:
            if type(config[key]) is not int or not 0 < config[key] <= maximum:
                raise ValueError('AuthorizationLimit:' + key)
        self.timeout = config.get('timeout_seconds', 60)
        if not number(self.timeout) or not 0 < self.timeout <= 180:
            raise ValueError('AuthorizationLimit:timeout_seconds')
        for key, maximum in [('max_usd', 50), ('max_reported_usd', 10)]:
            if not number(config[key]) or not 0 < config[key] <= maximum:
                raise ValueError('AuthorizationLimit:' + key)
        models = config['models']
        if not isinstance(models, dict) or not models:
            raise ValueError('InvalidModels')
        for model, settings in models.items():
            if not isinstance(model, str) or not model or not isinstance(settings, dict):
                raise ValueError('InvalidModel')
            if set(settings) - {'input_price_per_million', 'output_price_per_million', 'temperature', 'reasoning', 'response_aliases'}:
                raise ValueError('UnsupportedModelSetting')
            for key in ('input_price_per_million', 'output_price_per_million'):
                if not number(settings[key]) or settings[key] == 0:
                    raise ValueError('InvalidPrice')
            if 'temperature' in settings and (not number(settings['temperature']) or settings['temperature'] > 2):
                raise ValueError('InvalidTemperature')
            if 'reasoning' in settings and not isinstance(settings['reasoning'], dict):
                raise ValueError('InvalidReasoning')
            aliases = settings.get('response_aliases', [])
            if not isinstance(aliases, list) or any(not isinstance(a, str) or not a for a in aliases):
                raise ValueError('InvalidAliases')
        self.deadline = utc(config['deadline_utc'])
        seen = set()
        for row in rows:
            if set(row) != {'model', 'id', 'language', 'system_prompt', 'user_prompt'} or any(not isinstance(v, str) or not v for v in row.values()):
                raise ValueError('InvalidInput')
            key = self.key(row)
            if row['model'] not in models or row['language'] not in ('en', 'ko') or key in seen:
                raise ValueError('DuplicateOrInvalidInput')
            seen.add(key)
        if config['inputs_sha256'] != canonical_digest(rows):
            raise ValueError('InputDigestMismatch')
        self.ledger = Path(config.get('ledger_path', self.output / 'campaign-budget.json')).resolve()
        if not isinstance(config['external_ledgers'], list):
            raise ValueError('InvalidExternalLedgers')
        self.externals = sorted({Path(p).resolve() for p in config['external_ledgers']})
        if self.ledger in self.externals:
            raise ValueError('SelfExternalLedger')
        predecessors = config.get('predecessor_ledgers', {})
        if not isinstance(predecessors, dict):
            raise ValueError('InvalidPredecessorLedgers')
        self.predecessors = {}
        for name, digest in predecessors.items():
            if not isinstance(name, str) or not Path(name).is_absolute() or not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                raise ValueError('InvalidPredecessorLedger')
            path = Path(name).resolve()
            if path == self.ledger or path in self.predecessors:
                raise ValueError('DuplicateOrSelfPredecessorLedger')
            self.predecessors[path] = digest
        self.isolate = config.get('failure_policy', 'stop') == 'isolate_transient_models'
        if config.get('failure_policy', 'stop') not in ('stop', 'isolate_transient_models'):
            raise ValueError('InvalidFailurePolicy')
        self.allowed_failures = set()
        allowlist = config.get('predecessor_failure_allowlist', [])
        if not isinstance(allowlist, list) or (allowlist and not self.isolate):
            raise ValueError('InvalidFailureAllowlist')
        for entry in allowlist:
            if not isinstance(entry, dict) or set(entry) != {'ledger', 'reservation_sha256', 'failure_kind'}:
                raise ValueError('InvalidFailureAllowlist')
            if not isinstance(entry['ledger'], str) or not Path(entry['ledger']).is_absolute():
                raise ValueError('InvalidFailureAllowlist')
            path = Path(entry['ledger']).resolve()
            digest = entry['reservation_sha256']
            if path not in self.predecessors or entry['failure_kind'] != 'HTTP429' or not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                raise ValueError('InvalidFailureAllowlist')
            binding = (path, digest)
            if binding in self.allowed_failures:
                raise ValueError('DuplicateFailureAllowlist')
            self.allowed_failures.add(binding)
        self.binding = canonical_digest(config)

    @staticmethod
    def key(row):
        return row['model'], row['id'], row['language']

    def load(self):
        if not self.ledger.exists():
            return {'protocol': 'nl2shacl-multimodel-1', 'binding': self.binding,
                    'output': str(self.output), 'attempts': 0, 'reservations': []}
        data = json.loads(self.ledger.read_text())
        if data['binding'] != self.binding or data['attempts'] != len(data['reservations']) or data['output'] != str(self.output):
            raise Stop('LedgerMismatch')
        seen = set()
        for r in data['reservations']:
            if self.key(r) in seen or not number(r['upper_usd']) or (r['reported_usd'] is not None and not number(r['reported_usd'])):
                raise Stop('InvalidLedger')
            seen.add(self.key(r))
        return data

    def reserve(self, row, upper):
        with ExitStack() as stack:
            self.locks(stack, [self.ledger, *self.externals, *self.predecessors])
            data = self.load()
            # Check every configured external even on a completed-only resume.
            external = []
            predecessor = []
            allowed = set()
            for path in sorted(set(self.externals) | self.predecessors.keys()):
                raw = path.read_bytes()
                if path in self.predecessors and hashlib.sha256(raw).hexdigest() != self.predecessors[path]:
                    raise Stop('PredecessorDigestMismatch')
                saved = json.loads(raw)
                external.extend(saved['reservations'])
                if path in self.predecessors:
                    if type(saved.get('attempts')) is not int or saved['attempts'] != len(saved['reservations']) or any(not number(r['upper_usd']) or (r['reported_usd'] is not None and not number(r['reported_usd'])) for r in saved['reservations']):
                        raise Stop('InvalidPredecessorLedger')
                    for r in saved['reservations']:
                        binding = (path, canonical_digest(r))
                        if binding in self.allowed_failures:
                            if r['status'] != 'failed':
                                raise Stop('InvalidAllowedFailure')
                            allowed.add(binding)
                    predecessor.extend(saved['reservations'])
            if allowed != self.allowed_failures:
                raise Stop('FailureAllowlistMismatch')
            campaign = [*data['reservations'], *predecessor]
            quarantined = set()
            consumed = set()
            for r in campaign:
                admitted_old = any(digest == canonical_digest(r) for _, digest in allowed)
                if not self.isolate:
                    if r['status'] != 'completed' or r['reported_usd'] is None:
                        raise Stop('UnresolvedPriorAttempt')
                else:
                    if r['reported_usd'] is not None and money(r['reported_usd']) > money(r['upper_usd']):
                        raise Stop('UnresolvedPriorAttempt')
                    model = r.get('model')
                    if model not in self.config['models']:
                        raise Stop('InvalidCampaignModel')
                    aliases = self.config['models'][model].get('response_aliases', [])
                    if r.get('response_model') is not None and r['response_model'] not in [model, *aliases]:
                        raise Stop('UnresolvedPriorAttempt')
                    if r['status'] == 'completed' and r['reported_usd'] is not None:
                        pass
                    elif r['status'] == 'failed' and (admitted_old or r.get('isolated_failure') in ('HTTP429', 'Timeout', 'ConnectionError')):
                        if not admitted_old:
                            quarantined.add(model)
                    else:
                        raise Stop('UnresolvedPriorAttempt')
                # Historical cost-only predecessors remain supported in stop mode.
                if all(field in r for field in ('model', 'id', 'language')):
                    key = self.key(r)
                    if key in consumed:
                        raise Stop('DuplicateConsumedInput')
                    consumed.add(key)
                    matching = next((item for item in self.rows if self.key(item) == key), None)
                    if matching is not None and r.get('input_sha256') != canonical_digest(matching):
                        raise Stop('ConsumedInputMismatch')
                    if self.isolate and not isinstance(r.get('input_sha256'), str):
                        raise Stop('ConsumedInputMismatch')
            if self.key(row) in consumed or row['model'] in quarantined:
                return None
            current = self.now().astimezone(UTC)
            if current >= self.deadline:
                raise Stop('Deadline')
            daily = sum(utc(r['at']).date() == current.date() for r in [*data['reservations'], *external])
            reserved = sum((max(money(r['upper_usd']), money(r['reported_usd'] or 0)) for r in campaign), Decimal(0))
            reported = sum((money(r['reported_usd']) if r['reported_usd'] is not None else money(r['upper_usd']) for r in campaign), Decimal(0))
            if len(campaign) >= self.config['max_calls'] or daily >= self.config['daily_cap'] or reserved + money(upper) > money(self.config['max_usd']) or reported + money(upper) > money(self.config['max_reported_usd']):
                raise Stop('BudgetLimit')
            index = data['attempts']
            data['attempts'] += 1
            data['reservations'].append({'model': row['model'], 'id': row['id'], 'language': row['language'], 'at': current.isoformat(), 'upper_usd': upper, 'reported_usd': None, 'status': 'reserved', 'input_sha256': canonical_digest(row)})
            atomic(self.ledger, data)
            return index

    def update(self, index, **fields):
        with ExitStack() as stack:
            self.locks(stack, [self.ledger])
            data = self.load()
            data['reservations'][index].update(fields)
            atomic(self.ledger, data)

    def request(self, row):
        settings = self.config['models'][row['model']]
        request = {'model': row['model'], 'messages': [{'role': 'system', 'content': row['system_prompt']}, {'role': 'user', 'content': row['user_prompt']}], 'max_tokens': self.config['max_tokens'], 'usage': {'include': True}, 'provider': {'allow_fallbacks': False, 'require_parameters': True, 'max_price': {'prompt': settings['input_price_per_million'], 'completion': settings['output_price_per_million']}}}
        for key in ('temperature', 'reasoning'):
            if key in settings:
                request[key] = settings[key]
        size = len(json.dumps(request, ensure_ascii=False).encode())
        if size > 60000:
            raise Stop('PromptSizeLimit')
        upper = ((Decimal(size + 4096) * money(settings['input_price_per_million']) + Decimal(self.config['max_tokens']) * money(settings['output_price_per_million'])) / Decimal(1000000)).quantize(Decimal('0.000000000001'), rounding=ROUND_CEILING)
        return request, float(upper)

    def run(self, limit=None):
        if limit is not None and (type(limit) is not int or limit <= 0):
            raise ValueError('InvalidLimit')
        completed = 0
        attempted = 0
        for row in self.rows:
            if limit is not None and (attempted if self.isolate else completed) >= limit:
                break
            request, upper = self.request(row)
            index = self.reserve(row, upper)
            if index is None:
                continue
            attempted += 1
            path = self.output / f'call-{index:04d}'
            isolation_kind = None
            response_safe = True
            started = time.monotonic()
            try:
                path.mkdir(parents=True, exist_ok=False)
                atomic(path / 'request.json', request)
                remaining = (self.deadline - self.now()).total_seconds()
                if remaining <= 0:
                    raise Stop('DeadlineAfterReservation')
                response = self.client.post('https://openrouter.ai/api/v1/chat/completions', json=request, timeout=min(self.timeout, remaining))
                latency = time.monotonic() - started
                atomic(path / 'response.json', response.content)
                atomic(path / 'transport.json', {'status_code': response.status_code, 'latency_seconds': latency})
                if response.status_code == 429:
                    isolation_kind = 'HTTP429'
                try:
                    raw = response.json()
                except ValueError:
                    if response.status_code != 429:
                        raise
                    raw = {}
                if not isinstance(raw, dict):
                    raise Stop('InvalidResponse')
                cost = raw.get('usage', {}).get('cost')
                metadata = {'response_model': raw.get('model'), 'provider': raw.get('provider'), 'usage': raw.get('usage'), 'latency_seconds': latency}
                atomic(path / 'metadata.json', metadata)
                if cost is not None and number(cost):
                    self.update(index, reported_usd=cost)
                aliases = self.config['models'][row['model']].get('response_aliases', [])
                response_safe = ((cost is None or (number(cost) and money(cost) <= money(upper)))
                                 and (raw.get('model') is None or raw['model'] in [row['model'], *aliases]))
                response.raise_for_status()
                content = raw['choices'][0]['message']['content']
                if not isinstance(content, str):
                    raise Stop('NonTextResponse')
                atomic(path / 'output.ttl', content.encode())
                aliases = self.config['models'][row['model']].get('response_aliases', [])
                if raw.get('model') not in [row['model'], *aliases]:
                    raise Stop('ModelMismatch')
                if cost is None or not number(cost) or money(cost) > money(upper):
                    raise Stop('UnresolvedOrExcessCost')
                self.update(index, status='completed', **metadata)
                completed += 1
            except Exception as exc:
                # Do not serialize arbitrary exceptions (credentials may be present).
                if isinstance(exc, httpx.TimeoutException):
                    isolation_kind = 'Timeout'
                elif isinstance(exc, httpx.ConnectError):
                    isolation_kind = 'ConnectionError'
                safe_failure = self.isolate and response_safe and (
                    isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)) or
                    (isolation_kind == 'HTTP429' and isinstance(exc, httpx.HTTPStatusError)))
                fields = {'isolated_failure': isolation_kind} if safe_failure else {}
                self.update(index, status='failed', latency_seconds=time.monotonic() - started, **fields)
                if path.is_dir():
                    atomic(path / 'failure.json', {'error_type': type(exc).__name__, 'reason': str(exc) if isinstance(exc, Stop) else 'CallFailure'})
                if safe_failure:
                    continue
                raise Stop('CallFailedStopCampaign') from None
        return {'completed_this_run': completed, 'attempted_this_run': attempted, 'campaign_attempts': self.load()['attempts']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('config', 'inputs', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    config, rows = json.loads(Path(args.config).read_text()), json.loads(Path(args.inputs).read_text())
    key = dotenv_values(ROOT / '.env').get('OPENROUTER_API_KEY')
    if not key or key.startswith('your_'):
        raise Stop('MissingCredential')
    with httpx.Client(transport=httpx.HTTPTransport(retries=0), headers={'Authorization': 'Bearer ' + key}) as client:
        runner = Runner(config, rows, args.output, client)
        try:
            result = runner.run(limit=args.limit)
        except Stop as exc:
            result = {'status': 'stopped', 'reason': str(exc)}
        print(json.dumps(result))
        if result.get('status') == 'stopped':
            raise SystemExit(1)


if __name__ == '__main__':
    main()
