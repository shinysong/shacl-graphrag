"""Offline bounded runner: read runtime packets only; persist failures before scoring."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from industrial_question_python import evaluate as python_arm
from industrial_question_rdf import evaluate as rdf_arm

ROOT = Path(__file__).resolve().parents[1]
ARMS = {'python_rules': python_arm, 'rdf_owl_shacl': rdf_arm}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def validate_output(output, packet):
    required = {'scene_id', 'receipt_id', 'receipt', 'links', 'products', 'impact_graph_completeness'}
    if not isinstance(output, dict) or not required <= output.keys() or output.keys() - required - {'diagnostics'}:
        raise ValueError('output keys')
    if output['scene_id'] != packet['scene_id'] or output['receipt_id'] != packet['question']['receipt_id']:
        raise ValueError('output identity')
    if output['receipt'] not in ('accept', 'violation', 'unknown', 'error'):
        raise ValueError('receipt enum')
    if output['impact_graph_completeness'] not in ('complete', 'partial', 'error'):
        raise ValueError('graph enum')
    links = output['links']
    if not isinstance(links, dict) or set(links) != {'order_line', 'inspection', 'certificate'}:
        raise ValueError('link keys')
    if any(v not in ('resolved', 'missing', 'ambiguous', 'error') for v in links.values()):
        raise ValueError('link enum')
    if 'diagnostics' in output and not isinstance(output['diagnostics'], dict):
        raise ValueError('diagnostics type')
    products = output['products']
    if not isinstance(products, list) or len(products) != 4:
        raise ValueError('product count')
    expected_ids = {(p['id'], p['revision']) for p in packet['tables']['product']}
    ids = []
    for p in products:
        if not isinstance(p, dict) or set(p) != {'id', 'revision', 'candidate', 'recheck', 'witness'}:
            raise ValueError('product keys')
        if not isinstance(p['id'], str) or not isinstance(p['revision'], str):
            raise ValueError('product identity type')
        ids.append((p['id'], p['revision']))
        if p['candidate'] not in ('yes', 'no', 'unknown', 'error') or p['recheck'] not in ('required', 'not_required', 'unknown', 'error'):
            raise ValueError('product enum')
        witness = p['witness']
        if not isinstance(witness, list) or any(not isinstance(v, str) or not v for v in witness):
            raise ValueError('witness type')
        if bool(witness) != (p['candidate'] == 'yes'):
            raise ValueError('witness presence')
    if len(set(ids)) != 4 or set(ids) != expected_ids:
        raise ValueError('product universe')
    # Schema only: never compare with expected answers or correct semantic decisions.
    json.dumps(output, allow_nan=False)


def execute(arm, packet):
    envelope = {'scene_id': packet['scene_id'], 'raw_output': None, 'status': 'error', 'error': None}
    try:
        raw = arm(copy.deepcopy(packet))
        envelope['raw_output'] = raw
    except Exception as exc:
        envelope['error'] = {'stage': 'execution', 'type': type(exc).__name__, 'message': str(exc)}
        return envelope
    try:
        validate_output(raw, packet)
    except Exception as exc:
        envelope['error'] = {'stage': 'output_schema', 'type': type(exc).__name__, 'message': str(exc)}
        return envelope
    envelope['status'] = 'ok'
    return envelope


def run(fixture, output, arms=None):
    arms = ARMS if arms is None else arms
    if set(arms) not in ({"python_rules", "rdf_owl_shacl"}, {"asserted_only"}):
        raise ValueError("unsupported arm scope")
    session = json.loads((ROOT / '_workspace/industrial-questions-v1/session.json').read_text())
    if session['status'] != 'active' or datetime.now(timezone.utc) >= datetime.fromisoformat(session['deadline_utc']):
        raise RuntimeError('session closed or expired')
    manifest = json.loads((fixture / 'manifest.json').read_text())
    scenes = manifest['scenes']
    if len(scenes) != 24 or len({s['scene_id'] for s in scenes}) != 24:
        raise ValueError('expected24 unique scenes')
    packets = []
    for entry in scenes:
        sid = entry['scene_id']
        if not isinstance(sid, str) or len(sid) != 20 or any(c not in '0123456789abcdef' for c in sid):
            raise ValueError('scene ID format')
        name = f'runtime/{sid}.json'
        if digest(fixture / name) != entry['files'][name]:
            raise ValueError('runtime hash mismatch')
        packets.append(json.loads((fixture / name).read_text()))
    if digest(fixture / 'runtime/policy.json') != manifest['runtime_policy_sha256']:
        raise ValueError('policy hash mismatch')
    output.mkdir(parents=True, exist_ok=False)
    sources = ['scripts/run_industrial_questions.py', 'scripts/industrial_question_direct.py', 'scripts/industrial_question_python.py',
               'scripts/industrial_question_rdf.py', 'research/industrial-questions/receipt-shapes.ttl',
               'research/industrial-questions/protocol-v1.json', 'research/industrial-questions/io-contract-v1.json', 'uv.lock']
    plan = {'fixture_manifest_sha256': digest(fixture / 'manifest.json'), 'scenes': [p['scene_id'] for p in packets],
            'arms': list(arms), 'planned_executions': 24 * len(arms), 'hashes': {p: digest(ROOT / p) for p in sources}}
    save(output / 'plan.json', plan)
    outcomes = []
    for packet in packets:
        for name, arm in arms.items():
            if datetime.now(timezone.utc) >= datetime.fromisoformat(session['deadline_utc']):
                raise RuntimeError('deadline reached; retain missing attempts in scorer denominator')
            result = execute(arm, packet)
            result['arm'] = name
            # Raw outputs are normal JSON for these trusted implementations. Invalid
            # non-JSON outputs retain repr separately instead of aborting the campaign.
            try:
                json.dumps(result, allow_nan=False)
            except (TypeError, ValueError):
                result['raw_output_repr'] = repr(result.pop('raw_output'))
            path = output / f"{packet['scene_id']}-{name}.json"
            save(path, result)
            outcomes.append({'file': path.name, 'sha256': digest(path), 'status': result['status']})
    save(output / 'completed.json', {'outputs': outcomes, 'executions': len(outcomes)})
    print(json.dumps({'executions': len(outcomes), 'errors': sum(r['status'] != 'ok' for r in outcomes)}))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--fixture', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--direct-only', action='store_true')
    args = ap.parse_args()
    if args.direct_only:
        from industrial_question_direct import evaluate as direct_arm
        run(args.fixture, args.output, {'asserted_only': direct_arm})
    else:
        run(args.fixture, args.output)
