"""No LLM, gold, arbitrary query text, or automatic plan repair.

Plans are explicit interpretations supplied by a caller, not verified user intent.
Retrieval ranks metadata; the executor does NOT treat retrieval scores as approval.
"""
import copy
import json
import math
import re
from collections import Counter
from pathlib import Path

CATALOG = Path('research/query-contracts-1/catalog-proposal.json')
# Closed executable bindings. Proposal metadata alone never enables execution.
BINDINGS = {
    'impacted_orders': ('machine_id', 'Machine', {'order.id': 'Order', 'machine.id': 'Machine'}),
    'replacement_candidates': ('order_id', 'Order', {'order.id': 'Order', 'machine.id': 'Machine'}),
    'qualification_records': ('machine_id', 'Machine', {'machine.id': 'Machine'}),
    'assigned_machines': ('order_id', 'Order', {'order.id': 'Order', 'machine.id': 'Machine'}),
    'current_qualification_records': ('machine_id', 'Machine', {'machine.id': 'Machine'}),
    'expired_qualification_records': ('machine_id', 'Machine', {'machine.id': 'Machine'}),
}


def tokens(text):
    words = re.findall(r'[a-z0-9]+|[가-힣]+', text.lower())
    return [t for w in words for t in ([w] + [w[i:i+2] for i in range(len(w)-1)] if re.fullmatch('[가-힣]+', w) else [w])]


class CatalogIndex:
    """BM25 over identical full contract metadata; Korean word+bigrams, no embeddings."""
    def __init__(self, catalog=None):
        self.catalog = copy.deepcopy(catalog if catalog is not None else json.loads(CATALOG.read_text())['catalog'])
        self.docs = [Counter(tokens(json.dumps(c, ensure_ascii=False))) for c in self.catalog]
        self.avg = sum(map(lambda d: sum(d.values()), self.docs))/max(len(self.docs), 1)

    def search(self, text, k=3):
        if type(k) is not int or not 1 <= k <= len(self.catalog):
            raise ValueError('Invalid shortlist size')
        query = set(tokens(text)); n = len(self.docs); scores = []
        for c, d in zip(self.catalog, self.docs):
            score = 0.0
            for term in query:
                df = sum(term in other for other in self.docs)
                idf = math.log(1+(n-df+0.5)/(df+0.5))
                tf = d[term]
                score += idf * tf * 2.2/(tf+1.2*(0.25+0.75*sum(d.values())/(self.avg or 1)))
            scores.append({'tool': c['tool'], 'score': score, 'contract': copy.deepcopy(c)})
        return sorted(scores, key=lambda x: (-x['score'], x['tool']))[:k]


def _value(row, path):
    value = row
    for part in path.split('.'):
        if not isinstance(value, dict) or part not in value:
            raise ValueError('missing_output_binding')
        value = value[part]
    return value


def validate_plan(plan):
    """Ordered DAG; one bound argument per existing template; no implicit cross joins."""
    if set(plan) != {'obligations', 'steps'} or not isinstance(plan['obligations'], dict):
        raise ValueError('invalid_plan')
    if not plan['obligations'] or len(plan['obligations']) > 24 or len(plan['steps']) > 24:
        raise ValueError('plan_size')
    seen = {}
    for step in plan['steps']:
        if set(step) != {'id', 'obligation', 'tool', 'binding'} or step['id'] in seen:
            raise ValueError('invalid_step')
        if step['obligation'] not in plan['obligations'] or step['tool'] not in BINDINGS:
            raise ValueError('unsupported_obligation_or_tool')
        binding = step['binding']; expected = BINDINGS[step['tool']][1]
        if set(binding) == {'literal', 'kind'}:
            if binding['kind'] != expected or not isinstance(binding['literal'], str) or not binding['literal']:
                raise ValueError('incompatible_literal')
        elif set(binding) == {'step', 'path'}:
            if binding['step'] not in seen:
                raise ValueError('forward_or_missing_dependency')
            outputs = BINDINGS[seen[binding['step']]['tool']][2]
            if outputs.get(binding['path']) != expected:
                raise ValueError('incompatible_binding')
        else:
            raise ValueError('invalid_binding')
        seen[step['id']] = step


def execute(plan, tools, version='factory-v3', max_calls=12):
    """Execute supplied plan on one frozen selected view, preserving per-row lineage.

No final answer or qualification verdict is generated. 'rows_returned' is ONLY
retrieval status, never obligation satisfaction, answer coverage, or completeness.
"""
    validate_plan(plan)
    if type(max_calls) is not int or not 0 <= max_calls <= 100:
        raise ValueError('invalid_budget')
    snapshot, digest = tools.views.snapshot(version)
    anchor = (version, digest, snapshot['as_of'])
    entities = {n['id']: n['kind'] for n in snapshot['nodes']}
    calls = []; outputs = {}; states = {}
    for step in plan['steps']:
        binding = step['binding']; requests = []; problems = []; rows_out = []
        inherited_limit = False
        if 'literal' in binding:
            requests = [(binding['literal'], {}, [], False)]
        else:
            parent = states[binding['step']]
            inherited_limit = parent['limited']
            if parent['issues']:
                problems.append('upstream_unresolved')
            for item in outputs[binding['step']]:
                try:
                    requests.append((_value(item['row'], binding['path']), item['context'], item['lineage'], item['limited']))
                except ValueError as exc:
                    problems.append(str(exc))
            if not requests:
                problems.append('no_upstream_rows')
        for value, context, lineage, limited in requests:
            arg, kind, _ = BINDINGS[step['tool']]
            if entities.get(value) != kind:
                problems.append('entity_type_not_verified'); continue
            if len(calls) >= max_calls:
                problems.append('call_budget_exhausted'); continue
            args = {arg: value}; eid = f'Q{len(calls)+1}'
            record = {'id': eid, 'step': step['id'], 'arguments': args, 'tool': step['tool']}
            calls.append(record)  # failed attempts count too
            try:
                result = tools.run(version, step['tool'], args)
                record['result'] = result
                if (result.get('snapshot'), result.get('source_sha256'), result.get('as_of')) != anchor:
                    raise ValueError('version_mismatch')
                if result.get('arguments') != args or result.get('tool') != step['tool']:
                    raise ValueError('response_binding_mismatch')
                if not isinstance(result.get('rows'), list) or type(result.get('limit_reached')) is not bool:
                    raise ValueError('invalid_response')
                batch = []
                for row in result['rows']:
                    # Bind returned entity IDs back to THIS request, not merely its type.
                    if _value(row, 'order.id' if arg == 'order_id' else 'machine.id') != value:
                        raise ValueError('response_entity_mismatch')
                    ctx = copy.deepcopy(context)
                    if 'order' in row:
                        order = row['order']
                        current = {'id': order['id'], 'product': order.get('product'),
                                   'required_capability': row.get('required_capability')}
                        if 'order' in ctx and ctx['order'] != current:
                            raise ValueError('order_context_mismatch')
                        ctx['order'] = current
                    batch.append({'row': row, 'context': ctx, 'lineage': lineage+[eid],
                                  'limited': limited or result['limit_reached']})
                rows_out.extend(batch)
                inherited_limit |= result['limit_reached']
                record['status'] = 'completed'
            except Exception as exc:
                record['status'] = 'failed'; record['error'] = str(exc)
                problems.append(str(exc))
        outputs[step['id']] = rows_out
        states[step['id']] = {'obligation': step['obligation'], 'issues': sorted(set(problems)),
            'limited': inherited_limit, 'row_count': len(rows_out),
            'status': 'partial_or_unresolved' if problems or inherited_limit else ('rows_returned' if rows_out else 'empty_selected_view')}
    obligations = {}
    for key, text in plan['obligations'].items():
        linked = [s['id'] for s in plan['steps'] if s['obligation'] == key]
        obligations[key] = {'text': text, 'steps': linked,
            'status': 'not_planned' if not linked else 'retrieval_tracked_semantic_satisfaction_unverified',
            'answer_coverage': 'not_evaluated', 'review_coverage': 'not_evaluated'}
    return {'schema_version': 1, 'plan_origin': 'caller_supplied_not_verified_intent',
            'snapshot': list(anchor), 'calls': calls, 'steps': states, 'outputs': outputs,
            'obligations': obligations, 'source_completeness': 'unknown',
            'qualification_policy': 'not_evaluated_single_record_matching_required_downstream'}
