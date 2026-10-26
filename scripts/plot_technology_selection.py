"""Plot frozen descriptive results only; never launch measurement workers.

uv run --locked --with matplotlib==3.9.2 python scripts/plot_technology_selection.py
"""
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '_workspace/technology-selection/analysis-1/output/analysis.json'
OUT = ROOT / 'docs/assets/technology-selection'
ARMS = ('python_indexed', 'sqlite_recursive', 'rdf_owl_shacl')
LABELS = ('Python indexed', 'SQLite recursive', 'RDFLib + OWL-RL + pySHACL')
COLORS = ('#0072B2', '#D55E00', '#009E73')
MARKERS = ('o', 's', '^')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    record = json.loads((ROOT / 'docs/experiments/records/20261021-technology-selection-analysis.json').read_text())
    relative = str(SOURCE.relative_to(ROOT))
    if sha(SOURCE) != record['bindings'][relative]:
        raise ValueError('Frozen analysis hash mismatch')
    data = json.loads(SOURCE.read_text())
    cells = data['cells']
    index = {(c['case_id'], c['arm']): c for c in cells}
    cases = sorted({c['case_id'] for c in cells})
    if len(cells) != 66 or len(index) != 66 or len(cases) != 22:
        raise ValueError('Unexpected denominator')
    for case in cases:
        for arm in ARMS:
            if index[(case, arm)]['repeats'] != 3:
                raise ValueError('Incomplete technical repeats')
    OUT.mkdir(parents=True, exist_ok=True)
    outputs = [OUT / (name + ext) for name in ('cost-by-case', 'updates-and-repetition') for ext in ('.svg', '.png')]
    outputs += [OUT / 'figure-data.json']
    if any(p.exists() for p in outputs):
        raise FileExistsError('Preserve existing figure outputs; use an explicit new version')
    plt.rcParams.update({'font.size': 10, 'svg.fonttype': 'none', 'figure.facecolor': 'white', 'axes.facecolor': 'white'})
    labels = []
    for case in cases:
        c = index[(case, ARMS[0])]
        labels.append(f"{c['edges']}/{c['depth']}/{c['width']}/{c['seed']}")

    def panel(ax, metric, title, unit, log=True):
        for j, arm in enumerate(ARMS):
            values = [index[(case, arm)][metric] for case in cases]
            med = [v['median'] for v in values]
            error = [[v['median'] - v['min'] for v in values], [v['max'] - v['median'] for v in values]]
            ax.errorbar([i + (j-1)*.22 for i in range(22)], med, yerr=error,
                        fmt=MARKERS[j], color=COLORS[j], markersize=4, capsize=2,
                        linewidth=.8, label=LABELS[j])
        if log:
            ax.set_yscale('log')
        else:
            ax.set_ylim(bottom=0)
        ax.set_title(title)
        ax.set_ylabel(unit + (' (log scale)' if log else ''))
        ax.set_xticks(range(22), labels, rotation=90, fontsize=8)
        ax.grid(axis='y', alpha=.25)
        ax.set_xlabel('Case: total edges / depth / width / identity-order seed')

    def save(fig, name, footer):
        fig.text(.02, .015, footer, fontsize=9, va='bottom')
        fig.tight_layout(rect=(0, .075, 1, .96))
        for ext in ('.svg', '.png'):
            fig.savefig(OUT / (name + ext), dpi=180, facecolor='white')
        plt.close(fig)

    fig, axes = plt.subplots(3, 1, figsize=(13, 13))
    panel(axes[0], 'prepare_ms', 'Preparation: normalization + arm setup', 'ms')
    panel(axes[1], 'query_100_mean_ms', 'Mean query cost in the 100-query batch', 'ms / two-question bundle')
    panel(axes[2], 'whole_worker_peak_mib', 'Whole-worker peak RSS (imports and all phases included)', 'MiB', False)
    axes[0].legend(loc='upper left', ncols=3, fontsize=9)
    save(fig, 'cost-by-case', 'Points: median of 3 technical repeats; bars: min-max, NOT confidence intervals. Authored tasks; 22 cases.\nEdge growth adds unrelated edges. Depth/width combinations are not a full factorial. No RDF database server.')
    fig, axes = plt.subplots(3, 1, figsize=(13, 13))
    panel(axes[0], 'update_query_E_ms', 'Edge update + subsequent query (full rebuild policy)', 'ms')
    panel(axes[1], 'update_query_C_ms', 'Certificate update + subsequent query (full rebuild policy)', 'ms')
    axes[0].legend(loc='upper left', ncols=3, fontsize=9)
    ratios = []
    for j, arm in enumerate(ARMS[1:], start=1):
        for case in cases:
            vals = [index[(case, arm)][f'components_{n}_ms']['median'] / index[(case, ARMS[0])][f'components_{n}_ms']['median'] for n in (1, 10, 100)]
            ratios.append({'case_id': case, 'arm': arm, 'batches': [1, 10, 100], 'ratios': vals})
            axes[2].plot([1, 10, 100], vals, color=COLORS[j], marker=MARKERS[j], alpha=.45, linewidth=.7, label=LABELS[j] if case == cases[0] else None)
    axes[2].axhline(1, color='black', linestyle='--', label='Python = 1')
    axes[2].set(xscale='log', yscale='log', xlabel='Observed sequential batch size', ylabel='Cost / Python (log scale)', title='Measured component sums: paired case-median ratios')
    axes[2].set_xticks([1, 10, 100], ['1', '10', '100'])
    axes[2].legend(fontsize=9)
    axes[2].grid(alpha=.25)
    save(fig, 'updates-and-repetition', 'Update points: 3-repeat medians; bars: min-max, NOT confidence intervals. Each ratio line is one paired case.\nComponent sums = input + preparation + warmup + batch queries; NOT separate cold deployments. Lines connect measured batches only.')
    (OUT / 'figure-data.json').write_text(json.dumps({'source_sha256': sha(SOURCE), 'script_sha256': sha(Path(__file__)), 'matplotlib': matplotlib.__version__, 'denominator': data['denominator'], 'cells': cells, 'component_ratios': ratios, 'files': {p.name: sha(p) for p in outputs[:-1]}, 'limitations': ['Authored fixtures; no population inference', 'Technical min-max, not confidence intervals', 'Shared helpers and full rebuild policy', 'Sequential batch cache effects; no extrapolation']}, indent=2) + '\n')
    print(json.dumps({'figures': 4, 'cells': len(cells), 'ratio_lines': len(ratios), 'output': str(OUT)}))


if __name__ == '__main__':
    main()
