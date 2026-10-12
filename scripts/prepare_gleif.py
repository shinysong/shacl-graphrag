"""Stream a pinned full CSV release into a small, deterministic pilot cohort."""
import argparse
import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REASONS = {'NO_LEI', 'NATURAL_PERSONS', 'NON_CONSOLIDATING', 'NO_KNOWN_PERSON', 'NON_PUBLIC'}


def rows(path):
    with zipfile.ZipFile(path) as archive:
        members = [n for n in archive.namelist() if n.endswith('.csv')]
        if len(members) != 1:
            raise ValueError('Expected one CSV member')
        with archive.open(members[0]) as source:
            yield from csv.DictReader(io.TextIOWrapper(source, encoding='utf-8-sig'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    base = args.manifest.parent
    for kind, info in manifest['files'].items():
        h = hashlib.sha256()
        with (base / f'{kind}.csv.zip').open('rb') as source:
            for block in iter(lambda: source.read(1024 * 1024), b''):
                h.update(block)
        if h.hexdigest() != info['sha256']:
            raise ValueError(f'Input hash mismatch: {kind}')
    relations, exceptions, counts = {}, {}, {}
    # Deterministic discovery-order candidate pool; preserve every matching row,
    # including inactive rows, rather than treating a partial API page as complete.
    for n, row in enumerate(rows(base / 'rr.csv.zip'), 1):
        if row['Relationship.RelationshipType'] != 'IS_DIRECTLY_CONSOLIDATED_BY':
            continue
        lei = row['Relationship.StartNode.NodeID']
        if lei in relations or len(relations) < 30:
            relations.setdefault(lei, []).append(row)
    counts['rr'] = n
    for n, row in enumerate(rows(base / 'repex.csv.zip'), 1):
        if row['Exception.Category'] != 'DIRECT_ACCOUNTING_CONSOLIDATION_PARENT':
            continue
        lei = row['LEI']
        if lei in relations or lei in exceptions or len([k for k in exceptions if k not in relations]) < 30:
            exceptions.setdefault(lei, []).append(row)
    counts['repex'] = n
    targets = set(relations) | set(exceptions)
    targets |= {r['Relationship.EndNode.NodeID'] for rs in relations.values() for r in rs}
    entities = {}
    for n, row in enumerate(rows(base / 'lei2.csv.zip'), 1):
        if row['LEI'] in targets:
            entities[row['LEI']] = row
    counts['lei2'] = n
    for kind, count in counts.items():
        if count != manifest['files'][kind]['record_count']:
            raise ValueError(f'Row count mismatch for {kind}: {count}')
    def eligible(lei):
        return (lei in entities and entities[lei]['Entity.EntityStatus'] == 'ACTIVE'
                and entities[lei]['Registration.RegistrationStatus'] == 'ISSUED')
    cohort = []
    for lei, rs in relations.items():
        active = [r for r in rs if r['Relationship.RelationshipStatus'] == 'ACTIVE'
                  and r['Registration.RegistrationStatus'] == 'PUBLISHED']
        if not eligible(lei) or len(active) != 1 or exceptions.get(lei):
            continue
        parent = active[0]['Relationship.EndNode.NodeID']
        if not eligible(parent) or parent == lei:
            continue
        cohort.append({'lei': lei, 'kind': 'parent', 'parent': parent,
                       'raw_relationships': rs, 'raw_exceptions': []})
        if len(cohort) == 4:
            break
    if len(cohort) != 4:
        raise ValueError('Insufficient parent candidates')
    for lei, es in exceptions.items():
        reasons = [r[f'Exception.Reason.{i}'] for r in es for i in range(1, 6) if r[f'Exception.Reason.{i}']]
        if lei in relations or not eligible(lei) or len(reasons) != 1 or reasons[0] not in REASONS:
            continue
        cohort.append({'lei': lei, 'kind': 'exception', 'reason': reasons[0],
                       'raw_relationships': [], 'raw_exceptions': es})
        if len(cohort) == 8:
            break
    if len(cohort) != 8:
        raise ValueError('Insufficient exception candidates')
    # Final closure scan for exception subjects: discovery pool membership alone
    # cannot establish absence of a relation elsewhere in the full file.
    exception_ids = {c['lei'] for c in cohort if c['kind'] == 'exception'}
    for row in rows(base / 'rr.csv.zip'):
        if (row['Relationship.StartNode.NodeID'] in exception_ids
                and row['Relationship.RelationshipType'] == 'IS_DIRECTLY_CONSOLIDATED_BY'
                and row['Relationship.RelationshipStatus'] == 'ACTIVE'
                and row['Registration.RegistrationStatus'] == 'PUBLISHED'):
            raise ValueError('Exception cohort has an active direct relation')
    used = {c['lei'] for c in cohort} | {c['parent'] for c in cohort if c['kind'] == 'parent'}
    for i, item in enumerate(cohort):
        item['split'] = 'development' if i in (0, 4) else 'pilot'
    result = {'schema_version': 1, 'source_manifest': manifest, 'row_counts': counts,
              'selection': 'First four eligible parent and four exception subjects in CSV discovery order; first of each reserved for development. Not representative.',
              'entities': {lei: {'lei': lei, 'name': entities[lei]['Entity.LegalName'],
                                 'status': entities[lei]['Entity.EntityStatus'],
                                 'registration_status': entities[lei]['Registration.RegistrationStatus']}
                           for lei in sorted(used)},
              'cohort': cohort, 'raw_entities': {lei: entities[lei] for lei in sorted(used)}}
    out = base / 'pilot-dataset.json'
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    fixture = {k: v for k, v in result.items() if k != 'raw_entities'}
    fixture['cohort'] = [{k: v for k, v in c.items() if not k.startswith('raw_')} for c in cohort]
    fixture['raw_subset_sha256'] = hashlib.sha256(out.read_bytes()).hexdigest()
    (base / 'pilot-fixture.json').write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'path': str(out), 'sha256': hashlib.sha256(out.read_bytes()).hexdigest(),
                      'counts': counts, 'cohort': [{k:v for k,v in c.items() if not k.startswith('raw_')} for c in cohort]}, indent=2))


if __name__ == '__main__':
    main()
