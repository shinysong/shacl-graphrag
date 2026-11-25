"""Pure proposal preparation, with no database/service/model execution or approval.

Import bind(config, runtime_questions, draft, policy_review_operation_id=...).
The returned specs still require the normal reviewed relation/query lifecycle.
This module deliberately has no CLI that can silently approve or execute plans.
"""
from copy import deepcopy
import hashlib


def bind(config, runtime_questions, draft, *, policy_review_operation_id=None):
    questions = {q['id']: q for q in runtime_questions}
    fields = {}
    for entry in draft['entries']:
        source = entry.get('source', {})
        key = (source.get('file'), source.get('column'))
        if key in fields:
            raise ValueError('Ambiguous field mapping')
        fields[key] = entry

    def ref(name):
        table, column = name.split('.')
        entry = fields.get((table, column))
        if entry is None or entry.get('status') != 'approved':
            raise ValueError(f'Required field lacks approval: {name}')
        return {'entry_id': entry['id'], 'alias': table}

    plans = []
    for item in config['questions']:
        question_id = f"{config['pack']}-{item['number']}"
        question = questions[question_id]
        common = {'question_id': question_id, 'question': question['question'],
                  'kind': question['kind'], 'status': item['status']}
        if item['status'] != 'supported':
            plans.append({**common, 'diagnostic': deepcopy(item)})
            continue
        if item.get('policy_required') and not policy_review_operation_id:
            raise ValueError(f'Reviewed source policy paragraph required: {question_id}')
        relations, joins = {}, []
        for child, parent in item.get('joins', []):
            c, p = ref(child), ref(parent)
            rid = 'rel_' + hashlib.sha256(f'{child}>{parent}'.encode()).hexdigest()[:20]
            relations[rid] = {
                'id': rid, 'child_entry_id': c['entry_id'],
                'parent_entry_id': p['entry_id'],
                'interpretation': f'Recorded declared FK {child} references {parent}; retain child row grain.',
                'join_policy': 'left_many_to_one_preserve_root',
            }
            joins.append({'relation_id': rid, 'child_alias': c['alias'], 'parent_alias': p['alias']})
        if item.get('query_kind') == 'directed_reachability':
            r = item['reachability']
            def rid(child):
                parent = r['node']
                return 'rel_' + hashlib.sha256(f'{child}>{parent}'.encode()).hexdigest()[:20]
            spec = {
                'id': question_id.replace('-', '_'), 'title': question['question'],
                'question_scope': question['question'], 'query_kind': 'directed_reachability',
                'edge_id_entry_id': ref(r['edge_id'])['entry_id'],
                'source_entry_id': ref(r['source'])['entry_id'],
                'destination_entry_id': ref(r['destination'])['entry_id'],
                'node_entry_id': ref(r['node'])['entry_id'],
                'source_relation_id': rid(r['source']),
                'destination_relation_id': rid(r['destination']),
                'direction': r['direction'], 'node_key_type': r['node_key_type'],
                'comparison': 'binary_exact',
                'parameters': {k: v[0] for k, v in item['parameters'].items()},
                'seed_parameter': r['seed_parameter'], 'seed_policy': 'require_existing_node',
                'include_seed': False, 'node_semantics': 'distinct_reachable',
                'endpoint_policy': 'require_existing_node',
                'edge_filters': [{'entry_id': ref(f['field'])['entry_id'], 'op': f['op'],
                                  'parameter': f['parameter'], 'value_type': f['value_type']}
                                 for f in r['filters']],
                'projection': [], 'budgets': deepcopy(r['budgets']),
                'output_kind': 'potential_impact_candidates',
                'limitations': ['Authored synthetic source; review candidates, not automatic schedule changes.',
                               'Incomplete traversal is not the full impact set. Display truncation is separate.'],
                'policy_references': [{'review_operation_id': policy_review_operation_id}],
            }
            plans.append({**common, 'spec': spec, 'relation_specs': relations,
                'parameters': {k: v[1] for k, v in item['parameters'].items()},
                'origin': {'kind': 'source_only_authored_config', 'pack': config['pack'],
                           'question_id': question_id, 'policy_document': config['policy_document'],
                           'interpretation_verified': False}})
            continue
        aggregates = []
        for op, name, label in item.get('aggregates', []):
            aggregate = {'op': op, 'name': label}
            if op != 'count_rows':
                aggregate['field'] = ref(name)
            aggregates.append(aggregate)
        for product in item.get('product_aggregates', []):
            aggregates.append({'op': 'sum_product', 'name': product['name'],
                'left': ref(product['left']), 'right': ref(product['right']),
                'numeric_type': 'integer', 'unit': product['unit'],
                'null_policy': 'exclude_if_any_operand_null'})
        parameters = item.get('parameters', {})
        spec = {
            'id': question_id.replace('-', '_'), 'title': question['question'],
            'question_scope': question['question'],
            'root': ref(f"{item['root']}.{item['root_key']}"),
            'joins': joins,
            'parameters': {key: value[0] for key, value in parameters.items()},
            'filters': [{'field': ref(name), 'op': op, 'parameter': parameter}
                        for name, op, parameter in item.get('filters', [])],
            'projection': [{'field': ref(name), 'name': label} for name, label in item['projection']],
            'group_by': [ref(name) for name in item.get('group_by', [])],
            'aggregates': aggregates, 'distinct': item.get('distinct', False),
            'output_kind': item.get('output_kind', 'recorded_facts'),
            'limitations': ['Authored synthetic snapshot only; supplied policy interpretation requires review. '
                            'Result truncation must be reported; no full-set claim for truncated output.',
                            *item.get('limitations', [])],
            'policy_references': ([{'review_operation_id': policy_review_operation_id}]
                                  if item.get('policy_required') else []),
            'null_policy': 'exclude_from_aggregates_preserve_projection',
            'empty_groups': 'absent', 'measure_grain': item['root'],
        }
        if item.get('scalar_bindings') or item.get('comparisons'):
            spec['scalar_bindings'] = [{
                'name': b['name'], 'table_entry_id': ref(b['table'])['entry_id'],
                'selector_entry_id': ref(b['selector'])['entry_id'],
                'selector_type': b['selector_type'], 'parameter': b['parameter'],
                'value_entry_id': ref(b['value'])['entry_id'], 'value_type': b['value_type'],
                'cardinality': 'exactly_one', 'null_policy': 'require_nonnull',
                'comparison': 'binary_exact',
            } for b in item.get('scalar_bindings', [])]
            for c in item.get('comparisons', []):
                right = ({'kind': 'scalar', 'binding': c['right_scalar']}
                         if 'right_scalar' in c else {'kind': 'field', **ref(c['right_field'])})
                spec['filters'].append({'op': c['op'], 'left': {'kind': 'field', **ref(c['left'])},
                    'right': right, 'value_type': c['value_type'],
                    'null_policy': 'unknown_excluded', 'comparison': 'binary_exact'})
        plans.append({**common, 'spec': spec, 'relation_specs': relations,
                      'parameters': {key: value[1] for key, value in parameters.items()},
                      'origin': {'kind': 'source_only_authored_config', 'pack': config['pack'],
                                 'question_id': question_id, 'policy_document': config['policy_document'],
                                 'interpretation_verified': False}})
    if set(questions) != {p['question_id'] for p in plans}:
        raise ValueError('Configuration must retain every original representative question')
    return plans
