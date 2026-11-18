"""Authored, keyless engine diagnostics, not fresh model or efficacy measurements."""
from pathlib import Path
import copy
import json
import difflib
from hashlib import sha256

from experiments.factory_complexity.tools import Views, RDFStudyTools
from experiments.query_contracts.competing import CompetingTools
from .explanation import shacl_trace, owl_trace

ROOT = Path(__file__).resolve().parents[2]
CASES = {
    'applicability': {'label': '단일 자격 기록의 적용 조건', 'order': 'O18', 'machine': 'M03', 'records': True},
    'conforming': {'label': '선택한 조건을 충족하는 근거', 'order': 'O17', 'machine': 'M01', 'records': True},
    'omitted': {'label': '자격 조회를 생략한 근거', 'order': 'O17', 'machine': 'M01', 'records': False},
    'altered': {'label': '원자료와 다르지만 통과하는 근거', 'order': 'O17', 'machine': 'M01', 'records': True},
}
ASSERTED = '''@prefix demo: <urn:factory-explanation:> .
demo:CAP-CUT a demo:CuttingCapability .
'''
ONTOLOGY = '''@prefix demo: <urn:factory-explanation:> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
demo:CuttingCapability rdfs:subClassOf demo:ManufacturingCapability .
'''


def run_case(case_id):
    if case_id not in CASES:
        raise ValueError('Unknown authored diagnostic')
    case = CASES[case_id]
    tools = CompetingTools(RDFStudyTools(Views(ROOT / 'examples/factory_lab/snapshots')))
    selected = tools.run('factory-v3', 'replacement_candidates', {'order_id': case['order']})
    original_count = len(selected['rows'])
    selected['rows'] = [r for r in selected['rows'] if r['machine']['id'] == case['machine']]
    evidence = [selected]
    if case['records']:
        evidence.append(tools.run('factory-v3', 'qualification_records', {'machine_id': case['machine']}))
    intervention = None
    if case_id == 'altered':
        evidence = copy.deepcopy(evidence)
        record = next(r['qualification'] for r in evidence[1]['rows'] if r.get('qualification'))
        intervention = {'field': 'valid_until', 'record': record['id'], 'source_value': record['valid_until'],
                        'injected_value': '2099-12-31', 'meaning': 'Authored contradiction to the bundled source, not real-world ground truth. This annotation is not passed to the checker.'}
        record['valid_until'] = intervention['injected_value']
        evidence[1]['diagnostic_modified'] = True
    return {
        'mode': 'authored_diagnostic_actual_local_engines', 'case_id': case_id,
        'label': case['label'],
        'question': f"{case['order']} 주문의 {case['machine']} 후보에 어떤 검토 근거가 있나요?",
        'execution_notice': 'Authored selection, not LLM planning. Fixed RDF queries, pySHACL and OWL-RL execute now. No API calls.',
        'projection': {'machine_id': case['machine'], 'rows_before': original_count,
                       'rows_after': len(selected['rows']), 'qualification_query_executed': case['records']},
        'evidence': evidence,
        'intervention': intervention,
        'shacl': shacl_trace(evidence),
        'owl': owl_trace(ASSERTED, ONTOLOGY) | {
            'provenance': 'Authored ontology overlay classifying the existing fictional CAP-CUT identifier. Not an extracted or expert-validated production ontology.',
            'relation_to_shacl': 'Separate illustration. OWL closure is not added to qualification review evidence.'},
        'answer_effect': {'status': 'unmeasured', 'draft': None, 'final': None,
                         'reason': 'No LLM answer generated for this diagnostic. A pass or violation is not a measured answer change.'},
    }


def historical_examples():
    directory = ROOT / 'examples/factory_lab/explanations'
    manifest = json.loads((directory / 'manifest.json').read_text())
    path = directory / 'historical.json'
    if sha256(path.read_bytes()).hexdigest() != manifest['files']['historical.json']:
        raise ValueError('Historical comparison bundle hash mismatch')
    return json.loads(path.read_text())


def selected_owl(execution):
    """Opt-in authored classification of CAP-CUT only if retrieved this execution."""
    evidence_ids = [c['id'] for c in execution['calls'] if not c.get('error')
                    and any(r.get('required_capability') == 'CAP-CUT' for r in c.get('result', {}).get('rows', []))]
    result = owl_trace(ASSERTED if evidence_ids else '', ONTOLOGY)
    result.update(assessment='selected_capability_classified' if evidence_ids else 'not_assessed',
                  evidence_ids=evidence_ids,
                  provenance='Opt-in authored class mapping for retrieved CAP-CUT identifier, not a class extracted from source or a learned ontology.',
                  answer_scope='Class membership only. Does not establish order eligibility, qualification, scheduling, truth or operational approval.')
    return result


def historical_trace(case_id):
    records = {x['id']: x for x in historical_examples()}
    if case_id not in records:
        raise ValueError('Unknown historical comparison')
    result = copy.deepcopy(records[case_id])
    result['shacl'] = shacl_trace(result['evidence'])
    result['trace_mode'] = 'Current posthoc pySHACL execution on saved selected evidence; original reports retained separately. No model call.'
    result['text_comparison'] = {arm: {'identical_to_draft': answer == result['draft'],
                                      'quality_effect': 'not_inferred_from_text_difference'}
                                 for arm, answer in result['finals'].items()}
    result['line_diffs'] = {arm: '\n'.join(difflib.unified_diff(result['draft'].splitlines(), answer.splitlines(),
                                                             fromfile='original draft', tofile=arm, lineterm=''))
                            for arm, answer in result['finals'].items()}
    return result
