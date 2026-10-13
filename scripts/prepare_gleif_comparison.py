"""Prepare a new, component-disjoint GLEIF convenience cohort (offline only).

The CLI fixes the release, seed, pool bound and split sizes. Reserved identities,
answers and raw rows stay in reserved-dataset.json; stdout contains aggregates
and hashes only. This prepares data, not a GraphRAG benchmark.
"""
import argparse
import hashlib
import json
from pathlib import Path

from prepare_gleif import REASONS, rows

ROOT = Path(__file__).resolve().parents[1]
DIRECT = 'IS_DIRECTLY_CONSOLIDATED_BY'
ACCOUNTING = {DIRECT, 'IS_ULTIMATELY_CONSOLIDATED_BY'}
CATEGORY = 'DIRECT_ACCOUNTING_CONSOLIDATION_PARENT'
SEED = 20261013
POOL_SIZE = 10000


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


class Components:
    """Union-find over all active, published accounting relationships."""
    def __init__(self):
        self.parents = {}
        self.sizes = {}

    def find(self, node):
        if node not in self.parents:
            self.parents[node] = node
            self.sizes[node] = 1
        root = node
        while root != self.parents[root]:
            root = self.parents[root]
        while node != root:
            node, self.parents[node] = self.parents[node], root
        return root

    def union(self, left, right):
        left, right = self.find(left), self.find(right)
        if left == right:
            return
        if self.sizes[left] < self.sizes[right]:
            left, right = right, left
        self.parents[right] = left
        self.sizes[left] += self.sizes.pop(right)


def active(row):
    return (row['Relationship.RelationshipStatus'] == 'ACTIVE'
            and row['Registration.RegistrationStatus'] == 'PUBLISHED')


def rank(lei, purpose):
    return hashlib.sha256(f'{SEED}:{purpose}:{lei}'.encode()).hexdigest(), lei


def prepare(manifest_path, output_dir, prior, *, pool_size=POOL_SIZE,
            development_each=6, reserved_each=15):
    """Small parameter overrides support synthetic software tests only.

    `prior` supplies both all prior pilot entities and the pinned release hashes.
    CLI always reads the tracked original pilot and uses the fixed defaults.
    """
    manifest_path, output_dir = Path(manifest_path), Path(output_dir)
    if output_dir.exists():
        raise FileExistsError('Output directory already exists; refusing overwrite')
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    pinned = prior['source_manifest']
    if manifest['publish_date'] != pinned['publish_date']:
        raise ValueError('Release differs from the pinned pilot release')
    base = manifest_path.parent
    for kind in ('lei2', 'rr', 'repex'):
        info = manifest['files'][kind]
        if (info['sha256'] != pinned['files'][kind]['sha256']
                or info['record_count'] != pinned['files'][kind]['record_count']):
            raise ValueError(f'Pinned manifest mismatch: {kind}')
        if sha256(base / f'{kind}.csv.zip') != info['sha256']:
            raise ValueError(f'Input hash mismatch: {kind}')
    if pool_size < development_each + reserved_each or development_each < 1 or reserved_each < 1:
        raise ValueError('Invalid cohort or pool sizes')

    counts = {}

    def scan(kind):
        count = 0
        for row in rows(base / f'{kind}.csv.zip'):
            count += 1
            yield row
        if count != manifest['files'][kind]['record_count']:
            raise ValueError(f'Row count mismatch: {kind}')
        counts[kind] = count

    prior_ids = set(prior['entities'])
    for item in prior['cohort']:
        prior_ids.add(item['lei'])
        if item.get('parent'):
            prior_ids.add(item['parent'])
    groups = Components()
    parent_pool = set()
    for row in scan('rr'):
        subject = row['Relationship.StartNode.NodeID']
        if active(row) and row['Relationship.RelationshipType'] in ACCOUNTING:
            groups.union(subject, row['Relationship.EndNode.NodeID'])
        if row['Relationship.RelationshipType'] == DIRECT and len(parent_pool) < pool_size:
            parent_pool.add(subject)
    forbidden = {groups.find(lei) for lei in prior_ids}

    exception_pool, exceptions = set(), {}
    for row in scan('repex'):
        subject = row['LEI']
        if row['Exception.Category'] == CATEGORY:
            if len(exception_pool) < pool_size:
                exception_pool.add(subject)
            if subject in parent_pool or subject in exception_pool:
                exceptions.setdefault(subject, []).append(row)
    if min(len(parent_pool), len(exception_pool)) < pool_size:
        raise ValueError('Insufficient discovery pool; do not silently change selection')
    candidates = parent_pool | exception_pool
    # Preserve other reporting categories too, including rows preceding discovery.
    raw_exceptions = {}
    for row in scan('repex'):
        if row['LEI'] in candidates:
            raw_exceptions.setdefault(row['LEI'], []).append(row)
    relationships = {lei: [] for lei in candidates}
    targets = set(candidates)
    # Full closure scan: retain ALL outgoing RR, not only discovery rows.
    # This checks exception absence even when its direct edge lies past the pool.
    for row in scan('rr'):
        subject = row['Relationship.StartNode.NodeID']
        if subject in candidates:
            relationships[subject].append(row)
            if active(row) and row['Relationship.RelationshipType'] == DIRECT:
                targets.add(row['Relationship.EndNode.NodeID'])
    entities = {}
    for row in scan('lei2'):
        if row['LEI'] in targets:
            if row['LEI'] in entities:
                raise ValueError('Duplicate LEI in source')
            entities[row['LEI']] = row

    def eligible(lei):
        row = entities.get(lei, {})
        return (row.get('Entity.EntityStatus') == 'ACTIVE'
                and row.get('Registration.RegistrationStatus') == 'ISSUED')

    eligible_items = {'parent': [], 'exception': []}
    for lei in sorted(candidates):
        if not eligible(lei) or groups.find(lei) in forbidden:
            continue
        direct = [r for r in relationships[lei]
                  if active(r) and r['Relationship.RelationshipType'] == DIRECT]
        es = exceptions.get(lei, [])
        if lei in parent_pool and len(direct) == 1 and not es:
            parent = direct[0]['Relationship.EndNode.NodeID']
            if parent != lei and eligible(parent):
                eligible_items['parent'].append({'lei': lei, 'kind': 'parent', 'parent': parent})
        reasons = [r.get(f'Exception.Reason.{i}', '') for r in es for i in range(1, 6)
                   if r.get(f'Exception.Reason.{i}', '')]
        if lei in exception_pool and not direct and len(es) == 1 and len(reasons) == 1 and reasons[0] in REASONS:
            eligible_items['exception'].append({'lei': lei, 'kind': 'exception', 'reason': reasons[0]})
    selected, used_groups = [], set()
    for kind in ('parent', 'exception'):
        chosen = []
        for item in sorted(eligible_items[kind], key=lambda c: rank(c['lei'], 'selection')):
            component = groups.find(item['lei'])
            if component in used_groups:
                continue
            chosen.append(item)
            used_groups.add(component)
            if len(chosen) == development_each + reserved_each:
                break
        if len(chosen) != development_each + reserved_each:
            raise ValueError(f'Insufficient component-independent {kind} candidates')
        for index, item in enumerate(sorted(chosen, key=lambda c: rank(c['lei'], 'split'))):
            item['split'] = 'development' if index < development_each else 'reserved'
            selected.append(item)

    selection = {
        'description': 'CSV discovery-order bounded convenience pools; SHA-256 ranking; not representative.',
        'seed': SEED, 'discovery_pool_bound_per_kind': pool_size,
        'discovery_pool_counts': {'parent': len(parent_pool), 'exception': len(exception_pool)},
        'eligible_counts_before_component_deduplication': {k: len(v) for k, v in eligible_items.items()},
        'component_rule': 'At most one center per undirected component of all ACTIVE/PUBLISHED direct and ultimate accounting RR; exclude every component touching any prior pilot entity.',
        'selection_order': ['parent', 'exception'],
        'ranking': 'ascending SHA256(20261013:selection:LEI); then independent SHA256(20261013:split:LEI)',
        'prior_entity_count': len(prior_ids),
        'prior_fixture_sha256': hashlib.sha256(json.dumps(prior, sort_keys=True).encode()).hexdigest(),
    }

    def dataset(split):
        cohort = [dict(c) for c in selected if c['split'] == split]
        used = {c['lei'] for c in cohort} | {c['parent'] for c in cohort if c['kind'] == 'parent'}
        return {'schema_version': 1, 'source_manifest': manifest, 'row_counts': counts,
                'selection': selection,
                'entities': {lei: {'lei': lei, 'name': entities[lei]['Entity.LegalName'],
                                  'status': entities[lei]['Entity.EntityStatus'],
                                  'registration_status': entities[lei]['Registration.RegistrationStatus']}
                             for lei in sorted(used)},
                'cohort': [dict(c, raw_relationships=relationships[c['lei']],
                                raw_exceptions=raw_exceptions.get(c['lei'], [])) for c in cohort],
                'raw_entities': {lei: entities[lei] for lei in sorted(used)}}

    # A new directory is an exclusive reservation. Failures remain for inspection.
    output_dir.mkdir(parents=True, exist_ok=False, mode=0o700)

    def write(name, obj):
        with (output_dir / name).open('x', encoding='utf-8') as output:
            output.write(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

    with (output_dir / 'source-manifest.json').open('xb') as output:
        output.write(manifest_bytes)
    development = dataset('development')
    write('development-raw.json', development)
    fixture = {k: v for k, v in development.items() if k != 'raw_entities'}
    fixture['cohort'] = [{k: v for k, v in c.items() if not k.startswith('raw_')}
                         for c in development['cohort']]
    fixture['raw_subset_sha256'] = sha256(output_dir / 'development-raw.json')
    write('development-dataset.json', fixture)
    write('reserved-dataset.json', dataset('reserved'))
    summary = {'row_counts': counts, 'selection': selection,
               'cohort_counts': {'development': development_each * 2, 'reserved': reserved_each * 2},
               'kind_counts_per_split': {'development': development_each, 'reserved': reserved_each},
               'artifacts_sha256': {p.name: sha256(p) for p in sorted(output_dir.iterdir())}}
    write('preparation-summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    prior = json.loads((ROOT / 'experiments/gleif/dataset.json').read_text())
    summary = prepare(args.manifest, args.output_dir, prior)
    print(json.dumps({key: summary[key] for key in (
        'row_counts', 'cohort_counts', 'kind_counts_per_split', 'artifacts_sha256'
    )}, indent=2))


if __name__ == '__main__':
    main()
