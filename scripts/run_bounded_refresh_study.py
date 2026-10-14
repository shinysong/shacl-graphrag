"""One JSON bundle refresh after semantic guards; original arms are trace lineage only."""
import argparse
import copy
import json
import os
import signal
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

try:
    from scripts import run_semantic_guard_study as guard
    from scripts import run_shared_semantics_study as base
    from scripts.analyze_shared_semantics_study import reference
except ModuleNotFoundError:
    import run_semantic_guard_study as guard
    import run_shared_semantics_study as base
    from analyze_shared_semantics_study import reference

ROOT = Path(__file__).resolve().parents[1]
TASKS = guard.TASKS
CATALOGS = guard.CATALOGS
POLICIES = ('veto_only', 'selective_refresh', 'eager_refresh')
SERVICES = ('current', 'unavailable', 'stale_response')
EXPECTED = 12288 * len(CATALOGS) * len(POLICIES) * len(SERVICES)
SELECTED = ('cross', 'selective', 'semantic')


class SourceUnavailable(Exception):
    """Declared service failure, distinct from an unexpected implementation error."""


def runtime_policy(packet, catalog, policy, fetch):
    """Pure controller: no reference, fault label, or raw current source in packet.

    fetch is a zero-argument service returning JSON bytes, invoked at most once.
    Advertised current fingerprints remain fixed across a refresh.
    """
    if policy not in POLICIES:
        raise ValueError(policy)
    before = {task: guard.checks(packet, task, catalog) for task in TASKS}
    semantic_ok = all(before[t]['semantic']['status'] == 'valid' for t in TASKS)
    needs_refresh = any(before[t][c]['status'] != 'valid' for t in TASKS
                        for c in ('cross', 'selective'))
    requested = semantic_ok and (policy == 'eager_refresh' or
                                (policy == 'selective_refresh' and needs_refresh))
    updated = copy.deepcopy(packet)
    attempts, payload_bytes, error = 0, 0, None
    reason = ('semantic_block' if not semantic_ok else 'veto_only' if policy == 'veto_only'
              else 'eager' if policy == 'eager_refresh' else 'checks_failed' if needs_refresh
              else 'checks_valid')
    if requested:
        attempts = 1
        try:
            payload = fetch()
        except SourceUnavailable as exc:
            error = dict(type='SourceUnavailable', message=str(exc))
        else:
            payload_bytes = len(payload)
            source = json.loads(payload)
            publisher = packet['publisher']
            actuals = {}
            for task in TASKS:
                evidence = base.retrieve_json(source, publisher, packet['subject'])
                actuals[task] = dict(evidence=evidence, output=base.decide(evidence, publisher, task))
            updated = guard.make_packet(actuals, {'shared': publisher}, publisher,
                                        source, source, packet['subject'])
            updated['subject'] = packet['subject']
            for task in TASKS:
                for name in ('current_source', 'current_dependency', 'published_config', 'published_policy'):
                    updated['workflows'][task]['hashes'][name] = packet['workflows'][task]['hashes'][name]
    after = {task: guard.checks(updated, task, catalog) for task in TASKS}
    allowed = {task: error is None and all(after[task][c]['status'] == 'valid' for c in SELECTED)
               for task in TASKS}
    return dict(actuals=updated['actuals'], allowed=allowed, before_checks=before, after_checks=after,
                fetch_attempts=attempts, payload_bytes=payload_bytes, refresh_reason=reason, error=error,
                changed_outputs={t: packet['actuals'][t]['output'] != updated['actuals'][t]['output']
                                 for t in TASKS}, refreshed_packet=updated)


def evaluate(before, after, saved_reference, allowed):
    """Independent scoring boundary; reference never enters the runtime controller."""
    first = before['output'] == saved_reference['output']
    last = after['output'] == saved_reference['output']
    return dict(before_correct=first, after_correct=last,
                corrected_wrong_to_correct=not first and last and allowed,
                regression_correct_to_wrong=first and not last and allowed,
                **guard.evaluate(after, saved_reference, allowed))


def source_service(path, condition):
    """Each controller call gets its own hypothetical service; no memoized fetches."""
    def fetch():
        if condition == 'unavailable':
            raise SourceUnavailable('Controlled source service unavailable')
        return path.read_bytes()
    return fetch


def flush(*handles):
    for handle in handles:
        handle.flush()
        os.fsync(handle.fileno())


def run_replay(run, output):
    output.mkdir(parents=True, exist_ok=False)
    manifest = dict(protocol='bounded-refresh-1', original_run_id=run.name, status='running',
        planned_rows=EXPECTED, completed_rows=0, planned_group_calls=EXPECTED // 3, completed_group_calls=0,
        started=datetime.now(UTC).isoformat(), catalogs=CATALOGS, policies=POLICIES, services=SERVICES,
        refresh_backend='One JSON source bundle per group; original arms indicate trace lineage only.',
        service_accounting='Separate hypothetical calls across policies, catalogs, and services; no memoization.',
        scoring='Saved references independently verified before scoring; never passed to runtime policy.')
    summary, service_summary = defaultdict(Counter), defaultdict(Counter)
    guard.save(output / 'manifest.json', manifest)
    previous = {}
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f'Signal {signum}')
    for sig in (signal.SIGINT, signal.SIGTERM):
        previous[sig] = signal.signal(sig, interrupted)
    try:
        manifest['input_files'] = {str(p.relative_to(run)): guard.sha(p)
                                   for p in sorted(run.rglob('*')) if p.is_file()}
        archive = output / 'executed-source'
        archive.mkdir()
        files = [Path(__file__), ROOT / 'scripts/run_semantic_guard_study.py',
                 ROOT / 'scripts/run_shared_semantics_study.py', ROOT / 'scripts/analyze_shared_semantics_study.py',
                 ROOT / 'uv.lock', ROOT / 'tests/test_bounded_refresh_study.py']
        analyzer = ROOT / 'scripts/analyze_bounded_refresh_study.py'
        if analyzer.exists():
            files.append(analyzer)
        manifest['source_files'] = {}
        for path in files:
            (archive / path.name).write_bytes(path.read_bytes())
            manifest['source_files'][str(path.relative_to(ROOT))] = guard.sha(path)
        original = guard.read(run / 'manifest.json')
        for relative, expected_hash in original['source_files'].items():
            if guard.sha(run / 'executed-source' / Path(relative).name) != expected_hash:
                raise ValueError('Base archived source mismatch')
        rows = [json.loads(line) for line in (run / 'rows.jsonl').read_text().splitlines()]
        groups = guard.validate_rows(original, guard.read(run / 'planned-row-ids.json'), rows)
        # Scorer verifies frozen references against intended source contracts, outside the controller.
        for key, group in groups.items():
            size, seed, snapshot, _, subject, _ = key
            folder = run / 'snapshots' / f'{size}-{seed}-{snapshot}'
            source, intended = guard.read(folder / 'source.json'), guard.read(folder / 'intended-config.json')
            for task in TASKS:
                if reference(source, intended, subject, task) != group[task]['reference']:
                    raise ValueError('Saved reference differs from independent derivation')
        manifest['verified_references'] = len(rows)
        manifest['catalog_hashes'] = {name: guard.digest(value) for name, value in CATALOGS.items()}
        packets = output / 'runtime-packets'
        packets.mkdir()
        def persist(packet):
            packet_id = guard.digest(packet)
            path = packets / (packet_id + '.json')
            if not path.exists():
                guard.save(path, packet)
            return packet_id
        guard.save(output / 'manifest.json', manifest)
        with (output / 'rows.jsonl').open('x') as handle, (output / 'groups.jsonl').open('x') as group_handle:
            for key, group in sorted(groups.items()):
                size, seed, snapshot, fault, subject, arm = key
                packet = guard.load_packet(run, key, group)
                packet['subject'] = subject
                packet_id = persist(packet)
                for catalog_name, catalog in CATALOGS.items():
                    for service in SERVICES:
                        state = 'initial' if service == 'stale_response' else snapshot
                        path = run / 'snapshots' / f'{size}-{seed}-{state}' / 'source.json'
                        for policy in POLICIES:
                            outcome = runtime_policy(packet, catalog, policy, source_service(path, service))
                            after_packet_id = persist(outcome['refreshed_packet'])
                            group_id = '/'.join(map(str, (*key, catalog_name, service, policy)))
                            annotation = dict(group_id=group_id, packet_id=packet_id, after_packet_id=after_packet_id,
                                catalog=catalog_name, service=service, policy=policy, arm=arm, fault=fault,
                                size=size, seed=seed, snapshot=snapshot, subject=subject,
                                refresh_reason=outcome['refresh_reason'], error=outcome['error'])
                            group_result = dict(annotation, fetch_attempts=outcome['fetch_attempts'],
                                                payload_bytes=outcome['payload_bytes'])
                            group_handle.write(json.dumps(group_result, sort_keys=True) + '\n')
                            manifest['completed_group_calls'] += 1
                            counts = service_summary['/'.join((policy, catalog_name, service, arm, fault))]
                            counts['group_calls'] += 1
                            counts['fetch_attempts'] += outcome['fetch_attempts']
                            counts['payload_bytes'] += outcome['payload_bytes']
                            counts['service_failures'] += outcome['error'] is not None
                            for task in TASKS:
                                row = group[task]
                                result = dict(annotation, id=row['id'] + '/' + catalog_name + '/' + service + '/' + policy,
                                    base_id=row['id'], workflow=task, catalog_hash=manifest['catalog_hashes'][catalog_name],
                                    shared_fetch_attempts=outcome['fetch_attempts'], shared_payload_bytes=outcome['payload_bytes'],
                                    before_output=row['actual']['output'], output=outcome['actuals'][task]['output'],
                                    allowed=outcome['allowed'][task], changed_output=outcome['changed_outputs'][task],
                                    before_checks=outcome['before_checks'][task], after_checks=outcome['after_checks'][task],
                                    **evaluate(row['actual'], outcome['actuals'][task], row['reference'], outcome['allowed'][task]))
                                handle.write(json.dumps(result, sort_keys=True) + '\n')
                                manifest['completed_rows'] += 1
                                counts = summary['/'.join((policy, catalog_name, service, arm, fault, task))]
                                counts.update(['rows', result['outcome']])
                                for name in ('before_correct', 'after_correct', 'unnecessary_abstention',
                                             'correct_unknown_withheld', 'corrected_wrong_to_correct',
                                             'regression_correct_to_wrong', 'changed_output'):
                                    counts[name] += result[name]
                            if manifest['completed_group_calls'] % 128 == 0:
                                flush(handle, group_handle)
                                guard.save(output / 'manifest.json', manifest)
            flush(handle, group_handle)
        if manifest['completed_rows'] != EXPECTED or manifest['completed_group_calls'] != EXPECTED // 3:
            raise ValueError('Decision matrix incomplete')
        manifest['status'] = 'complete'
    except BaseException as exc:
        manifest.update(status='partial', failure_kind='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed',
                        error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        manifest['finished'] = datetime.now(UTC).isoformat()
        guard.save(output / 'summary.json', dict(rows=manifest['completed_rows'],
                   group_calls=manifest['completed_group_calls'], groups=dict(summary), service_groups=dict(service_summary)))
        guard.save(output / 'manifest.json', manifest)
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=ROOT / 'runs/20261014T063154Z-shared-semantics')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_replay(args.run, args.output), sort_keys=True))
