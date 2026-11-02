"""Author development fixtures and separate scorer labels; never imported by runtime."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / 'research/actionable-evidence-1'
STATES = ('supported_unique_current_reference', 'reference_missing_in_source',
          'reference_present_but_omitted_from_projection', 'stale_reference',
          'wrong_entity_or_field_role', 'conflicting_references',
          'shape_conforming_false_reference', 'patch_creates_dependency_violation')


def authored_cases():
    for role_i, (field, unit, truth, false, lower, upper) in enumerate([
            ('setting', 'code', 2, 3, 1, 11), ('end_mm', 'mm', 200, 210, 0, 1000)]):
        for depth in (1, 2):
            family = role_i * 2 + depth - 1
            target, bridge, ref = (f's{family}_{suffix}' for suffix in ('target', 'bridge', 'ref'))
            for state_i, state in enumerate(STATES):
                case_id = f'c{family * 8 + state_i:03d}'
                reference = dict(id=ref, type='Reference', entity=target, field=field,
                                 unit=unit, version='v1', value=truth,
                                 citation=f'synthetic://source/{family}/record/1')
                nodes = [reference]
                edges = [dict(**{'from': target, 'to': ref})]
                if depth == 2:
                    nodes.append(dict(id=bridge, type='Bridge'))
                    edges = [{'from': target, 'to': bridge}, {'from': bridge, 'to': ref}]
                data = dict(target=dict(id=target, field=field, unit=unit, version='v1',
                                        value=None, minimum=lower, maximum=upper),
                            nodes=nodes, edges=edges,
                            dependencies=[dict(id=f's{family}_dep', target=target,
                                               minimum=lower, maximum=upper)])
                if state_i in (1, 2):
                    data['nodes'] = [n for n in nodes if n['id'] != ref]
                    data['edges'] = [e for e in edges if e['to'] != ref]
                elif state_i == 3:
                    reference['version'] = 'v0'
                elif state_i == 4:
                    reference['entity'] = f's{family}_other'
                    reference['field'] = 'end_mm' if field == 'setting' else 'setting'
                elif state_i == 5:
                    rival = copy.deepcopy(reference)
                    rival.update(id=ref + 'b', value=false,
                                 citation=f'synthetic://source/{family}/record/2')
                    data['nodes'].append(rival)
                    data['edges'].append({'from': bridge if depth == 2 else target, 'to': rival['id']})
                elif state_i == 6:
                    reference['value'] = false
                elif state_i == 7:
                    data['dependencies'][0]['maximum'] = truth - 1
                applicable = state_i in (0, 6, 7)
                gold = dict(case_id=case_id, family=family, field=field, depth=depth, state=state,
                            reference_applicable=applicable, contract_eligible=state_i in (0, 6),
                            correct_known_eligible=state_i == 0,
                            expected_candidate_value=(false if state_i == 6 else truth) if applicable else None,
                            external_truth=truth,
                            expected_refs=[ref] if applicable else [],
                            provenance='Authored synthetic development expectation, not observed factory truth')
                yield case_id, data, gold


def main():
    dest = ROOT / 'fixtures'
    if dest.exists():
        raise SystemExit('Refusing to overwrite frozen fixtures')
    (dest / 'runtime').mkdir(parents=True)
    scorer, manifest = [], {}
    for case_id, data, gold in authored_cases():
        raw = (json.dumps(data, sort_keys=True, indent=2) + '\n').encode()
        (dest / 'runtime' / f'{case_id}.json').write_bytes(raw)
        manifest[case_id] = hashlib.sha256(raw).hexdigest()
        scorer.append(gold)
    assert len(scorer) == 32
    for family in range(4):
        assert manifest[f'c{family * 8 + 1:03d}'] == manifest[f'c{family * 8 + 2:03d}']
    (dest / 'scorer.json').write_text(json.dumps(scorer, indent=2) + '\n')
    (dest / 'manifest.json').write_text(json.dumps(dict(kind='authored_consumed_development',
         cases=32, planned_rows=192, runtime_sha256=manifest,
         scorer_sha256=hashlib.sha256((dest / 'scorer.json').read_bytes()).hexdigest()), indent=2) + '\n')
    print(json.dumps({'cases': 32, 'planned_rows': 192, 'missing_cause_identical_pairs': 4}))


if __name__ == '__main__':
    main()
