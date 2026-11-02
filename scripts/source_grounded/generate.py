"""Author small structural fixtures; never sample or relabel real transactions."""
import copy
import json
from pathlib import Path

STATES = ('clean', 'semantic_decoy', 'broken_reference', 'source_absence', 'retrieval_omission', 'false_fact')


def base(source, family):
    prefix = f'SYN_{source}_{family:02d}_'
    def ident(s):
        return prefix + s
    if source == 'penelope':
        records = [
            dict(id=ident('book'), type='Code', namespace='worksheet', code='2', meaning='lack_fusion'),
            dict(id=ident('setting'), type='Setting', current=400 + family * 10),
            dict(id=ident('bead'), type='Bead', setting=ident('setting')),
            dict(id=ident('obs'), type='Observation', coupon=ident('coupon'), book=ident('book'), bead=ident('bead'), scope='weld'),
        ]
        q = dict(target=ident('coupon'), meaning='lack_fusion', scope='weld')
        gold = [ident('obs')]
        essential = (ident('bead'), 'setting')
    elif source == 'hinge':
        depth = 1 + family % 4
        records = [dict(id=ident(f'n{i}'), type='Product' if i == depth else 'Material') for i in range(depth + 1)]
        records += [dict(id=ident(f'e{i}'), type='Event', input=ident(f'n{i}'), output=ident(f'n{i+1}')) for i in range(depth)]
        q = dict(target=ident('n0'))
        gold = [ident(f'n{depth}')]
        essential = (ident('e0'), 'input')
    else:
        records = [dict(id=ident('item'), type='Item'),
                   dict(id=ident('gr'), type='Receipt', item=ident('item'), time=10 + family),
                   dict(id=ident('ir'), type='Invoice', item=ident('item'), time=20 + family)]
        q = dict(target=ident('item'))
        gold = [ident('ir')]
        essential = (ident('gr'), 'item')
    return records, q, gold, essential, ident


def cases():
    for source in ('penelope', 'hinge', 'bpi'):
        for family in range(8):
            rows, q, gold, (subject, predicate), ident = base(source, family)
            for state in STATES:
                records = copy.deepcopy(rows)
                complete = True
                contract_gold = gold[:]
                if state == 'semantic_decoy':
                    if source == 'penelope':
                        records += [dict(id=ident('rx'), type='Code', namespace='radiography', code='2', meaning='porosity'),
                                    dict(id=ident('decoy'), type='Observation', coupon=q['target'], book=ident('rx'), bead=ident('bead'), scope='weld'),
                                    dict(id=ident('base'), type='Observation', coupon=q['target'], book=ident('book'), bead=ident('bead'), scope='base_material')]
                    elif source == 'hinge':
                        records += [dict(id=ident('other'), type='Material'), dict(id=ident('decoy'), type='Product'),
                                    dict(id=ident('other_event'), type='Event', input=ident('other'), output=ident('decoy'), with_role=q['target'])]
                    else:
                        records += [dict(id=ident('other_item'), type='Item'),
                                    dict(id=ident('decoy'), type='Invoice', item=ident('other_item'), time=30 + family)]
                if state in ('source_absence', 'retrieval_omission'):
                    # Both expose the same incomplete records. Cause is ONLY in scorer file.
                    for r in records:
                        if r['id'] == subject:
                            del r[predicate]
                    complete = False
                    contract_gold = []
                if state == 'broken_reference':
                    # A typed relation points to a missing node, not a missing real-world fact.
                    target = next(r[predicate] for r in records if r['id'] == subject)
                    records = [r for r in records if r['id'] != target]
                    contract_gold = []
                if state == 'false_fact':
                    # All structural requirements still hold, but the supplied assertion is false.
                    if source == 'penelope':
                        records[0]['meaning'] = 'porosity'
                    elif source == 'hinge':
                        records += [dict(id=ident('other'), type='Material')]
                        next(r for r in records if r['id'] == subject)['input'] = ident('other')
                    else:
                        next(r for r in records if r['type'] == 'Receipt')['time'] = 40 + family
                    contract_gold = []
                payload = dict(source=source, question=q, declared_complete=complete, records=records)
                evaluation = dict(id=f'{source}-{family:02d}-{state}', source=source, family=family, state=state,
                                  contract_candidates=contract_gold, external_candidates=gold,
                                  expected_conforms=state not in ('broken_reference', 'source_absence', 'retrieval_omission'))
                yield payload, evaluation


def write(root):
    root = Path(root)
    for payload, evaluation in cases():
        directory = root / evaluation['source']
        directory.mkdir(parents=True, exist_ok=True)
        (directory / (evaluation['id'] + '.json')).write_text(json.dumps(payload, indent=2) + '\n')
    (root / 'evaluation.json').write_text(json.dumps([e for _, e in cases()], indent=2) + '\n')
