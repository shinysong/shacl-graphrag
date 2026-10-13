"""Frozen protocol 0.5-study1 comparison; no automatic API retries or resume."""
import argparse
import fcntl
import hashlib
import json
import math
import os
import platform
import random
import signal
import threading
import time
import uuid
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from rdflib import RDF, Graph

try:
    from scripts import run_gleif_comparison as core
except ModuleNotFoundError:
    import run_gleif_comparison as core

ROOT, old = core.ROOT, core.old
CONDITIONS = {'none', 'code', 'shacl', 'refresh', 'llm', 'hybrid'}


class CriticalAbort(RuntimeError):
    """Stop further calls while preserving the planned denominator."""


def atomic_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


class CampaignBudget:
    """Reservations are never refunded, including failed HTTP requests."""
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def reserve(self, usd, run_id):
        if not math.isfinite(usd) or usd <= 0:
            raise CriticalAbort('InvalidReservation')
        with self.path.with_suffix(self.path.suffix + '.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            ledger = json.loads(self.path.read_text()) if self.path.exists() else {
                'protocol': '0.5-study1', 'attempts': 0, 'reserved_usd': 0.0, 'reservations': []}
            if ledger['attempts'] >= 3200 or ledger['reserved_usd'] + usd > 5.0:
                raise CriticalAbort('CampaignBudgetLimit')
            if (not isinstance(ledger['attempts'], int) or ledger['attempts'] < 0
                    or not math.isfinite(ledger['reserved_usd']) or ledger['reserved_usd'] < 0
                    or len(ledger['reservations']) != ledger['attempts']):
                raise CriticalAbort('CorruptCampaignLedger')
            ledger['attempts'] += 1
            ledger['reserved_usd'] += usd
            ledger['reservations'].append({'run_id': run_id, 'reserved_usd': usd,
                                           'at': datetime.now(UTC).isoformat()})
            atomic_write(self.path, ledger)
            return ledger['attempts']


def path_from_root(value):
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def validate_config(config, dataset_bytes, limit_subjects=None):
    if config['protocol_version'] != '0.5-study1' or config['stage'] not in {'development', 'evaluation'}:
        raise ValueError('InvalidProtocolStage')
    if config['stage'] == 'evaluation':
        if limit_subjects is not None or config.get('frozen') is not True:
            raise ValueError('EvaluationMustBeFrozenAndComplete')
        if hashlib.sha256(dataset_bytes).hexdigest() != config.get('expected_dataset_sha256'):
            raise ValueError('EvaluationDatasetHashMismatch')
    if config['repeat_count'] != 3 or config['max_retries'] != 1:
        raise ValueError('FixedRepeatOrRetryMismatch')
    if not config['conditions'] or not set(config['conditions']) <= CONDITIONS or len(set(config['conditions'])) != len(config['conditions']):
        raise ValueError('InvalidConditions')
    if config['model'] != 'openai/gpt-4o-mini' or config['max_completion_tokens'] != 240:
        raise ValueError('FixedModelOrTokenMismatch')
    if type(config.get('max_parallel_calls', 1)) is not int or not 1 <= config.get('max_parallel_calls', 1) <= 4:
        raise ValueError('InvalidParallelism')
    if config['evidence_format'] not in {'raw', 'structured'}:
        raise ValueError('InvalidEvidenceFormat')
    if not 0 < config['max_llm_calls'] <= 3200 or not 0 < config['max_cost_usd'] <= 5:
        raise ValueError('InvalidRunBudget')
    prices = config['provider_max_price_per_million']
    if any(not isinstance(prices.get(k), (int, float)) or not math.isfinite(prices[k]) or prices[k] <= 0
           for k in ('prompt', 'completion')):
        raise ValueError('MissingOrInvalidProviderPrices')
    if limit_subjects is not None and limit_subjects < 1:
        raise ValueError('InvalidSubjectLimit')


def evidence_payload(evidence, subject, evidence_format):
    facts = core.canonical(evidence)
    if evidence_format == 'raw':
        return facts
    # No case metadata or evaluator labels enter this projection.
    return {'subject': str(subject), 'facts': facts,
            'parent_candidates': [
                {'term': str(parent),
                 'relation_fact_ids': [f['id'] for f in facts if f['s'] == str(subject)
                                       and f['p'] == str(core.EX.directParent) and f['o'] == str(parent)],
                 'types': [f for f in facts if f['s'] == str(parent) and f['p'] == str(RDF.type)]}
                for parent in sorted(set(evidence.objects(subject, core.EX.directParent)), key=str)],
            'reason_literals': [f for f in facts if f['s'] == str(subject)
                                and f['p'] == str(core.EX.exceptionReason)]}


class RunBudget:
    """One lock protects all per-run reservations and durable aggregate accounting."""
    def __init__(self, config, output):
        self.config, self.output = config, output
        self.campaign = CampaignBudget(path_from_root(config['campaign_ledger_path']))
        self.lock = threading.Lock()
        self.stopped = threading.Event()
        self.totals = {'calls': 0, 'reserved_usd': 0.0, 'reported_usd': 0.0, 'missing_cost': 0}

    def reserve(self, usd):
        with self.lock:
            if self.stopped.is_set():
                raise CriticalAbort('RunStopped')
            if (self.totals['calls'] >= self.config['max_llm_calls'] or
                    self.totals['reserved_usd'] + usd > self.config['max_cost_usd']):
                self.stopped.set()
                raise CriticalAbort('RunBudgetLimit')
            try:
                self.campaign.reserve(usd, self.output.name)
            except Exception:  # Fail closed before any network call.
                self.stopped.set()
                raise
            self.totals['calls'] += 1
            self.totals['reserved_usd'] += usd
            atomic_write(self.output / 'budget.json', self.totals)

    def report(self, actual, missing):
        with self.lock:
            self.totals['reported_usd'] += actual
            self.totals['missing_cost'] += missing
            atomic_write(self.output / 'budget.json', self.totals)

    def budget(self):
        with self.lock:
            return dict(self.totals)

    def close(self):
        pass


class StudyGateway:
    """A gateway belongs to one row; only RunBudget is shared between threads."""
    def __init__(self, config, output, prompt_path, coordinator=None):
        self.coordinator = coordinator or RunBudget(config, output)
        self.inner = old.Gateway(config, output, prompt_path=prompt_path, answer_kinds=('judgement',))
        if self.inner.model != config['model']:
            self.inner.client.close()
            raise CriticalAbort('ConfiguredModelMismatch')
        original_post = self.inner.client.post
        self.previous_reserved = 0.0
        self.accepted_calls, self.accepted_reserved = 0, 0.0

        def post(*args, **kwargs):
            delta = self.inner.reserved - self.previous_reserved
            self.coordinator.reserve(delta)
            self.previous_reserved = self.inner.reserved
            self.accepted_calls += 1
            self.accepted_reserved += delta
            return original_post(*args, **kwargs)
        self.inner.client.post = post

    def budget(self):
        return {'calls': self.accepted_calls, 'reserved_usd': self.accepted_reserved,
                'reported_usd': self.inner.actual, 'missing_cost': self.inner.missing_cost}

    def generate(self, question, evidence, path):
        before = self.budget()
        try:
            return self.inner.generate(question, evidence, path)
        except RuntimeError as exc:
            if str(exc) in {'BudgetLimit', 'PromptLimit'}:
                self.coordinator.stopped.set()
                raise CriticalAbort(str(exc)) from exc
            raise
        finally:
            current = self.budget()
            actual_delta = current['reported_usd'] - before['reported_usd']
            missing_delta = current['missing_cost'] - before['missing_cost']
            self.coordinator.report(actual_delta, missing_delta)
            if missing_delta:
                self.coordinator.stopped.set()
                raise CriticalAbort('MissingReportedCost')
            if not math.isfinite(actual_delta) or actual_delta < 0 or actual_delta > current['reserved_usd'] - before['reserved_usd'] + 1e-12:
                self.coordinator.stopped.set()
                raise CriticalAbort('ReportedCostOutsideReservation')

    def close(self):
        self.inner.client.close()


def execute_row(runtime_case, condition, shapes, directory, config, output, prompt_path, coordinator):
    gateway, critical = None, None
    result = {'status': 'error', 'error_type': None, 'answer': None,
              'trace': [], 'runtime_ms': 0, 'cost': {}}
    try:
        directory.mkdir(parents=True)
        if condition in {'llm', 'hybrid'}:
            gateway = StudyGateway(config, output, prompt_path, coordinator)
        # pySHACL may mutate its shapes graph; give each worker an independent copy.
        result, critical = run_condition(*runtime_case, condition, old.clone(shapes), directory,
                                         gateway, config['evidence_format'])
    except Exception as exc:  # noqa: BLE001 - every worker failure must remain in the grid
        result.update(status='error', error_type=type(exc).__name__, answer=None)
        if gateway:
            result['cost'] = gateway.budget()
        critical = exc if isinstance(exc, CriticalAbort) else CriticalAbort('RowExecutionFailure')
    finally:
        if gateway:
            try:
                gateway.close()
            except Exception as exc:  # noqa: BLE001 - cleanup must not discard a completed call
                result['cleanup_error_type'] = type(exc).__name__
                if result.get('answer') is not None:
                    result['answer_before_cleanup_error'] = result['answer']
                result.update(status='error', error_type=type(exc).__name__, answer=None)
                critical = critical or CriticalAbort('RowCleanupFailure')
        if critical and coordinator:
            coordinator.stopped.set()
    return result, critical


def bounded_results(tasks, worker, max_parallel, stopped):
    """Dispatch at most max_parallel rows; after a blocker drain only in-flight work."""
    iterator = iter(enumerate(tasks))
    with ThreadPoolExecutor(max_workers=max_parallel) as executor:
        pending = {}
        def fill():
            while len(pending) < max_parallel and not stopped.is_set():
                try:
                    index, task = next(iterator)
                except StopIteration:
                    break
                pending[executor.submit(worker, task)] = index
        fill()
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in sorted(done, key=lambda f: pending[f]):
                index = pending.pop(future)
                try:
                    result, critical = future.result()
                except Exception as exc:  # noqa: BLE001 - drain every other in-flight result
                    result = {'status': 'error', 'error_type': type(exc).__name__, 'answer': None,
                              'trace': [], 'runtime_ms': 0, 'cost': {},
                              'critical_reason': 'UnexpectedWorkerFailure'}
                    critical = CriticalAbort('UnexpectedWorkerFailure')
                if critical:
                    stopped.set()
                yield index, result, critical
            fill()


def model_judge(gateway, evidence, subject, directory, evidence_format):
    # Reuse the v1 response/check validator while substituting only input serialization.
    class InputAdapter:
        def generate(self, question, ignored_raw, destination):
            return gateway.generate(question, json.dumps(evidence_payload(evidence, subject, evidence_format),
                                                         ensure_ascii=False), destination)
    return core.model_judge(InputAdapter(), evidence, subject, directory)


def run_condition(source, first, subject, condition, shapes, directory, gateway=None, evidence_format='raw'):
    started = time.perf_counter()
    evidence = old.clone(first)
    result = {'status': 'running', 'trace': [], 'extra_retrievals': 0, 'judge_calls': 0,
              'answer': None, 'error_type': None}
    before = gateway.budget() if gateway and hasattr(gateway, 'budget') else {}
    critical = None
    try:
        for attempt in range(2):
            step = directory / f'attempt-{attempt}'
            step.mkdir(parents=True)
            old.write(step / 'evidence.json', evidence_payload(evidence, subject, evidence_format))
            trace = {'attempt': attempt, 'judgement': None, 'detail': {}}
            result['trace'].append(trace)
            if condition in {'none', 'refresh'}:
                judgement = 'unchecked'
            elif condition == 'code':
                judgement = core.code_judge(evidence, subject)
            elif condition in {'shacl', 'hybrid'}:
                judgement, detail = core.shacl_judge(evidence, subject, shapes, step)
                trace['detail']['shacl'] = {'judgement': judgement, **detail}
            elif condition == 'llm':
                judgement = None
            else:
                raise ValueError('UnknownCondition')
            if condition == 'llm' or (condition == 'hybrid' and judgement != 'fail'):
                result['judge_calls'] += 1
                llm, detail = model_judge(gateway, evidence, subject, step, evidence_format)
                trace['detail']['llm'] = {'judgement': llm, **detail}
                judgement = llm if condition == 'llm' else (
                    'fail' if 'fail' in (judgement, llm) else
                    'unknown' if 'unknown' in (judgement, llm) else 'pass')
            trace['judgement'] = judgement
            old.write(step / 'judgement.json', trace)
            if attempt == 0 and (condition == 'refresh' or judgement == 'unknown'):
                evidence = old.retrieve(source, subject)
                result['extra_retrievals'] += 1
                continue
            break
        result['answer'] = core.extract(evidence, subject) if judgement in {'pass', 'unchecked'} else {
            'status': 'abstain', 'kind': None, 'value': None}
        result['status'] = 'ok'
    except Exception as exc:  # noqa: BLE001 - preserve failed experimental attempts
        result.update(status='error', error_type=type(exc).__name__)
        if isinstance(exc, CriticalAbort):
            result['critical_reason'] = str(exc)
            critical = exc
    finally:
        result['runtime_ms'] = (time.perf_counter() - started) * 1000
        result['final_evidence_sha256'] = hashlib.sha256(old.graph_text(evidence).encode()).hexdigest()
        result['cost'] = {key: value - before[key] for key, value in gateway.budget().items()} if before else {}
        old.write(directory / 'result.json', result)
    return result, critical


def summarize(rows):
    # v1 summary expects absent answers for failures, not null answers.
    summary = core.summarize([{k: v for k, v in row.items() if k != 'answer' or v is not None} for row in rows])
    for value in summary.values():
        value['accuracy_all'] = value['correct'] / value['total'] if value['total'] else None
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--deterministic', action='store_true')
    parser.add_argument('--limit-subjects', type=int)
    args = parser.parse_args(argv)
    run_id = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ') + '-comparison-study-' + uuid.uuid4().hex[:8]
    output = ROOT / 'runs' / run_id
    output.mkdir(parents=True)
    record = {'run_id': run_id, 'protocol': '0.5-study1', 'status': 'initializing', 'rows': [], 'cases': [],
              'command': {'deterministic': args.deterministic, 'limit_subjects': args.limit_subjects}, 'inputs_sha256': {}}
    gateway = None
    exit_code = 0
    signal_handlers = {}
    try:
        dataset_bytes, config_bytes = args.dataset.read_bytes(), args.config.read_bytes()
        (output / 'dataset.json').write_bytes(dataset_bytes)
        (output / 'config.json').write_bytes(config_bytes)
        record['dataset_sha256'] = hashlib.sha256(dataset_bytes).hexdigest()
        record['config_sha256'] = hashlib.sha256(config_bytes).hexdigest()
        config = json.loads(config_bytes)
        record['config'] = config
        validate_config(config, dataset_bytes, args.limit_subjects)  # Before dataset JSON loading.
        dataset = json.loads(dataset_bytes)
        if not dataset.get('cohort') or any(x['split'] not in (
                {'development'} if config['stage'] == 'development' else {'reserved', 'evaluation'}) for x in dataset['cohort']):
            raise ValueError('DatasetStageMismatch')
        record['source_manifest'] = dataset.get('source_manifest')
        record['stage'] = config['stage']
        prompt_path = path_from_root(config['prompt_path'])
        paths = [Path(__file__), ROOT / 'scripts/run_gleif_comparison.py', ROOT / 'scripts/run_gleif_pilot.py',
                 ROOT / 'scripts/prepare_gleif_comparison.py', ROOT / 'experiments/comparison/shapes.ttl',
                 ROOT / 'uv.lock', ROOT / 'pyproject.toml', prompt_path]
        for index, path in enumerate(paths):
            data = path.read_bytes()
            dest = output / 'inputs' / f'{index:02d}-{path.name}'
            dest.parent.mkdir(exist_ok=True)
            dest.write_bytes(data)
            record['inputs_sha256'][str(path)] = hashlib.sha256(data).hexdigest()
        record['python'] = platform.python_version()
        record['packages'] = {p: version(p) for p in ['rdflib', 'pyshacl', 'httpx']}
        shapes = Graph().parse(output / 'inputs' / '04-shapes.ttl')
        conditions = [c for c in config['conditions'] if not args.deterministic or c not in {'llm', 'hybrid'}]
        if not conditions:
            raise ValueError('NoConditionsSelected')
        cohort = dataset['cohort']
        if args.limit_subjects:
            groups = [[x for x in cohort if x['kind'] == kind] for kind in ('parent', 'exception')]
            interleaved = [group[i] for i in range(max(map(len, groups))) for group in groups if i < len(group)]
            cohort = interleaved[:args.limit_subjects]
        runtime_cases = []
        for item in cohort:
            subject = core.LEI[item['lei']]
            for variant in config[item['kind'] + '_variants']:
                source = core.build_case(dataset, item, variant)
                first = core.omit(old.retrieve(source, subject), subject, variant)
                case_id = item['lei'] + '-' + variant
                case = {'case_id': case_id, 'entity': item['lei'], 'variant': variant,
                        'gold': {'kind': item['kind'], 'value': item.get('parent', item.get('reason'))},
                        'source_answerable': variant not in {'source_relation_missing', 'source_exception_missing',
                                                            'wrong_class', 'wrong_parent', 'invalid_reason'}}
                record['cases'].append(case)
                runtime_cases.append((source, first, subject))
                directory = output / case_id
                directory.mkdir()
                source.serialize(directory / 'source.ttl', format='turtle')
                old.write(directory / 'first-evidence.json', core.canonical(first))
        schedule = [(i, repeat, condition) for i in range(len(runtime_cases))
                    for repeat in range(config['repeat_count']) for condition in conditions]
        random.Random(config['seed']).shuffle(schedule)
        record['schedule'] = schedule
        for i, repeat, condition in schedule:
            case = record['cases'][i]
            record['rows'].append({'entity': case['entity'], 'case_id': case['case_id'], 'repeat': repeat,
                                   'condition': condition, 'source_answerable': case['source_answerable'],
                                   'status': 'error', 'error_type': 'NotExecuted', 'answer': None,
                                   'trace': [], 'runtime_ms': 0, 'cost': {}})
        record['status'] = 'running'
        atomic_write(output / 'record.json', record)  # Freeze everything before gateway initialization.
        if set(conditions) & {'llm', 'hybrid'}:
            gateway = RunBudget(config, output)
        stopped = gateway.stopped if gateway else threading.Event()
        def stop_on_signal(number, frame):
            record['interrupted_signal'] = number
            stopped.set()
        if threading.current_thread() is threading.main_thread():
            for number in (signal.SIGINT, signal.SIGTERM):
                signal_handlers[number] = signal.signal(number, stop_on_signal)
        prompt_snapshot = output / 'inputs' / f'{len(paths)-1:02d}-{prompt_path.name}'
        def worker(task):
            i, repeat, condition = task
            path = output / record['cases'][i]['case_id'] / condition / f'repeat-{repeat}'
            return execute_row(runtime_cases[i], condition, shapes, path, config, output, prompt_snapshot, gateway)
        blocker = None
        for index, result, critical in bounded_results(schedule, worker, config.get('max_parallel_calls', 1), stopped):
            row = record['rows'][index]
            i, repeat, condition = schedule[index]
            case = record['cases'][i]
            path = output / case['case_id'] / condition / f'repeat-{repeat}'
            row.update(result)
            answer = row.get('answer')
            row['correct'] = bool(answer and answer['status'] == 'answer' and all(answer[k] == case['gold'][k] for k in ('kind', 'value')))
            row['wrong'] = bool(answer and answer['status'] == 'answer' and not row['correct'])
            row['unnecessary_abstention'] = bool(answer and answer['status'] == 'abstain' and case['source_answerable'])
            try:
                old.write(path / 'result.json', row)
                atomic_write(output / 'record.json', record)
            except OSError as exc:
                row['persistence_error_type'] = type(exc).__name__
                stopped.set()
                critical = critical or CriticalAbort('RowPersistenceFailure')
            if critical and blocker is None:
                blocker = critical
        if record.get('interrupted_signal'):
            raise CriticalAbort('Interrupted')
        if blocker:
            raise blocker
        record['status'] = 'completed_with_errors' if any(r['status'] == 'error' for r in record['rows']) else 'completed'
    except Exception as exc:  # noqa: BLE001 - preserve failed experimental attempts
        record.update(status='failed', error_type=type(exc).__name__)
        if isinstance(exc, CriticalAbort):
            record['critical_reason'] = str(exc)
        exit_code = 1
    finally:
        for number, handler in signal_handlers.items():
            signal.signal(number, handler)
        record['summary'] = summarize(record['rows'])
        if gateway:
            record['budget'] = gateway.budget()
            gateway.close()
        atomic_write(output / 'record.json', record)
    print(json.dumps({'run_id': run_id, 'status': record['status'], 'summary': record['summary'],
                      'error_type': record.get('error_type'), 'budget': record.get('budget')}, indent=2))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
