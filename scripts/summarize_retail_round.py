"""Reconcile saved results only; no model calls, execution or reference repair."""
import json
from decimal import Decimal
from pathlib import Path

BASE = Path('_workspace/retail-llm-v1')
DEST = Path('docs/experiments/records/20261020-retail-round-summary.json')


def read(path):
    return json.loads(path.read_text())


def compact(metric):
    m = metric['overall']
    correct = sum(m['confusion'][s][s] for s in ('pass', 'violation', 'unknown'))
    return {'decisions': m['n'], 'reference_agreement': correct,
            'violation_tp': m['violation_tp'], 'violation_fp': m['violation_fp'],
            'violation_fn': m['violation_fn'], 'false_pass': m['false_pass_n'],
            'unnecessary_abstention': m['unnecessary_abstention_known_refs_n'],
            'unknown_reference_n': m['n']-m['known_reference_n'],
            'error': m['runtime_error_n'], 'missing_output': m['missing_output_n']}


def main():
    direct = read(BASE/'result.json')
    boundary = read(BASE/'boundary-v1/llm-result.json')
    controls = read(BASE/'boundary-v1/result.json')
    python = read(BASE/'generated-python-v1/result.json')
    shacl = read(BASE/'generated-shacl-v1/result.json')
    groups = ('random_development', 'selected_actual_development_source', 'authored_boundary_probe')
    matrix = {}
    for arm, direct_key, control_key in (
        ('authored_python', 'authored_python', 'python'),
        ('authored_shacl', 'reused_authored_shacl', 'shacl')):
        matrix[arm] = {'random_development': compact(direct['metrics'][direct_key])}
        for group in groups[1:]:
            matrix[arm][group] = compact(controls[group][control_key])
    for arm in ('raw', 'metadata'):
        matrix['direct_llm_'+arm] = {'random_development': compact(direct['metrics'][arm])}
        for group in groups[1:]:
            matrix['direct_llm_'+arm][group] = compact(boundary['split_metrics'][group][arm])
    for arm in ('adhoc', 'reusable'):
        matrix['generated_python_'+arm] = {g: compact(python['metrics'][arm][g]) for g in groups}
    matrix['generated_shacl'] = {g: compact(shacl['metrics'][g]) for g in groups}
    assert all([m[g]['decisions'] for g in groups] == [72, 6, 36] for m in matrix.values())
    files = [BASE/'campaign-budget.json', BASE/'boundary-v1/campaign-budget.json',
             BASE/'generated-python-v1/campaign-budget.json', BASE/'generated-shacl-v1/campaign-budget.json']
    reservations = [r for f in files for r in read(f)['reservations']]
    assert len(reservations) == 80
    assert len({(r['model'], r['id'], r['language']) for r in reservations}) == 80
    assert all(r['status'] == 'completed' and r['reported_usd'] is not None for r in reservations)
    costs = {}
    for r in reservations:
        if r['id'].startswith('generated-python'):
            arm = 'generated_python_reusable' if r['id'].endswith('-reusable') else 'generated_python_adhoc'
        elif r['id'].startswith('generated-shacl'):
            arm = 'generated_shacl'
        else:
            arm = 'direct_llm_'+r['id'].rsplit('-', 1)[1]
        costs.setdefault(arm, []).append(r)
    per_arm = {arm: {'model_calls': len(rr),
                    'reported_usd': str(sum((Decimal(str(r['reported_usd'])) for r in rr), Decimal(0))),
                    'nonrefunded_reserved_usd': str(sum((Decimal(str(r['upper_usd'])) for r in rr), Decimal(0))),
                    'cost_role': 'decision generation' if arm.startswith('direct') else 'artifact construction'}
               for arm, rr in costs.items()}
    total_reported = sum((Decimal(v['reported_usd']) for v in per_arm.values()), Decimal(0))
    total_reserved = sum((Decimal(v['nonrefunded_reserved_usd']) for v in per_arm.values()), Decimal(0))
    assert total_reported == Decimal('0.02410625')
    assert total_reserved == Decimal('0.21650088')
    result = {
        'scope': 'Single-model consumed-development diagnostic round, not representative business accuracy',
        'model': 'openai/gpt-6-luna',
        'cohorts': {'random_development': '24 source rows hash-selected; 72 correlated policy decisions',
                    'selected_actual_development_source': '2 previously known rare source cases; 6 policy decisions, purposive',
                    'authored_boundary_probe': '12 authored probes; 36 policy decisions, not observed source faults'},
        'matrix': matrix, 'model_cost_by_arm': per_arm,
        'campaign': {'calls': 80, 'reported_usd': str(total_reported),
                     'nonrefunded_reserved_usd': str(total_reserved), 'transport_failures': 0},
        'interpretation': [
            'No accuracy benefit observed from computed parsing metadata in these direct LLM samples.',
            'Reusable Python returns schema-valid decisions but reads cells at wrong envelope level; interface assumption caused failures.',
            'Adhoc Python sees concrete batches; reusable Python construction had empty rows and no explicit envelope schema. This is a confound.',
            'Generated SHACL received clarified interface/subset and supplied unknown precheck. No isolated language/RDF superiority inference.',
            'Three unknown authored decisions in SHACL arms come from eligibility preprocessing, not shape validation.',
            'One artifact construction per reusable arm; per-row scores are not independent construction trials.',
            'All automated arms received explicit authored policies. Adhoc here means batch-specific code, not unspecified business rules.',
        ],
        'unmeasured': ['Actual human review time/accuracy or time saved',
                       'Ambiguous/unstated-rule LLM-plus-code baseline requested in broader design',
                       'Maintenance effort, policy changes and regression burden',
                       'Untouched610row heldout evaluation and representative error prevalence',
                       'Complete end-to-end comparable latency, total Codex/operator/infrastructure cost',
                       'Cross-model or independent construction-repeat uncertainty'],
        'cost_limits': 'Reported model API costs only. Authored code construction labor and shared infrastructure are unmeasured, not free. Direct per-row calls and amortized artifact construction are different units.',
        'sources': [str(BASE/'result.json'), str(BASE/'boundary-v1/llm-result.json'),
                    str(BASE/'boundary-v1/result.json'), str(BASE/'generated-python-v1/result.json'),
                    str(BASE/'generated-shacl-v1/result.json'), *map(str, files)],
    }
    with DEST.open('x') as f:
        json.dump(result, f, indent=2)
    print(json.dumps({'matrix': {a: {g: str(m[g]['reference_agreement'])+'/'+str(m[g]['decisions']) for g in groups}
                                for a, m in matrix.items()}, 'cost_by_arm': per_arm,
                      'campaign': result['campaign']}, indent=2))


if __name__ == '__main__':
    main()
