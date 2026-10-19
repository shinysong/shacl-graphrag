"""Bounded one-shot NL2SHACL generation. No gold, repair, scoring, or retries."""
import argparse
from contextlib import ExitStack
from datetime import UTC, datetime
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

from dotenv import dotenv_values
import httpx

ROOT = Path(__file__).resolve().parents[1]


class Stop(RuntimeError):
    pass


def atomic(path, value):
    """Persist bytes before atomic replacement, including the directory entry."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False, indent=2).encode()
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def utc(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('TimestampNeedsTimezone')
    return result.astimezone(UTC)


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


class Runner:
    def __init__(self, config, rows, output, client, now=lambda: datetime.now(UTC)):
        self.config, self.rows, self.output, self.client, self.now = config, rows, Path(output), client, now
        for name in ('max_calls', 'max_tokens', 'daily_cap'):
            if type(config[name]) is not int or config[name] <= 0:
                raise ValueError('InvalidLimit')
        if config['daily_cap'] > 500:
            raise ValueError('DailyLimitExceedsAuthorization')
        for name in ('max_usd', 'input_price_per_million', 'output_price_per_million'):
            if not number(config[name]) or config[name] == 0:
                raise ValueError('InvalidPrice')
        if config['max_calls'] > 120 or config['max_usd'] > 5:
            raise ValueError('CampaignLimitExceedsAuthorization')
        if not isinstance(config['model'], str) or not config['model']:
            raise ValueError('InvalidModel')
        self.deadline = utc(config['deadline_utc'])
        seen = set()
        for row in rows:
            if set(row) != {'id', 'language', 'system_prompt', 'user_prompt'} or any(not isinstance(v, str) or not v for v in row.values()):
                raise ValueError('InvalidInput')
            key = (row['id'], row['language'])
            if row['language'] not in ('en', 'ko') or key in seen:
                raise ValueError('DuplicateOrInvalidLanguage')
            seen.add(key)
        digest = hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if config.get('inputs_sha256') != digest:
            raise ValueError('InputDigestMismatch')
        self.ledger = Path(config.get('ledger_path', self.output / 'campaign-budget.json')).resolve()
        self.externals = sorted({Path(p).resolve() for p in config['external_ledgers']} - {self.ledger})
        self.binding = hashlib.sha256(json.dumps(config, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def load(self):
        if self.ledger.exists():
            data = json.loads(self.ledger.read_text())
            if data['binding'] != self.binding or data['attempts'] != len(data['reservations']):
                raise Stop('LedgerMismatch')
            if any(not number(r['upper_usd']) or (r['reported_usd'] is not None and not number(r['reported_usd'])) for r in data['reservations']):
                raise Stop('InvalidLedgerCost')
            return data
        return {'protocol': 'nl2shacl-pair-1', 'binding': self.binding, 'attempts': 0, 'reservations': []}

    def locks(self, stack, paths):
        for path in sorted(set(paths)):
            path.parent.mkdir(parents=True, exist_ok=True)
            stream = stack.enter_context(path.with_suffix('.lock').open('a+'))
            fcntl.flock(stream, fcntl.LOCK_EX)

    def reserve(self, row, upper):
        with ExitStack() as stack:
            self.locks(stack, [self.ledger, *self.externals])
            data = self.load()
            if any(r['status'] != 'completed' or r['reported_usd'] is None for r in data['reservations']):
                raise Stop('UnresolvedPriorAttempt')
            for reservation in data['reservations']:
                if (reservation['id'], reservation['language']) == (row['id'], row['language']):
                    digest = hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                    if reservation['input_sha256'] != digest:
                        raise Stop('ConsumedInputMismatch')
                    return None
            current = self.now()
            if current >= self.deadline:
                raise Stop('Deadline')
            reservations = list(data['reservations'])
            for path in self.externals:
                # Missing configured ledgers fail closed, never silently count zero.
                reservations.extend(json.loads(path.read_text())['reservations'])
            daily = sum(utc(r['at']).date() == current.date() for r in reservations)
            spend = sum(max(r['upper_usd'], r['reported_usd'] or 0) for r in data['reservations'])
            if data['attempts'] >= self.config['max_calls'] or spend + upper > self.config['max_usd'] or daily >= self.config['daily_cap']:
                raise Stop('BudgetLimit')
            index = data['attempts']
            data['attempts'] += 1
            data['reservations'].append({'id': row['id'], 'language': row['language'], 'at': current.isoformat(), 'upper_usd': upper, 'reported_usd': None, 'status': 'reserved', 'output': str(self.output.resolve()), 'input_sha256': hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()})
            atomic(self.ledger, data)
            return index

    def update(self, index, **fields):
        with ExitStack() as stack:
            self.locks(stack, [self.ledger])
            data = self.load()
            data['reservations'][index].update(fields)
            atomic(self.ledger, data)

    def run(self):
        completed = 0
        for row in self.rows:
            cfg = self.config
            request = {'model': cfg['model'], 'messages': [{'role': 'system', 'content': row['system_prompt']}, {'role': 'user', 'content': row['user_prompt']}], 'temperature': 0, 'reasoning': {'enabled': False}, 'max_tokens': cfg['max_tokens'], 'usage': {'include': True}, 'provider': {'allow_fallbacks': False, 'require_parameters': True, 'max_price': {'prompt': cfg['input_price_per_million'], 'completion': cfg['output_price_per_million']}}}
            size = len(json.dumps(request, ensure_ascii=False).encode())
            if size > 60000:
                raise Stop('PromptSizeLimit')
            # UTF-8 byte count plus framing allowance conservatively bounds input tokens.
            upper = ((size + 4096) * cfg['input_price_per_million'] + cfg['max_tokens'] * cfg['output_price_per_million']) / 1e6
            index = self.reserve(row, upper)
            if index is None:
                continue
            path = self.output / f'call-{index:04d}'
            try:
                path.mkdir(parents=True, exist_ok=False)
                atomic(path / 'request.json', request)
                remaining = (self.deadline - self.now()).total_seconds()
                if remaining <= 0:
                    raise Stop('DeadlineAfterReservation')
                response = self.client.post('https://openrouter.ai/api/v1/chat/completions', json=request, timeout=min(60, remaining))
                atomic(path / 'response.json', response.content)
                raw = response.json()
                cost = raw.get('usage', {}).get('cost')
                if cost is not None and number(cost):
                    self.update(index, reported_usd=cost)
                response.raise_for_status()
                content = raw['choices'][0]['message']['content']
                if not isinstance(content, str):
                    raise Stop('NonTextResponse')
                atomic(path / 'output.ttl', content.encode())
                if raw.get('model') != cfg['model']:
                    raise Stop('ModelMismatch')
                if cost is None or not number(cost) or cost > upper:
                    raise Stop('UnresolvedOrExcessCost')
                self.update(index, status='completed')
                completed += 1
            except Exception as exc:
                # Exception messages can contain credentials; record only the class.
                atomic(path / 'failure.json', {'error_type': type(exc).__name__, 'reason': str(exc) if isinstance(exc, Stop) else 'CallFailure'})
                self.update(index, status='failed')
                raise Stop('CallFailedStopCampaign') from None
        return {'completed_this_run': completed, 'campaign_attempts': self.load()['attempts']}


def main():
    parser = argparse.ArgumentParser()
    for name in ('config', 'inputs', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    config, rows = json.loads(Path(args.config).read_text()), json.loads(Path(args.inputs).read_text())
    key = dotenv_values(ROOT / '.env').get('OPENROUTER_API_KEY')
    if not key or key.startswith('your_'):
        raise Stop('MissingCredential')
    with httpx.Client(transport=httpx.HTTPTransport(retries=0), headers={'Authorization': 'Bearer ' + key}) as client:
        runner = Runner(config, rows, args.output, client)
        try:
            result = runner.run()
        except Stop as exc:
            result = {'status': 'stopped', 'reason': str(exc)}
        print(json.dumps(result))
        if result.get('status') == 'stopped':
            raise SystemExit(1)


if __name__ == '__main__':
    main()
