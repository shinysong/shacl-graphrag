"""Fixed BM25 top1 versus top3 input/output-type filtering.

Consumes supplied decomposition/bindings, not natural-language parsing. No scorer
or accepted-tool list is imported. Same catalog and rankings for both arms.
"""
from .core import BINDINGS, CatalogIndex, validate_plan, execute


def select(request, catalog, constrained=False):
    index = CatalogIndex(catalog)
    steps = []; decisions = []; selected = {}
    for task in request['tasks']:
        binding = task['binding']
        if 'literal' in binding:
            kind = binding['kind']
        else:
            parent = selected.get(binding['step'])
            kind = BINDINGS[parent][2].get(binding['path']) if parent else None
        ranked = index.search(task['text'], 3)
        eligible = [r for r in ranked if r['score'] > 0 and (not constrained or BINDINGS[r['tool']][1] == kind)]
        pick = eligible[0]['tool'] if eligible else None
        decisions.append({'id':task['id'],'text':task['text'],'binding':binding,'inferred_input_kind':kind,
            'ranked':ranked,'selected_tool':pick,
            'status':'selected_not_semantically_verified' if pick else 'no_candidate_in_shortlist',
            'rejected_by_type':[r['tool'] for r in ranked if constrained and BINDINGS[r['tool']][1] != kind]})
        if pick:
            selected[task['id']] = pick
            steps.append({'id':task['id'],'obligation':task['id'],'tool':pick,'binding':binding})
    plan = {'obligations':{t['id']:t['text'] for t in request['tasks']},'steps':steps}
    try:
        validate_plan(plan); valid = True; error = None
    except ValueError as exc:
        valid = False; error = str(exc)
    return {'decisions':decisions,'plan':plan,'structurally_valid':valid,'plan_error':error,
        'intent_correctness':'unverified','decomposition_origin':'operator_supplied_development'}


def run_request(request, catalog, tools, constrained=False):
    selected = select(request,catalog,constrained)
    if not selected['structurally_valid']:
        return {'selection':selected,'execution':None,'status':'invalid_plan_no_queries'}
    try:
        result = execute(selected['plan'], tools, max_calls=12)
        result['plan_origin'] = 'lexical_selection_on_operator_decomposition'
        return {'selection':selected,'execution':result,'status':'executed_inspect_step_failures'}
    except Exception as exc:
        return {'selection':selected,'execution':None,'status':'execution_failed','error':str(exc)}
