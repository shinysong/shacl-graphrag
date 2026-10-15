#!/usr/bin/env python3
"""Offline reference scorer; never imported into the experimental runtime."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from rdflib import Graph, URIRef


def typed_equal(left, right):
    """JSON type equality, with order-insensitive lists; bool is not integer."""
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        if len(left) != len(right):
            return False
        remaining = list(right)
        for value in left:
            found = next((i for i, other in enumerate(remaining) if typed_equal(value, other)), None)
            if found is None:
                return False
            remaining.pop(found)
        return True
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(typed_equal(left[k], right[k]) for k in left)
    return left == right


def read_json(path):
    return json.loads(Path(path).read_text())


def read_events(path):
    if not path.exists():
        return [], ['events_missing']
    events, errors = [], []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        try:
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError('not an object')
            events.append(event)
        except (ValueError, TypeError):
            errors.append(f'event_line_{number}_invalid')
    return events, errors


def summarize(rows):
    counts = Counter()
    terminals = Counter()
    check_results = Counter()
    reported_cost = 0.0
    for row in rows:
        counts['assigned'] += 1
        terminals[row['terminal_status']] += 1
        for key in ('finished', 'failed', 'unfinished', 'decision_match', 'qualified_decision_match', 'evidence_exact', 'wrong_substantive', 'unnecessary_withholding'):
            counts[key] += int(row[key])
        counts['invalid_citation_episodes'] += int(bool(row['invalid_citations']))
        counts['unretrieved_citation_episodes'] += int(bool(row['unretrieved_citations']))
        counts['episodes_using_checks'] += int(bool(row['checks']))
        counts['observed_tool_errors'] += len(row['tool_errors'])
        for key, value in row['counts'].items():
            if type(value) is int:
                counts[key] += value
        counts['calls_with_metadata'] += row['calls_with_metadata']
        counts['calls_without_metadata'] += row['calls_without_metadata']
        counts['call_failure_artifacts'] += row['call_failure_artifacts']
        reported_cost += row['reported_cost_usd']
        check_results.update(item.get('status', 'unknown') for item in row['checks'])
    return {'counts': dict(counts), 'terminal_statuses': dict(terminals), 'check_results': dict(check_results), 'reported_cost_usd': reported_cost, 'decision_match_denominator': len(rows), 'rate': counts['decision_match'] / len(rows) if rows else None}


def analyze(runs, references):
    refs_list = read_json(references)
    refs = {r['case_id']: r for r in refs_list}
    if len(refs) != len(refs_list):
        raise ValueError('Duplicate reference case IDs')
    results = []
    for run in map(Path, runs):
        record = read_json(run / 'record.json')
        runtime_path = run / 'runtime.json'
        runtimes = {c['case_id']: c['runtime'] for c in read_json(runtime_path)} if runtime_path.exists() else {}
        for assigned in record['rows']:
            case_id, arm = assigned['case_id'], assigned['arm']
            ref = refs[case_id]
            episode_id = assigned.get('episode_id', f'{case_id}-{arm}')
            # Paths come from stored run data, not a model response.
            if Path(episode_id).name != episode_id:
                raise ValueError('Unsafe episode path')
            directory = run / episode_id
            saved = read_json(directory / 'result.json') if (directory / 'result.json').exists() else {}
            row = dict(assigned, **saved)
            terminal = row.get('status', 'not_executed')
            answer = row.get('answer') or {}
            expected = ref['expected']
            events, event_errors = read_events(directory / 'events.jsonl')
            runtime = runtimes.get(case_id, {})
            source_ids = None
            turtle = runtime.get('source_turtle', runtime.get('turtle'))
            if turtle is not None:
                graph = Graph().parse(data=turtle, format='turtle')
                source_ids = {str(v) for v in graph.objects(None, URIRef('urn:business-questions:id'))}
            citations = answer.get('evidence_ids', [])
            citation_schema_valid = isinstance(citations, list) and all(isinstance(v, str) for v in citations)
            cited = set(citations) if citation_schema_valid else set()
            finished = terminal == 'finished'
            decision_match = finished and answer.get('status') == expected['status'] and typed_equal(answer.get('value'), expected.get('value'))
            caveats = answer.get('caveats', [])
            caveat_text = ' '.join(caveats).casefold() if isinstance(caveats, list) and all(isinstance(v, str) for v in caveats) else ''
            caveats_match = all(term.casefold() in caveat_text for term in expected.get('required_caveat_terms', []))
            tool_results = [e.get('payload', {}) for e in events if e.get('event_type') == 'tool_result']
            checks = [{'tool': e.get('name'), **e.get('response', {})} for e in tool_results if e.get('name') in ('check_query_contract', 'check_evidence')]
            tool_errors = [e for e in tool_results if e.get('response', {}).get('status') == 'error' or e.get('response', {}).get('error_type')]
            call_dirs = sorted({p.parent for p in directory.rglob('request.json')}) if directory.exists() else []
            metadata = [read_json(p) for p in directory.rglob('metadata.json')] if directory.exists() else []
            costs = [m.get('usage', {}).get('cost') for m in metadata]
            known = ('known', 'eligible', 'blocked', 'review_ready', 'review_required', 'reported_exception')
            withholding = ('unknown', 'incomplete', 'conflict', 'clarification')
            results.append({
                'run': str(run), 'episode_id': episode_id, 'case_id': case_id, 'arm': arm,
                'family': ref['family'], 'scenario': ref.get('scenario'), 'question': runtime.get('question', ref.get('question')),
                'expected': expected, 'answer': answer, 'terminal_status': terminal,
                'finished': finished, 'failed': terminal == 'failed', 'unfinished': not finished and terminal != 'failed',
                'decision_match': decision_match, 'caveats_match': caveats_match,
                'qualified_decision_match': decision_match and caveats_match,
                'evidence_exact': finished and citation_schema_valid and typed_equal(sorted(citations), sorted(expected.get('evidence_ids', []))),
                'citation_schema_valid': citation_schema_valid,
                'invalid_citations': sorted(cited - source_ids) if source_ids is not None else None,
                'citation_source_check': 'checked' if source_ids is not None else 'unverified_source_unavailable',
                'unretrieved_citations': sorted(cited - set(row.get('source_ids_retrieved', []))),
                'wrong_substantive': finished and not decision_match and answer.get('status') in known,
                'unnecessary_withholding': finished and answer.get('status') in withholding and expected['status'] in known,
                'counts': row.get('counts', {}), 'calls_with_metadata': len(metadata),
                'calls_without_metadata': sum(not (p / 'metadata.json').exists() for p in call_dirs),
                'call_failure_artifacts': len(list(directory.rglob('failure.json'))) if directory.exists() else 0,
                'reported_cost_usd': sum(c for c in costs if type(c) in (int, float)),
                'metadata_missing_cost': sum(type(c) not in (int, float) for c in costs),
                'checks': checks, 'tool_errors': tool_errors,
                'query_results': [e for e in tool_results if e.get('name') == 'query'],
                'interpretations': [e.get('payload') for e in events if e.get('event_type') == 'model_interpretation'],
                'final_events': [e.get('payload') for e in events if e.get('event_type') in ('final_answer', 'episode_stopped')],
                'format_errors': [e.get('payload') for e in events if e.get('event_type') == 'format_error'],
                'event_read_errors': event_errors, 'error_type': row.get('error_type'),
                'semantic_stage_attribution': 'unverified_without_independent_intent_and_evidence_adjudication',
            })
    arms, families = defaultdict(list), defaultdict(list)
    assignments = Counter((r['case_id'], r['arm']) for r in results)
    for row in results:
        arms[row['arm']].append(row)
        families[row['family']].append(row)
    return {
        'protocol': 'llm-ontology-tools-1-offline-analysis', 'overall': summarize(results),
        'by_arm': {k: summarize(v) for k, v in sorted(arms.items())},
        'by_family': {k: summarize(v) for k, v in sorted(families.items())},
        'by_arm_family': {arm: {family: summarize([r for r in rows if r['family'] == family]) for family in sorted({r['family'] for r in rows})} for arm, rows in sorted(arms.items())},
        'repeated_assignments': [{'case_id': c, 'arm': a, 'count': n} for (c, a), n in sorted(assignments.items()) if n > 1],
        'limitations': ['All assigned rows retained; repeated run assignments are not deduplicated or independent trials.', 'Decision agreement excludes citations; qualified agreement additionally requires caveat terms. Evidence equality and invalid/unretrieved citations reported separately.', 'Reported costs sum saved call metadata only; missing metadata and unresolved reservations are not zero-cost evidence. No ledger reservation is refunded.', 'Observed tool errors and declared interpretations do not independently identify semantic interpretation errors or causal repairs.', 'Consumed synthetic development references measure authored contract agreement, not external business truth.'],
        'rows': results,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', nargs='+', required=True)
    parser.add_argument('--references', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = analyze(args.runs, args.references)
    with Path(args.output).open('x') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
