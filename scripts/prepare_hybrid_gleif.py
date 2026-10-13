"""Freeze bounded snapshot-connectivity questions from pinned GLEIF RR, offline.

This transfer convenience sample is neither external financial truth nor a
representative/held-out benchmark. Prior consumed components are excluded.
"""
import argparse
import hashlib
import json
from collections import defaultdict, deque
from pathlib import Path

from prepare_gleif import rows
from prepare_gleif_comparison import ACCOUNTING, DIRECT, Components, active, sha256

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261013


def rank(value, purpose):
    return hashlib.sha256(f'{SEED}:hybrid:{purpose}:{value}'.encode()).hexdigest(), value


def identities(dataset):
    result = set(dataset.get('entities', {}))
    for item in dataset['cohort']:
        result.add(item['lei'])
        if item.get('parent'):
            result.add(item['parent'])
    return result


def neighborhood(adjacency, subject, bound):
    """All outgoing records of nodes at shortest distance < bound, including cycles."""
    distance, records = {subject: 0}, set()
    pending = deque([subject])
    while pending:
        node = pending.popleft()
        if distance[node] == bound:
            continue
        for target, ordinal in adjacency.get(node, []):
            records.add(ordinal)
            if target not in distance:
                distance[target] = distance[node] + 1
                pending.append(target)
    return distance, records


def prepare(manifest_path, output_dir, prior_paths, *, per_depth=4, depths=(4, 2, 1)):
    manifest_path, output_dir = Path(manifest_path), Path(output_dir)
    if output_dir.exists():
        raise FileExistsError('Refusing to overwrite frozen preparation')
    if per_depth < 1 or not depths or any(d < 1 for d in depths) or len(set(depths)) != len(depths):
        raise ValueError('Invalid depth or cohort size')
    manifest = json.loads(manifest_path.read_text())
    priors = [json.loads(Path(p).read_text()) for p in prior_paths]
    if not priors:
        raise ValueError('Prior cohort exclusion inputs required')
    info = manifest['files']['rr']
    for prior in priors:
        pinned = prior['source_manifest']
        if (pinned['publish_date'] != manifest['publish_date']
                or pinned['files']['rr']['sha256'] != info['sha256']
                or pinned['files']['rr']['record_count'] != info['record_count']):
            raise ValueError('Pinned release mismatch')
    archive = manifest_path.parent / 'rr.csv.zip'
    if sha256(archive) != info['sha256']:
        raise ValueError('RR hash mismatch')
    groups, adjacency, node_source = Components(), defaultdict(list), {}
    count = 0
    for count, row in enumerate(rows(archive), 1):
        if active(row) and row['Relationship.RelationshipType'] in ACCOUNTING:
            child, parent = row['Relationship.StartNode.NodeID'], row['Relationship.EndNode.NodeID']
            groups.union(child, parent)
            node_source.setdefault(child, count)
            node_source.setdefault(parent, count)
            if row['Relationship.RelationshipType'] == DIRECT:
                adjacency[child].append((parent, count))
    if count != info['record_count']:
        raise ValueError('RR row count mismatch')
    excluded = set().union(*(identities(p) for p in priors))
    forbidden = {groups.find(node) for node in excluded}
    # Stable component names do not depend on union-find root implementation.
    members = defaultdict(list)
    for node in list(groups.parents):
        members[groups.find(node)].append(node)
    component_ids = {group: min(nodes) for group, nodes in members.items()}
    available = sorted((n for n in adjacency if groups.find(n) not in forbidden),
                       key=lambda n: rank(n, 'negative'))
    chosen, used, eligible_counts = [], set(), {}
    for depth in depths:
        candidates = []
        for subject in adjacency:
            group = groups.find(subject)
            if group in forbidden:
                continue
            distances, evidence = neighborhood(adjacency, subject, depth)
            targets = [n for n, d in distances.items() if d == depth]
            if targets:
                candidates.append((subject, targets, distances, evidence))
        eligible_counts[str(depth)] = len(candidates)
        selected_count = 0
        for subject, targets, distances, evidence in sorted(candidates, key=lambda c: rank(c[0], f'depth{depth}')):
            group = groups.find(subject)
            if group in used:
                continue
            # Reserve a distinct component for a real disconnected distractor.
            negative_subject = next((n for n in available
                                     if groups.find(n) not in used | {group}), None)
            if negative_subject is None:
                continue
            negative, distractor_ordinal = min(adjacency[negative_subject])
            chosen.append({'subject': subject, 'depth': depth,
                           'positive': min(targets, key=lambda n: rank(n, 'target')),
                           'negative': negative,
                           'ordinals': sorted(evidence | {distractor_ordinal}),
                           'component': component_ids[group],
                           'distractor_component': component_ids[groups.find(negative_subject)]})
            used.update({group, groups.find(negative_subject)})
            selected_count += 1
            if selected_count == per_depth:
                break
    needed = set()
    for item in chosen:
        needed.update(item['ordinals'])
        needed.update(node_source[item[k]] for k in ('subject', 'positive', 'negative'))
    raw = {ordinal: row for ordinal, row in enumerate(rows(archive), 1) if ordinal in needed}

    def provenance(ordinal):
        return {'source_sha256': info['sha256'], 'csv_data_row': ordinal}

    def normalized(ordinal):
        row = raw[ordinal]
        return {'id': f'rr-{ordinal}', 'subject': row['Relationship.StartNode.NodeID'],
                'object': row['Relationship.EndNode.NodeID'], 'relation': 'direct',
                'status': row['Relationship.RelationshipStatus'],
                'registration': row['Registration.RegistrationStatus'],
                'period_fields': {k: v for k, v in row.items() if 'Period' in k},
                'provenance': provenance(ordinal)}

    cases, evaluator = [], {}
    for index, item in enumerate(chosen):
        for label in ('positive', 'negative'):
            target = item[label]
            case_id = f'gleif-{index * 2 + (1 if label == "positive" else 2):03d}'
            contract = {'subject': item['subject'], 'target': target,
                        'max_hops': item['depth'], 'relation': 'direct',
                        'status': 'ACTIVE', 'registration': 'PUBLISHED',
                        'scope': 'supplied_snapshot'}
            cases.append({'id': case_id,
                          'question': f'In the supplied snapshot, is {target} reachable from '
                                      f'{item["subject"]} by 1 to {item["depth"]} directed '
                                      'ACTIVE/PUBLISHED direct accounting-consolidation edges?',
                          'contract': contract,
                          'records': [normalized(n) for n in item['ordinals']]})
            evaluator[case_id] = {'expected_decision': 'reachable' if label == 'positive' else 'not_reachable',
                                  'depth': item['depth'], 'selected_component': item['component'],
                                  'distractor_component': item['distractor_component'],
                                  'query_provenance': {k: provenance(node_source[v]) for k, v in
                                                       [('subject', item['subject']), ('target', target)]}}
    output_dir.mkdir(parents=True, exist_ok=False)

    def write(name, value):
        (output_dir / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')

    write('runtime-cases.json', cases)
    write('evaluator.json', evaluator)
    write('selected-raw-rr.json', {f'rr-{n}': row for n, row in raw.items()})
    (output_dir / 'source-manifest.json').write_bytes(manifest_path.read_bytes())
    result = {'schema_version': 1, 'seed': SEED, 'rr_rows_scanned': count,
              'rr_sha256': info['sha256'], 'source_url': info.get('url'),
              'requested_centers_per_depth': per_depth,
              'selected_centers_per_depth': {str(d): sum(x['depth'] == d for x in chosen) for d in depths},
              'eligible_centers_before_component_deduplication': eligible_counts,
              'case_count': len(cases), 'excluded_identity_count': len(excluded),
              'excluded_components': len(forbidden),
              'prior_inputs_sha256': {str(p): sha256(Path(p)) for p in prior_paths},
              'selection': 'Depth order '+str(list(depths))+'; ascending SHA256(seed:hybrid:depthN:LEI); '
                           'one center per undirected ACTIVE/PUBLISHED direct+ultimate component; '
                           'exclude all prior pilot and consumed development/reserved components.',
              'evidence_scope': 'Complete outgoing ACTIVE/PUBLISHED DIRECT neighborhood through max_hops. '
                                'Plus one real edge from a distinct reserved distractor component. Both queries for a center '
                                'use identical records. No period interpreted as validity.',
              'negative_selection': 'Target of a real direct edge in a seed-ranked separate component; '
                                    'reserve distractor components too, preventing cross-center component reuse.',
              'limitations': ['Bounded convenience transfer check; not representative or held-out.',
                              'Connectivity in supplied release only; no ownership or external-truth claims.',
                              'Shortfalls are reported without replacing requested depths.'],
              'artifacts_sha256': {p.name: sha256(p) for p in sorted(output_dir.iterdir())}}
    write('manifest.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / '_workspace/hybrid-study/gleif')
    args = parser.parse_args()
    base = ROOT / 'data/gleif/20261012T080000'
    prior = [ROOT / 'experiments/gleif/dataset.json']
    prior += [base / 'comparison-20261013-dev1' / f'{split}-dataset.json'
              for split in ('development', 'reserved')]
    print(json.dumps(prepare(base / 'manifest.json', args.output_dir, prior), indent=2))


if __name__ == '__main__':
    main()
