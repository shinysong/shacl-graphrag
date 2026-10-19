"""Offline paired witness audit of saved original upstream postprocessing.

Never generates, cleans, repairs, or modifies candidates or previous raw results.
"""
import argparse
from collections import Counter
import copy
import fcntl
import json
from pathlib import Path
import re

from audit_nl2shacl_witnesses import account, execute
from render_nl2shacl_tier_report import collect, key, sha

OPTIONS = {'inference': 'none', 'advanced': False, 'meta_shacl': True,
           'do_owl_imports': False, 'abort_on_first': False,
           'allow_infos': False, 'allow_warnings': False}


def change_class(raw, cleaned):
    """Classification only: never feed this transformation to validation."""
    if raw == cleaned:
        return 'unchanged'
    match = re.fullmatch(r'\s*```(?:turtle|ttl)?[^\S\r\n]*\r?\n(.*?)\r?\n```\s*', raw, re.DOTALL)
    if match and match[1].strip() == cleaned.strip() and '```' not in match[1]:
        return 'outer_fence_removal_only_ignoring_boundary_whitespace'
    return 'original_postprocessing_change'


def run(audit, inputs, ledger, design, raw_results, output, pairs=None, timeout=30):
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    if not 0 < timeout <= 120:
        raise ValueError('Timeout must be in (0,120] seconds')
    with Path(ledger).with_suffix('.lock').open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('Ledger is busy') from exc
        data, tracked = collect(audit, inputs, ledger, pairs)

        def read(path, expected=None, *, binary=False):
            path = Path(path).resolve()
            digest = sha(path)
            if expected is not None and digest != expected:
                raise ValueError('Hash mismatch: ' + str(path))
            if str(path) in tracked and tracked[str(path)] != digest:
                raise ValueError('Input changed: ' + str(path))
            tracked[str(path)] = digest
            return path.read_bytes() if binary else path.read_text(encoding='utf-8')

        audit_data = json.loads(read(audit))
        manifests = [Path(p).resolve() for p in audit_data['hashes'] if Path(p).name == 'source-hashes.json']
        if len(manifests) != 1:
            raise ValueError('Missing or ambiguous source manifest')
        manifest = manifests[0]
        if json.loads(read(manifest)) != audit_data['source_hashes'] or not audit_data['source_hashes']:
            raise ValueError('Source manifest binding mismatch')
        for name, digest in audit_data['source_hashes'].items():
            path = (manifest.parent / name).resolve()
            if not path.is_relative_to(manifest.parent):
                raise ValueError('Source path escapes manifest root')
            read(path, digest, binary=True)
        design_data = json.loads(read(design))
        previous = json.loads(read(raw_results))
        if previous['protocol'] != 'nl2shacl-finite-witness-audit-1':
            raise ValueError('Unexpected raw result protocol')
        for field, path in [('audit', audit), ('design', design)]:
            if Path(previous[field]).resolve() != Path(path).resolve():
                raise ValueError('Raw result ' + field + ' binding mismatch')
            hashes = {str(Path(p).resolve()): h for p, h in previous['hashes'].items()}
            if hashes.get(str(Path(path).resolve())) != sha(path):
                raise ValueError('Raw result ' + field + ' hash mismatch')
        for path, digest in previous['hashes'].items():
            read(path, digest)
        read(design_data['source_pairs_path'], design_data['source_pairs_sha256'])
        if pairs and Path(pairs).resolve() != Path(design_data['source_pairs_path']).resolve():
            raise ValueError('Design pair binding mismatch')
        reference = read(design_data['reference_path'], design_data['reference_sha256'])
        probes = []
        for probe in design_data['witnesses']:
            if type(probe['expected_reference_conforms']) is not bool:
                raise ValueError('Nonboolean expectation')
            probes.append({**probe, 'ttl': read(probe['data_path'], probe['sha256'])})
        if not probes or len({p['id'] for p in probes}) != len(probes):
            raise ValueError('Empty or duplicate witnesses')
        if design_data['validation_options'] != OPTIONS or previous['validation_options'] != OPTIONS:
            raise ValueError('Unsupported validation options')
        payload = dict(reference=reference, witnesses=probes, options=OPTIONS)
        baseline = account(execute({**payload, 'shape': reference}, timeout), probes)
        if baseline['counts']['agreement'] != len(probes):
            raise ValueError('Reference witness expectation mismatch')
        selected = [r for r in data['rows'] if r['id'] == design_data['case_id']]
        attempted = [r for r in selected if r['status'] != 'unexecuted']
        old = {key(r): r for r in previous['rows']}
        if len(old) != len(previous['rows']) or set(old) != {key(r) for r in attempted}:
            raise ValueError('Raw candidate binding mismatch')
        if previous['candidate_count'] != len(attempted) or previous['witnesses_per_candidate'] != len(probes):
            raise ValueError('Raw denominator mismatch')
        rows, raw_total, normalized_total, transitions = [], Counter(), Counter(), Counter()
        counterexamples = []
        for row in selected:
            item = {k: row[k] for k in ('model', 'id', 'language', 'status')}
            if row['status'] == 'unexecuted':
                item.update(pipeline_status='unexecuted', raw_result=None, normalized_result=None)
                rows.append(item)
                continue
            prior = old[key(row)]
            if prior['reservation_index'] != row['reservation_index'] or prior['audit_raw_meta'] != row['meta']:
                raise ValueError('Raw row audit binding mismatch')
            raw_result = copy.deepcopy(prior['result'])
            # Recount saved outcomes, not re-execute or reinterpret the original candidates.
            checked = account(copy.deepcopy(raw_result), probes)
            if checked['counts'] != raw_result['counts']:
                raise ValueError('Raw saved counts mismatch')
            if row['status'] == 'failed':
                if raw_result.get('reason') != 'terminal_provider_failure':
                    raise ValueError('Raw provider failure mismatch')
                normalized = account({'status': 'unavailable', 'reason': 'terminal_provider_failure'}, probes)
                item.update(pipeline_status='terminal_provider_failure', postprocessing_change=None)
            else:
                if row['reference_sha256'] != design_data['reference_sha256'] or row['reference'] != reference:
                    raise ValueError('Design reference binding mismatch')
                if prior.get('raw_sha256') != row['raw_sha256']:
                    raise ValueError('Raw candidate hash mismatch')
                normalized = account(execute({**payload, 'shape': row['cleaned']}, timeout), probes)
                item.update(pipeline_status=normalized['status'], postprocessing_change=change_class(row['raw'], row['cleaned']),
                            raw_sha256=row['raw_sha256'], cleaned_sha256=row['cleaned_sha256'],
                            reference_sha256=row['reference_sha256'], audit_classification=row.get('classification'),
                            finish_reason=row.get('finish_reason'))
            item.update(reservation_index=row['reservation_index'], raw_result=raw_result, normalized_result=normalized)
            for result, total in [(raw_result, raw_total), (normalized, normalized_total)]:
                total.update(result['counts'])
            raw_probes = raw_result.get('witnesses') or raw_result['unavailable_witnesses']
            normalized_probes = normalized.get('witnesses') or normalized['unavailable_witnesses']
            if [p['id'] for p in raw_probes] != [p['id'] for p in probes]:
                raise ValueError('Raw witness binding mismatch')
            for before, after in zip(raw_probes, normalized_probes):
                transitions[before['outcome'] + ' -> ' + after['outcome']] += 1
                if any(p['outcome'] in ('underconstraint_observed', 'overconstraint_observed') for p in (before, after)):
                    counterexamples.append({**{k: row[k] for k in ('model', 'id', 'language')},
                                            'witness_id': before['id'], 'raw': before, 'normalized': after})
            rows.append(item)
        if dict(raw_total) != previous['summary']:
            raise ValueError('Raw summary mismatch')
        record = dict(protocol='nl2shacl-original-postprocessing-witness-audit-1', paid_calls=0,
                      audit=str(audit), design=str(design), raw_results=str(raw_results), hashes=tracked,
                      script_sha256=sha(__file__), reference_validation=baseline,
                      validation_options=OPTIONS, timeout_seconds_per_shape=timeout,
                      denominators=dict(planned=len(selected), attempted=len(attempted),
                                        completed=sum(r['status']=='completed' for r in selected),
                                        failed=sum(r['status']=='failed' for r in selected),
                                        unexecuted=sum(r['status']=='unexecuted' for r in selected),
                                        witnesses_per_attempt=len(probes)),
                      summary=dict(raw=dict(raw_total), normalized=dict(normalized_total), paired_transitions=dict(transitions)),
                      rows=rows, counterexamples=counterexamples,
                      limits=design_data['limits'] + [
                          'Saved original postprocessing only; no custom cleanup or gold repair. Raw results remain unchanged.',
                          'Finite reference-relative witness agreement is not semantic equivalence, external truth or a model ranking.',
                          'Provider failures count unavailable; unexecuted planned rows are excluded from witness denominators.',
                          'chemrof-2 prompts omit four reference enum identifiers; enum counterexamples retain this input underspecification qualification.',
                          'Length finish metadata and audit truncation classification are preserved, not inferred from parse failure.',
                          'Timeout loses partial progress; failed validation is unavailable, not a semantic negative.'])
        for path, expected in tracked.items():
            if sha(path) != expected:
                raise ValueError('Inputs changed while evaluating')
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', encoding='utf-8') as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('audit', 'inputs', 'ledger', 'design', 'raw-results', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--pairs', type=Path)
    parser.add_argument('--timeout', type=float, default=30)
    args = parser.parse_args()
    print(json.dumps(run(**vars(args))['summary']))
