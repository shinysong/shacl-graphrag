"""Exploratory synthetic semantic evidence experiment; never a GLEIF benchmark.

The contract is supplied to every engine. No learned policy or open-world reasoning
is measured. Gold is separate from runtime; one false but consistent record is
intentionally undetectable without external evidence.
"""
import argparse
import copy
import hashlib
import json
import math
import random
import shutil
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import dotenv_values
from pyshacl import validate
from rdflib import XSD, Graph, Literal, Namespace

try:
    from scripts import run_comparison_study as transport
except ModuleNotFoundError:
    import run_comparison_study as transport

ROOT = transport.ROOT
EX = Namespace('urn:semantic:')
CONTRACT = """Use only the supplied records. Answer the requested subject's requested
relation as of the stated date. A record qualifies only if subject and relation
match, status is current, start <= as_of and end is absent or end > as_of.
All records have equal authority. Exactly one distinct qualifying candidate is
answerable; cite all qualifying record IDs. Multiple qualifying candidates require
abstention. With no qualifying candidate, retrieve if retrieval_available is true;
otherwise abstain. Do not retrieve to resolve a contradiction. There is at most one
source-only retrieval. Never infer direct from ultimate or ultimate from direct.
For abstain/retrieve use candidate null and citations []."""
PROMPT = CONTRACT + """
Return one JSON object with exactly three keys:
{"decision":"answer|abstain|retrieve", "candidate":"ID or null", "citations":["record ID"]}.
Use a JSON null candidate for abstain/retrieve. No envelope or other prose.
"""
# This qualification expression is used only by the SHACL engine, never by code.
MATCH = '''$this <urn:semantic:subject> ?s; <urn:semantic:relation> ?rel; <urn:semantic:as_of> ?date .
?r <urn:semantic:subject> ?s; <urn:semantic:relation> ?rel;
   <urn:semantic:status> "current"; <urn:semantic:start> ?start;
   <urn:semantic:candidate> ?candidate .
OPTIONAL { ?r <urn:semantic:end> ?end }
FILTER (?start <= ?date && (!BOUND(?end) || ?end > ?date))'''
SHAPES = f'''@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <urn:semantic:> .
ex:Answerable a sh:NodeShape; sh:targetNode ex:request;
 sh:sparql [ sh:message "No qualifying record"; sh:select """SELECT $this WHERE {{
 FILTER NOT EXISTS {{ {MATCH} }} }}""" ];
 sh:sparql [ sh:message "Conflicting candidates"; sh:select """SELECT $this WHERE {{
 {{ SELECT $this (COUNT(DISTINCT ?candidate) AS ?n) WHERE {{ {MATCH} }} GROUP BY $this }}
 FILTER (?n > 1) }}""" ] .'''


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def fixtures(seed=20261013):
    """Synthetic controlled tasks; opaque IDs do not encode variant/gold labels."""
    rng = random.Random(seed)
    def opaque():
        return 'n' + f'{rng.getrandbits(64):016x}'
    runtime, gold = [], {}
    for variant in ('direct', 'ultimate', 'temporal', 'ended', 'future', 'conflict',
                    'duplicate', 'source_absence', 'retrieval_omission', 'false_fact'):
        case_id, subject, a, b = [opaque() for _ in range(4)]
        query = {'subject': subject, 'relation': 'ultimate' if variant == 'ultimate' else 'direct',
                 'as_of': '2026-01-01'}
        def record(candidate=a, subject=subject, **updates):
            row = {'id': opaque(), 'subject': subject, 'candidate': candidate, 'relation': 'direct',
                       'status': 'current', 'start': '2020-01-01', 'end': None}
            row.update(updates)
            return row
        source = [record()]
        expected, target = 'answer', a
        if variant in ('direct', 'ultimate'):
            source += [record(b, relation='ultimate')]
            target = b if variant == 'ultimate' else a
        elif variant == 'temporal':
            source += [record(b, status='ended', end='2025-01-01')]
        elif variant == 'ended':
            source = [record(status='ended', end='2025-01-01')]
            expected, target = 'abstain', None
        elif variant == 'future':
            source = [record(start='2027-01-01')]
            expected, target = 'abstain', None
        elif variant == 'conflict':
            source += [record(b)]
            expected, target = 'abstain', None
        elif variant == 'duplicate':
            source += [record()]
        elif variant == 'source_absence':
            source = []
            expected, target = 'abstain', None
        elif variant == 'false_fact':
            source = [record(b)]  # Evaluator truth a never enters runtime payload.
            target = a
        first = [] if variant == 'retrieval_omission' else copy.deepcopy(source)
        relation = query['relation']
        questions = [f'What is the {relation} parent of {subject} on 2026-01-01?',
                     f'Identify {subject}’s {relation} parent as of 2026-01-01.',
                     f'On 2026-01-01, which entity is the {relation} parent for {subject}?']
        runtime.append({'id': case_id, 'query': query, 'questions': questions, 'first': first, 'source': source})
        gold[case_id] = {'variant': variant, 'decision': expected, 'candidate': target,
                            'first_decision': 'retrieve' if variant in ('ended', 'future', 'source_absence', 'retrieval_omission') else expected,
                            'policy_candidate': b if variant == 'false_fact' else target,
                            'policy_citations': sorted(r['id'] for r in source if r['candidate'] == (b if variant == 'false_fact' else target) and r['relation'] == query['relation']),
                            'answerable': expected == 'answer' and variant != 'false_fact'}
    return runtime, gold


def targeted_fixtures(seed=20261013):
    """Posthoc paired stale-evidence follow-up, not an independent cohort.

    Preserve each original first payload byte-for-byte under JSON serialization;
    only the source snapshot gains a current record with a different candidate.
    """
    baseline, baseline_gold = fixtures(seed)
    runtime, gold = [], {}
    for original in baseline:
        variant = baseline_gold[original['id']]['variant']
        if variant not in {'ended', 'future'}:
            continue
        case = copy.deepcopy(original)
        def new_id(role, case_id=case['id']):
            return 'n' + hashlib.sha256(
                f'semantic-stale-followup-1:{seed}:{case_id}:{role}'.encode()).hexdigest()[:16]
        record = {'id': new_id('record'), 'subject': case['query']['subject'],
                  'candidate': new_id('candidate'), 'relation': case['query']['relation'],
                  'status': 'current', 'start': '2025-06-01', 'end': None}
        case['source'].append(record)
        runtime.append(case)
        gold[case['id']] = {'variant': variant + '_retrieval_omission',
                           'decision': 'answer', 'candidate': record['candidate'],
                           'first_decision': 'retrieve', 'policy_candidate': record['candidate'],
                           'policy_citations': [record['id']], 'answerable': True}
    return runtime, gold


def decision(candidates, citations, available):
    if len(candidates) == 1:
        return {'decision': 'answer', 'candidate': next(iter(candidates)), 'citations': sorted(citations)}
    return {'decision': 'retrieve' if not candidates and available else 'abstain',
                'candidate': None, 'citations': []}


def code_judge(payload):
    q = payload['query']
    rows = [r for r in payload['records'] if r['subject'] == q['subject']
            and r['relation'] == q['relation'] and r['status'] == 'current'
            and r['start'] <= q['as_of'] and (r['end'] is None or r['end'] > q['as_of'])]
    return decision({r['candidate'] for r in rows}, [r['id'] for r in rows],
                    payload['retrieval_available'])


def shacl_judge(payload, report_path=None):
    graph = Graph()
    for key, value in payload['query'].items():
        graph.add((EX.request, EX[key], Literal(value, datatype=XSD.date if key == 'as_of' else None)))
    for r in payload['records']:
        for key, value in r.items():
            if value is not None:
                graph.add((EX[r['id']], EX[key], Literal(value, datatype=XSD.date if key in ('start', 'end') else None)))
    conforms, report, _ = validate(graph, shacl_graph=Graph().parse(data=SHAPES, format='turtle'))
    if report_path:
        report.serialize(report_path, format='turtle')
    # Extraction is independent RDF/SPARQL, with SHACL conformity gating the answer.
    matches = list(graph.query('SELECT ?r ?candidate WHERE { ' + MATCH.replace('$this', '<urn:semantic:request>') + ' }'))
    if conforms:
        candidates = {str(row.candidate) for row in matches}
        if len(candidates) != 1:
            raise RuntimeError('SHACLExtractionMismatch')
        return {'decision': 'answer', 'candidate': candidates.pop(),
                    'citations': sorted(str(row.r).removeprefix(str(EX)) for row in matches)}
    return {'decision': 'retrieve' if not matches and payload['retrieval_available'] else 'abstain',
                'candidate': None, 'citations': []}


def check_response(result, records, query=None):
    if (not isinstance(result, dict) or set(result) != {'decision', 'candidate', 'citations'}
            or result['decision'] not in {'answer', 'abstain', 'retrieve'}
            or not isinstance(result['citations'], list)
            or any(not isinstance(x, str) for x in result['citations'])
            or len(set(result['citations'])) != len(result['citations'])):
        raise ValueError('InvalidDecisionSchema')
    if result['decision'] == 'answer':
        if not isinstance(result['candidate'], str):
            raise ValueError('InvalidCandidateType')
    elif result['candidate'] is not None:
        raise ValueError('NonAnswerPayload')
    return result


def run_case(case, paraphrase, judge, trace=None):
    trace = [] if trace is None else trace
    for step in range(2):
        payload = {'contract': CONTRACT, 'query': case['query'], 'question': case['questions'][paraphrase],
                       'records': copy.deepcopy(case['first'] if step == 0 else case['source']),
                       'retrieval_available': step == 0}
        result = judge(payload, step)
        trace.append(result)
        check_response(result, payload['records'], payload['query'])
        if result['decision'] != 'retrieve':
            return {'answer': result, 'trace': trace, 'retrieval_calls': step, 'final_records': payload['records'], 'query': payload['query']}
    raise ValueError('RetrievalLimitExceeded')


def config():
    return {'model': 'openai/gpt-4o-mini', 'max_llm_calls': 120, 'max_cost_usd': 0.8,
                'max_prompt_chars': 18000, 'max_completion_tokens': 300, 'temperature': 0,
                'provider_max_price_per_million': {'prompt': 0.15, 'completion': 0.6},
                'campaign_ledger_path': str(ROOT / '_workspace/expanded-study/campaign-budget.json')}


class UnknownCost(transport.CriticalAbort):
    """An attempted request has no trustworthy accounted usage envelope."""


class SemanticGateway:
    """Flat semantic output; durable shared accounting before every single POST."""
    def __init__(self, cfg, output, prompt_path, coordinator=None):
        if (cfg['model'] != 'openai/gpt-4o-mini' or cfg['max_completion_tokens'] != 300
                or not 0 < cfg['max_llm_calls'] <= 120 or not 0 < cfg['max_cost_usd'] <= 0.8):
            raise transport.CriticalAbort('InvalidSemanticBudgetOrModel')
        env = dotenv_values(ROOT / '.env')
        key = env.get('OPENROUTER_API_KEY')
        if not key or key.startswith('your_'):
            raise transport.CriticalAbort('MissingCredential')
        self.model = env.get('OPENROUTER_MODEL', cfg['model'])
        self.base = env.get('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1').rstrip('/')
        if self.model != cfg['model'] or self.base != 'https://openrouter.ai/api/v1':
            raise transport.CriticalAbort('GatewayEndpointOrModelMismatch')
        self.cfg, self.coordinator = cfg, coordinator or transport.RunBudget(cfg, output)
        self.prompt = prompt_path.read_text()
        self.client = httpx.Client(timeout=60, headers={'Authorization': 'Bearer ' + key})
        self.totals = {'calls': 0, 'reserved_usd': 0.0, 'reported_usd': 0.0, 'missing_cost': 0}

    def budget(self):
        return dict(self.totals)

    def close(self):
        self.client.close()

    def generate(self, question, evidence, path):
        content = question + '\n\nEvidence:\n' + evidence
        if len(self.prompt) + len(content) > self.cfg['max_prompt_chars']:
            raise transport.CriticalAbort('PromptLimit')
        prices = self.cfg['provider_max_price_per_million']
        if any(type(prices.get(k)) not in (int, float) or not math.isfinite(prices[k])
               or prices[k] <= 0 for k in ('prompt', 'completion')):
            raise transport.CriticalAbort('InvalidPriceCaps')
        upper = ((len((self.prompt + content).encode()) + 2048) * prices['prompt']
                 + 300 * prices['completion']) / 1e6
        request = {'model': self.model, 'temperature': self.cfg['temperature'], 'max_tokens': 300,
                   'response_format': {'type': 'json_object'},
                   'provider': {'max_price': prices, 'allow_fallbacks': False},
                   'usage': {'include': True},
                   'messages': [{'role': 'system', 'content': self.prompt},
                                {'role': 'user', 'content': content}]}
        transport.atomic_write(path / 'request.json', request)
        self.coordinator.reserve(upper)
        self.totals['calls'] += 1
        self.totals['reserved_usd'] += upper
        started = time.perf_counter()
        try:
            response = self.client.post(self.base + '/chat/completions', json=request)
            (path / 'response.json').write_text(response.text)
            raw = response.json()
            cost = raw['usage']['cost']
            if type(cost) not in (int, float) or not math.isfinite(cost) or cost < 0 or cost > upper + 1e-12:
                raise ValueError('InvalidUsageCost')
        except Exception as exc:
            self.totals['missing_cost'] += 1
            self.coordinator.report(0, 1)
            self.coordinator.stopped.set()
            raise UnknownCost('UnaccountedAttempt') from exc
        self.totals['reported_usd'] += cost
        self.coordinator.report(cost, 0)
        metadata = {'model': raw.get('model'), 'provider': raw.get('provider'),
                    'generation_id': raw.get('id'), 'usage': raw['usage'],
                    'llm_ms': (time.perf_counter() - started) * 1000,
                    'http_status': response.status_code}
        transport.atomic_write(path / 'metadata.json', metadata)
        response.raise_for_status()  # A known-cost HTTP error remains a failed row.
        choice = raw['choices'][0]
        metadata['finish_reason'] = choice.get('finish_reason')
        transport.atomic_write(path / 'metadata.json', metadata)
        return json.loads(choice['message']['content']), metadata


def evaluate(row, expected):
    answer = row['answer']
    by_id = {r['id']: r for r in row['final_records']}
    cited = [by_id[c] for c in answer['citations'] if c in by_id]
    q = row['query']
    cited_exist = bool(answer['citations']) and len(cited) == len(answer['citations'])
    applicable = cited_exist and all(
        r['subject'] == q['subject'] and r['relation'] == q['relation']
        and r['status'] == 'current' and r['start'] <= q['as_of']
        and (r['end'] is None or r['end'] > q['as_of']) for r in cited)
    supported = cited_exist and all(r['candidate'] == answer['candidate'] for r in cited)
    return {'evidence_applicable': applicable if answer['decision'] == 'answer' else None,
                'evidence_support': supported if answer['decision'] == 'answer' else None,
                'policy_correct': answer['decision'] == expected['decision'] and answer['candidate'] == expected['policy_candidate'] and sorted(answer['citations']) == expected['policy_citations'],
                'correct_answer': answer['decision'] == 'answer' and answer['candidate'] == expected['candidate'],
                'correct': answer['decision'] == expected['decision'] and answer['candidate'] == expected['candidate'],
                'wrong_answer': answer['decision'] == 'answer' and answer['candidate'] != expected['candidate'],
                'unnecessary_abstention': answer['decision'] == 'abstain' and expected['answerable'],
                'first_decision_correct': row['trace'][0]['decision'] == expected['first_decision']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--llm', action='store_true', help='Authorize paid experimental calls; default offline')
    parser.add_argument('--stale-followup', action='store_true',
                        help='Posthoc paired two-task follow-up; only source evidence changes')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--seed', type=int, default=20261013)
    args = parser.parse_args()
    output = args.output or ROOT / 'runs' / (datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ') + '-semantic-' + uuid.uuid4().hex[:8])
    output.mkdir(parents=True, exist_ok=False)
    runtime, gold = targeted_fixtures(args.seed) if args.stale_followup else fixtures(args.seed)
    cfg = config()
    if args.stale_followup:
        cfg.update(max_llm_calls=24, max_cost_usd=0.10)
    conditions = ['code', 'shacl'] + (['llm'] if args.llm else [])
    schedule = [{'case_id': c['id'], 'condition': k, 'paraphrase': p, 'repeat': r}
                for c in runtime for k in conditions for p in range(3) for r in range(2)]
    random.Random(args.seed).shuffle(schedule)
    for name, value in [('runtime.json', runtime), ('evaluation.json', gold), ('config.json', cfg), ('schedule.json', schedule)]:
        transport.atomic_write(output / name, value)
    (output / 'prompt.txt').write_text(PROMPT)
    (output / 'shapes.ttl').write_text(SHAPES)
    for name in ('run_semantic_study.py', 'run_comparison_study.py', 'run_gleif_comparison.py', 'run_gleif_pilot.py'):
        shutil.copyfile(ROOT / 'scripts' / name, output / name)
    shutil.copyfile(ROOT / 'uv.lock', output / 'uv.lock')
    frozen = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}
    transport.atomic_write(output / 'freeze.json', frozen)
    rows = [dict(**item, status='not_executed') for item in schedule]
    record = {'protocol': 'semantic-stale-followup-1' if args.stale_followup else 'semantic-exploratory-2',
                  'posthoc_paired_followup': args.stale_followup, 'synthetic': True, 'seed': args.seed, 'rows': rows, 'status': 'running',
                  'planned_rows': len(rows), 'max_planned_llm_calls': len(runtime) * 3 * 2 * 2 if args.llm else 0}
    transport.atomic_write(output / 'record.json', record)
    budget = None
    if args.llm:
        if not Path(cfg['campaign_ledger_path']).exists():
            raise RuntimeError('ExistingCampaignLedgerRequired')
        budget = transport.RunBudget(cfg, output)
    cases = {c['id']: c for c in runtime}
    try:
        for index, row in enumerate(rows):
            directory = output / f'row-{index:04d}'
            directory.mkdir()
            gateway = None
            row['status'] = 'running'
            transport.atomic_write(output / 'record.json', record)
            try:
                if row['condition'] == 'llm':
                    gateway = SemanticGateway(cfg, output, output / 'prompt.txt', budget)
                def judge(payload, step, directory=directory):
                    transport.atomic_write(directory / f'payload-{step}.json', payload)
                    result = decide(payload, step)
                    transport.atomic_write(directory / f'decision-{step}.json', result)
                    return result
                def decide(payload, step, row=row, directory=directory, gateway=gateway):
                    if row['condition'] == 'code':
                        return code_judge(payload)
                    if row['condition'] == 'shacl':
                        return shacl_judge(payload, directory / f'report-{step}.ttl')
                    path = directory / str(step)
                    path.mkdir()
                    inner, _metadata = gateway.generate(payload['question'], json.dumps(payload), path)
                    return inner
                row['trace'] = []
                row.update(run_case(cases[row['case_id']], row['paraphrase'], judge, row['trace']))
                row.update(evaluate(row, gold[row['case_id']]), status='ok')
            except BaseException as exc:
                row.update(status='error', error_type=type(exc).__name__)
                if isinstance(exc, UnknownCost):
                    row['cost_accounting_unknown'] = True
                if not isinstance(exc, Exception) or isinstance(exc, transport.CriticalAbort):
                    raise
            finally:
                if gateway:
                    row['cost'] = gateway.budget()
                    gateway.close()
                transport.atomic_write(output / 'record.json', record)
        record['status'] = 'complete'
    finally:
        if record['status'] != 'complete':
            record['status'] = 'interrupted'
        record['budget'] = budget.budget() if budget else {}
        record['unknown_cost_rows'] = sum(bool(r.get('cost_accounting_unknown')) for r in rows)
        transport.atomic_write(output / 'record.json', record)
    print(output)


if __name__ == '__main__':
    main()
