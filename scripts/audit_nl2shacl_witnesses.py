"""Offline finite witness comparison of immutable raw shapes; no semantic proof."""
import argparse
from collections import Counter
from contextlib import ExitStack
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

from nl2shacl_multimodel import canonical_digest
from nl2shacl_pair_study import Runner


def sha(data):
    return hashlib.sha256(data).hexdigest()


def worker(payload):
    from rdflib import Graph, Namespace
    from rdflib.compare import isomorphic
    from pyshacl import validate
    from audit_nl2shacl_saved_meta import check
    sh = Namespace('http://www.w3.org/ns/shacl#')
    raw = payload['shape']
    meta = check(raw)
    if meta['status'] != 'meta_conformant':
        return {'status': 'unavailable', 'reason': meta['status'], 'meta': meta}
    graph = Graph().parse(data=raw, format='turtle')
    # Core only: never execute user-provided SPARQL/JS/rules or custom targets.
    forbidden = {sh.sparql, sh.js, sh.rule, sh.select, sh.ask, sh.construct, sh.target,
                 sh.validator, sh.nodeValidator, sh.propertyValidator}
    if any(predicate in forbidden for _, predicate, _ in graph):
        return {'status': 'unavailable', 'reason': 'unsupported_executable_extension'}
    raw_isomorphic = isomorphic(graph, Graph().parse(data=payload['reference'], format='turtle'))
    rows = []
    for probe in payload['witnesses']:
        try:
            conforms, report, text = validate(
                Graph().parse(data=probe['ttl'], format='turtle'),
                shacl_graph=Graph().parse(data=raw, format='turtle'), **payload['options'])
            if type(conforms) is not bool or not isinstance(report, Graph):
                raise ValueError('Nonboolean conformance or non-graph report')
            rows.append({'id': probe['id'], 'status': 'observed', 'conforms': conforms,
                         'components': sorted(str(x) for x in report.objects(None, sh.sourceConstraintComponent)),
                         'report': text})
        except Exception as exc:
            rows.append({'id': probe['id'], 'status': 'unavailable',
                         'reason': type(exc).__name__, 'detail': str(exc)})
    return {'status': 'evaluated', 'witnesses': rows,
            'raw_graph_isomorphic': raw_isomorphic}


def execute(payload, timeout):
    try:
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker'],
                                input=json.dumps(payload), capture_output=True, text=True,
                                timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {'status': 'unavailable', 'reason': 'candidate_timeout', 'timeout_seconds': timeout}
    if result.returncode:
        return {'status': 'unavailable', 'reason': 'worker_failure',
                'exit_code': result.returncode, 'stderr': result.stderr}
    try:
        return json.loads(result.stdout)
    except ValueError:
        return {'status': 'unavailable', 'reason': 'invalid_worker_response', 'stdout': result.stdout}


def account(result, probes):
    rows = result.get('witnesses', [])
    if rows and [r['id'] for r in rows] != [p['id'] for p in probes]:
        raise ValueError('Worker witness binding mismatch')
    counts = Counter(agreement=0, underconstraint_observed=0, overconstraint_observed=0, unavailable=0)
    for i, probe in enumerate(probes):
        row = rows[i] if rows else {'id': probe['id'], 'status': 'unavailable', 'reason': result.get('reason', 'unavailable')}
        if row['status'] != 'observed':
            category = 'unavailable'
        elif type(row.get('conforms')) is not bool:
            raise ValueError('Invalid worker conformance')
        elif row['conforms'] == probe['expected_reference_conforms']:
            category = 'agreement'
        elif row['conforms']:
            category = 'underconstraint_observed'
        else:
            category = 'overconstraint_observed'
        row.update(expected_reference_conforms=probe['expected_reference_conforms'], outcome=category)
        counts[category] += 1
        if not rows:
            result.setdefault('unavailable_witnesses', []).append(row)
    result['counts'] = dict(counts)
    result['interpretation'] = ('no_counterexample_among_frozen_witnesses' if counts['agreement'] == len(probes)
                                else 'finite_witness_outcomes_only')
    return result


def run(audit_path, design_path, output, timeout=30):
    audit_path, design_path, output = map(Path, (audit_path, design_path, output))
    if output.exists():
        raise FileExistsError(output)
    if not 0 < timeout <= 120:
        raise ValueError('Timeout must be in (0,120] seconds')
    snapshots = {}

    def read(path, expected=None):
        path = Path(path)
        raw = path.read_bytes()
        digest = sha(raw)
        if expected is not None and digest != expected:
            raise ValueError(f'Hash mismatch: {path}')
        if str(path) in snapshots and snapshots[str(path)] != digest:
            raise ValueError(f'Input changed: {path}')
        snapshots[str(path)] = digest
        return raw

    audit = json.loads(read(audit_path))
    design = json.loads(read(design_path))
    ledger_path = Path(audit['ledger'])
    with ExitStack() as stack:
        Runner.locks(None, stack, [ledger_path.resolve()])
        if str(ledger_path) not in audit['hashes']:
            raise ValueError('Audit missing ledger binding')
        ledger = json.loads(read(ledger_path, audit['hashes'][str(ledger_path)]))
        reservations = ledger['reservations']
        if ledger['attempts'] != len(reservations):
            raise ValueError('Ledger count mismatch')
        if any(r['status'] not in ('completed', 'failed') or
               (r['status'] == 'completed' and r.get('reported_usd') is None) for r in reservations):
            raise ValueError('Unresolved reservation')
        for name, digest in audit['hashes'].items():
            read(name, digest)
        read(design['source_pairs_path'], design['source_pairs_sha256'])
        reference = read(design['reference_path'], design['reference_sha256']).decode('utf-8')
        probes = []
        for probe in design['witnesses']:
            if type(probe['expected_reference_conforms']) is not bool:
                raise ValueError('Nonboolean expectation')
            probes.append({**probe, 'ttl': read(probe['data_path'], probe['sha256']).decode('utf-8')})
        if not probes or len({p['id'] for p in probes}) != len(probes):
            raise ValueError('Empty or duplicate witnesses')
        options = design['validation_options']
        required = {'inference': 'none', 'advanced': False, 'meta_shacl': True,
                    'do_owl_imports': False, 'abort_on_first': False,
                    'allow_infos': False, 'allow_warnings': False}
        if options != required:
            raise ValueError('Unsupported validation options')
        payload = {'reference': reference, 'witnesses': probes, 'options': options}
        baseline = execute({**payload, 'shape': reference}, timeout)
        baseline = account(baseline, probes)
        if baseline['counts']['agreement'] != len(probes):
            raise ValueError('Reference witness expectation mismatch or unavailable validation')
        if len(audit['rows']) != len(reservations):
            raise ValueError('Audit reservation count mismatch')
        selected = []
        seen = set()
        for row in audit['rows']:
            index = row['reservation_index']
            if type(index) is not int or not 0 <= index < len(reservations) or index in seen:
                raise ValueError('Invalid or duplicate reservation index')
            seen.add(index)
            reservation = reservations[index]
            if any(row[k] != reservation[k] for k in ('model', 'id', 'language', 'status')):
                raise ValueError('Audit reservation binding mismatch')
            if row['status'] == 'failed':
                if row['id'] == design['case_id']:
                    selected.append({**{k: row[k] for k in ('model', 'id', 'language', 'reservation_index')},
                                     'audit_raw_meta': row['meta'],
                                     'result': account({'status': 'unavailable', 'reason': 'terminal_provider_failure',
                                                        'reported_usd': reservation.get('reported_usd')}, probes)})
                continue
            folder = Path(ledger['output']) / f'call-{index:04d}'
            request = json.loads(read(folder / 'request.json'))
            messages = request['messages']
            if len(messages) != 2 or [m['role'] for m in messages] != ['system', 'user']:
                raise ValueError('Unexpected request messages')
            original_input = {k: reservation[k] for k in ('model', 'id', 'language')}
            original_input.update(system_prompt=messages[0]['content'], user_prompt=messages[1]['content'])
            if request['model'] != reservation['model'] or canonical_digest(original_input) != reservation['input_sha256']:
                raise ValueError('Request input hash mismatch')
            raw_path, response_path = folder / 'output.ttl', folder / 'response.json'
            for path in (raw_path, response_path):
                if str(path) not in audit['hashes']:
                    raise ValueError('Missing audit output hash binding')
            raw = read(raw_path, row['raw_sha256']).decode('utf-8')
            response = json.loads(read(response_path, audit['hashes'][str(response_path)]))
            if response['choices'][0]['message']['content'] != raw:
                raise ValueError('Raw response/output mismatch')
            if row['id'] != design['case_id']:
                continue
            if row['reference_sha256'] != design['reference_sha256']:
                raise ValueError('Audit/design reference mismatch')
            result = (execute({**payload, 'shape': raw}, timeout)
                      if row['meta']['status'] == 'meta_conformant'
                      else {'status': 'unavailable', 'reason': 'audit_raw_' + row['meta']['status']})
            selected.append({**{k: row[k] for k in ('model', 'id', 'language', 'reservation_index', 'raw_sha256')},
                             'audit_raw_meta': row['meta'], 'result': account(result, probes)})
        if not selected:
            raise ValueError('No candidates for design case')
        for name, digest in list(snapshots.items()):
            read(name, digest)
        totals = Counter()
        for row in selected:
            totals.update(row['result']['counts'])
        record = {'protocol': 'nl2shacl-finite-witness-audit-1', 'paid_calls': 0,
                  'audit': str(audit_path), 'design': str(design_path), 'hashes': snapshots,
                  'terminal_failed_reservations': sum(r['status'] == 'failed' for r in reservations),
                  'terminal_failed_unknown_cost': sum(r['status'] == 'failed' and r.get('reported_usd') is None for r in reservations),
                  'script_sha256': sha(Path(__file__).read_bytes()),
                  'versions': {p: importlib.metadata.version(p) for p in ('rdflib', 'pyshacl')},
                  'validation_options': options, 'timeout_seconds_per_shape': timeout,
                  'reference_validation': baseline, 'candidate_count': len(selected),
                  'witnesses_per_candidate': len(probes), 'summary': dict(totals), 'rows': selected,
                  'limits': design['limits'] + [
                      'Only raw proper-meta conformant candidates execute. Parse/meta/provider failures are unavailable, never semantic negatives.',
                      'SHACL Core only; executable extensions are unavailable. No targets or repairs are injected.',
                      'A timeout makes all witnesses for that candidate unavailable; partial worker progress is not recovered.',
                      'Observed under/overconstraint is relative to frozen references; path/target errors can cause either direction. Finite agreement is not semantic equivalence.']}
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', encoding='utf-8') as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit')
    parser.add_argument('--design')
    parser.add_argument('--output')
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(json.load(sys.stdin))))
    else:
        if not all((args.audit, args.design, args.output)):
            parser.error('--audit, --design and --output are required')
        print(json.dumps(run(args.audit, args.design, args.output, args.timeout)['summary']))
