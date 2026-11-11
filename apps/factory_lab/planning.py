"""Model-declared request interpretation; schema validity is not semantic correctness."""
import json
from .graph import TOOLS, validate_args
from .store import dumps

TOOL_NAMES = {t['function']['name'] for t in TOOLS}
NOTICE = ('Model-declared interpretation, NOT verified intent or source truth. '
          'Quoted user reports are unverified. Plans are advisory, not executed automatically. '
          'The source has machines/orders/capabilities/qualification records only; '
          'no load, schedule, delivery-date or renewal-document service. '
          'Read-only analysis only; never approve or perform a physical allocation.')

PROMPT = '''Interpret the Korean user request using ALL supplied user turns. Return only one JSON object, no Markdown.
Do not answer the business question and do not invent database facts. Separate goals, constraints,
user-reported facts/rumours, and unknowns. Retain prohibitions and changed conditions. Mark superseded
constraints but do not silently discard them. Do not treat a previous assistant answer as evidence.
Each goals/user_reports item has exactly {text, source_turn, quote}.
Each constraints item has exactly {text, source_turn, quote, state}, state=active|superseded|uncertain.
source_turn is a zero-based integer in user_turns; quote must be an exact nonempty substring of that turn.
Quotes establish attribution only, not correct meaning or complete coverage.
Top-level keys exactly: goals, constraints, user_reports, unknowns, steps, clarifications.
unknowns and clarifications are lists of short strings. Ask only decision-relevant clarifications;
when partial answers are possible, plan them and label unsupported parts instead of withholding all.
steps items exactly {id, question, tool, arguments, depends_on, status, reason}.
id must be S1,S2,... in order. depends_on lists earlier step IDs only.
status=ready|needs_prior_result|unsupported. For ready, tool is a listed tool name and arguments
are its valid arguments. For needs_prior_result, tool is a listed tool, arguments=null;
the later tool-using model will choose actual arguments from results. For unsupported,
tool=null, arguments=null. Never emit Cypher or SPARQL. At most 8 items per list.
These steps are advisory retrieval intentions, not an automatic execution plan.
Keep descriptions concise. ''' + NOTICE


def request_messages(turns):
    return [{'role': 'system', 'content': PROMPT}, {'role': 'user', 'content': dumps({
        'user_turns': turns, 'available_tools': TOOLS})}]


def validate_interpretation(text, turns):
    """Only bounded syntax, verbatim attribution, tool arguments and DAG checks."""
    def unique_object(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:raise ValueError('Duplicate JSON field')
            obj[key] = value
        return obj
    obj = json.loads(text, object_pairs_hook=unique_object)
    keys = {'goals', 'constraints', 'user_reports', 'unknowns', 'steps', 'clarifications'}
    if not isinstance(obj, dict) or set(obj) != keys:
        raise ValueError('Interpretation fields')
    for key in keys:
        if not isinstance(obj[key], list) or len(obj[key]) > 8:
            raise ValueError('Interpretation list limit')
    def string(value):
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 500:
            raise ValueError('Interpretation string')
    for key in ('goals', 'constraints', 'user_reports'):
        for item in obj[key]:
            expected = {'text', 'source_turn', 'quote'} | ({'state'} if key == 'constraints' else set())
            if not isinstance(item, dict) or set(item) != expected:
                raise ValueError('Attributed item fields')
            string(item['text']); string(item['quote'])
            n = item['source_turn']
            if type(n) is not int or not 0 <= n < len(turns) or item['quote'] not in turns[n]:
                raise ValueError('Quote is not in cited user turn')
            if key == 'constraints' and item['state'] not in ('active', 'superseded', 'uncertain'):
                raise ValueError('Constraint state')
    for key in ('unknowns', 'clarifications'):
        for value in obj[key]:string(value)
    seen = set()
    for i, step in enumerate(obj['steps'], 1):
        if not isinstance(step, dict) or set(step) != {'id','question','tool','arguments','depends_on','status','reason'}:
            raise ValueError('Step fields')
        if step['id'] != f'S{i}':raise ValueError('Step ID')
        string(step['question']); string(step['reason'])
        deps=step['depends_on']
        if not isinstance(deps,list) or len(deps)>8 or any(not isinstance(d,str) or d not in seen for d in deps):
            raise ValueError('Only prior step dependencies allowed')
        status=step['status']
        if status == 'unsupported':
            if step['tool'] is not None or step['arguments'] is not None:raise ValueError('Unsupported step must not execute')
        elif status in ('ready','needs_prior_result'):
            if not isinstance(step['tool'],str) or step['tool'] not in TOOL_NAMES:raise ValueError('Unknown tool')
            if status == 'ready':validate_args(step['tool'], step['arguments'])
            elif step['arguments'] is not None:raise ValueError('Deferred arguments must be null')
        else:raise ValueError('Step status')
        seen.add(step['id'])
    return obj


def user_turns(store, question, parent_id=None):
    """Bounded original user text only; never silently drop older constraints."""
    turns=[question];seen=set();rid=parent_id
    while rid:
        if rid in seen:raise ValueError('Conversation cycle')
        seen.add(rid);run=store.get(rid)
        if run['status']!='completed':raise ValueError('Only completed parent runs')
        turns.append(run['config']['question']);rid=run['config'].get('parent_id')
        if len(turns)>6:raise ValueError('At most six user turns; start a new explicit request')
    turns.reverse()
    if sum(map(len,turns))>8000:raise ValueError('User context too long; no automatic truncation')
    return turns
