"""Offline exploratory analysis of scored records; never loads source datasets.

The original entity (one selected centre per corporate component) is the sampling
unit. Repeats and variants are averaged within entity before paired resampling.
No confidence interval establishes equivalence or population representativeness.
"""
import argparse
from collections import defaultdict
import hashlib
from html import escape
import json
from pathlib import Path
import random
from statistics import mean

SEED = 20261013
SAMPLES = 10000
CONFIG = {
    'seed': SEED, 'bootstrap_samples': SAMPLES, 'confidence': 0.95,
    'method': 'paired entity cluster percentile bootstrap; equal entity weights',
    'cluster': 'original entity LEI, one selected entity per corporate component',
    'repeat_handling': 'average repeats and variants within entity/condition before resampling',
    'contrasts': ['shacl-minus-code', 'shacl-minus-llm'],
    'metrics': ['wrong/all', 'unnecessary_abstentions/source_answerable'],
    'jev': 'unmeasured; excluded from primary comparisons',
    'p_values': 'not computed',
    'interpretation': 'exploratory convenience cohort; no equivalence or population claims',
}


def rate(numerator, denominator):
    return numerator / denominator if denominator else None


def outcome(row):
    if row['status'] == 'error':
        return 'errors'
    if row['status'] != 'ok':
        raise ValueError('Unknown row status')
    answer = row.get('answer', {}).get('status')
    if answer == 'abstain':
        if row.get('correct') or row.get('wrong'):
            raise ValueError('Abstention has conflicting correctness flags')
        return 'abstained'
    if answer == 'answer' and bool(row.get('correct')) != bool(row.get('wrong')):
        return 'correct' if row['correct'] else 'wrong'
    raise ValueError('Missing or contradictory scored outcome')


def summarize(rows):
    result = {}
    for condition in sorted({r['condition'] for r in rows}):
        group = [r for r in rows if r['condition'] == condition]
        counts = dict.fromkeys(('correct', 'wrong', 'abstained', 'errors'), 0)
        eligible = unnecessary = 0
        for row in group:
            category = outcome(row)
            counts[category] += 1
            if not isinstance(row.get('source_answerable'), bool):
                raise ValueError('Missing boolean source_answerable')
            eligible += row['source_answerable']
            unnecessary += category == 'abstained' and row['source_answerable']
        total = len(group)
        costs = [r['cost'] for r in group if isinstance(r.get('cost'), dict)]
        result[condition] = {
            'total': total, **counts, 'source_answerable': eligible,
            'unnecessary_abstentions': unnecessary,
            'wrong_rate_all': rate(counts['wrong'], total),
            'unnecessary_abstention_rate': rate(unnecessary, eligible),
            'coverage': rate(counts['correct'] + counts['wrong'], total),
            'risk_among_answers': rate(counts['wrong'], counts['correct'] + counts['wrong']),
            'extra_retrievals': sum(r.get('extra_retrievals', 0) for r in group),
            'api_cost': {
                'reported_usd': sum(c.get('reported_usd', 0) for c in costs) if costs else None,
                'missing_cost': sum(c.get('missing_cost', 0) for c in costs) if costs else None,
                'rows_with_cost_metadata': len(costs),
            },
        }
    return result


def entity_id(row, cases):
    case = cases.get(row['case_id'], {})
    entity = row.get('entity') or row.get('entity_lei') or row.get('lei') or case.get('entity') or case.get('entity_lei') or case.get('lei')
    if entity is None:
        candidate = row['case_id'].split('-', 1)[0]
        if len(candidate) == 20 and candidate.isalnum():
            entity = candidate
    if not entity:
        raise ValueError('Original entity LEI missing')
    return entity


def validate_grid(record):
    rows = record['rows']
    if not rows:
        raise ValueError('Empty record')
    if record.get('status') not in {'completed', 'completed_with_errors'}:
        raise ValueError('Incomplete run: inferential comparison refused')
    config = record.get('config', {})
    conditions = config.get('conditions')
    repeats = config.get('repeat_count', config.get('repeats'))
    if not conditions or not isinstance(repeats, int) or repeats < 1:
        raise ValueError('Frozen conditions and positive repeats required')
    cases = {c['case_id']: c for c in record.get('cases', [])}
    if not cases or len(cases) != len(record['cases']):
        raise ValueError('Missing or duplicate case manifest')
    observed = set()
    labels = {}
    clusters = defaultdict(list)
    for row in rows:
        key = (row['case_id'], row['condition'], row['repeat'])
        if key in observed:
            raise ValueError('Duplicate case/condition/repeat')
        observed.add(key)
        lei = entity_id(row, cases)
        manifest = cases.get(row['case_id'], {})
        if 'source_answerable' in manifest and manifest['source_answerable'] != row['source_answerable']:
            raise ValueError('Answerability differs from case manifest')
        identity = (lei, row['source_answerable'])
        if labels.setdefault(row['case_id'], identity) != identity:
            raise ValueError('Inconsistent entity or answerability within case')
        clusters[lei].append(row)
    expected = {(case, condition, repeat) for case in cases for condition in conditions for repeat in range(repeats)}
    if observed != expected:
        raise ValueError('Unequal or missing group grid: inferential comparison refused')
    return clusters


def percentile(values, probability):
    position = (len(values) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def paired_bootstrap(differences):
    if not differences:
        return {'difference': None, 'ci95': None, 'eligible_clusters': 0}
    rng = random.Random(SEED)
    n = len(differences)
    samples = sorted(mean(differences[rng.randrange(n)] for _ in range(n)) for _ in range(SAMPLES))
    return {'difference': mean(differences), 'ci95': [percentile(samples, .025), percentile(samples, .975)],
            'eligible_clusters': n}


def analyze(record):
    descriptive = summarize(record['rows'])
    clusters = validate_grid(record)
    grouped = {lei: summarize(rows) for lei, rows in sorted(clusters.items())}
    contrasts = {}
    for comparator in ('code', 'llm'):
        key = 'shacl-minus-' + comparator
        if 'shacl' not in descriptive or comparator not in descriptive:
            contrasts[key] = {'status': 'unmeasured', 'reason': 'Primary condition absent from frozen run'}
            continue
        contrasts[key] = {'status': 'measured'}
        for metric in ('wrong_rate_all', 'unnecessary_abstention_rate'):
            differences = []
            for cluster in grouped.values():
                left, right = cluster['shacl'][metric], cluster[comparator][metric]
                if (left is None) != (right is None):
                    raise ValueError('Unpaired eligible denominator')
                if left is not None:
                    differences.append(left - right)
            contrasts[key][metric] = paired_bootstrap(differences)
    return {'analysis_config': CONFIG, 'run_id': record.get('run_id'),
            'descriptive': descriptive, 'cluster_count': len(clusters),
            'cluster_summaries': grouped, 'primary_contrasts': contrasts,
            'actual_reported_api_budget': record.get('budget'),
            'cost_note': 'Reported API costs only; missing costs remain unknown; AWS and Codex excluded.'}


def svg_chart(summary):
    """Observed points only. Errors remain in coverage denominator."""
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="800" height="560" viewBox="0 0 800 560" role="img">',
             '<title>Observed risk and coverage by condition</title>',
             '<desc>Single aggregate points, not estimated curves. Risk is wrong answers divided by answers; coverage is answers divided by all attempts, including errors.</desc>',
             '<rect width="800" height="560" fill="white"/>',
             '<g fill="#202020" font-family="sans-serif" font-size="14">',
             '<text x="70" y="30">Observed risk and coverage (exploratory)</text>',
             '<path d="M80 60V460H560" fill="none" stroke="#202020"/>',
             '<text x="210" y="510">Coverage: answers / all attempts</text>',
             '<text transform="translate(22 360) rotate(-90)">Risk: wrong / answers</text>']
    colors = ['#0072b2', '#d55e00', '#009e73', '#cc79a7', '#805300', '#333333']
    for tick in range(6):
        value = tick / 5
        parts.append(f'<text x="{80 + 480*value:.1f}" y="483">{value:.1f}</text>')
        parts.append(f'<text x="45" y="{465 - 400*value:.1f}">{value:.1f}</text>')
    for index, (condition, counts) in enumerate(sorted(summary.items())):
        color = colors[index % len(colors)]
        risk, coverage = counts['risk_among_answers'], counts['coverage']
        suffix = ' (risk undefined)' if risk is None else ''
        parts.append(f'<text x="590" y="{90 + 28*index}" fill="{color}">{index+1}: {escape(condition+suffix)}</text>')
        if risk is not None and coverage is not None:
            x, y = 80 + 480*coverage, 460 - 400*risk
            parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{5+index*2}" fill="none" stroke="{color}" stroke-width="2"><title>{escape(condition)}: coverage {coverage:.6f}, risk {risk:.6f}</title></circle>')
    parts.extend(['<text x="70" y="545">Concentric marks can represent identical results. No equivalence claim.</text>', '</g></svg>'])
    return '\n'.join(parts)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('record', type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output_dir.exists():
        raise FileExistsError('Analysis output directory must be new')
    raw = args.record.read_bytes()
    result = analyze(json.loads(raw))
    result['record_sha256'] = hashlib.sha256(raw).hexdigest()
    result['analysis_script_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / 'record.json').write_bytes(raw)
    for filename, value in [('analysis.json', result), ('analysis-config.json', CONFIG)]:
        (args.output_dir / filename).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    (args.output_dir / 'risk-coverage.svg').write_text(svg_chart(result['descriptive']))
    print(json.dumps({'output_dir': str(args.output_dir), 'record_sha256': result['record_sha256']}))


if __name__ == '__main__':
    main()
