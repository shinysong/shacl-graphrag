"""Offline saved-output audit. References are read only here, never for generation.

--output is a new JSON file; adjacent <stem>-artifacts preserves processed inputs
and optional original upstream CLI results/logs. Never reports semantic accuracy.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import importlib.metadata
import json
from pathlib import Path
import re
import subprocess
import sys

from audit_nl2shacl_saved_meta import check


DEFAULT_SOURCE = Path('_workspace/nl2shacl-ko')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write('\n')


def verify_sources(root):
    manifest = root / 'source-hashes.json'
    pins = json.loads(manifest.read_text())
    if not pins:
        raise ValueError('Empty source hash manifest')
    for name, digest in pins.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or sha(path) != digest:
            raise ValueError(f'Source hash mismatch: {name}')
    return pins


def load_postprocessor(root, pins):
    name = 'framework/NL2SHACL-Translator/postprocess.py'
    if name not in pins:
        raise ValueError('Unpinned postprocessor')
    spec = importlib.util.spec_from_file_location('pinned_nl2_postprocess', root / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def summarize(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row['model'], row['language'])].append(row)
    groups = []
    for (model, lang), members in sorted(grouped.items()):
        groups.append({'model': model, 'language': lang, 'reserved': len(members),
                       'completed': sum(r['status'] == 'completed' for r in members),
                       'classification': dict(Counter(r['classification'] for r in members)),
                       'raw_meta': dict(Counter(r['meta']['status'] for r in members)),
                       'upstream_scored': sum('upstream' in r for r in members),
                       'upstream_flags_pass': {k: sum((r.get('upstream', {}).get('validity') or {}).get(k) is True for r in members)
                                               for k in ('parsing_valid', 'spec_valid', 'vocab_valid')},
                       'upstream_gated_structural_isomorphism': sum((r.get('upstream', {}).get('structural') or {}).get('isomorphic') is True for r in members)})
    paired = []
    for model in sorted({r['model'] for r in rows}):
        by_id = defaultdict(dict)
        for row in rows:
            if row['model'] == model:
                by_id[row['id']][row['language']] = row
        both = [r for r in by_id.values() if set(r) == {'en', 'ko'}]
        complete = [r for r in both if all(x['status'] == 'completed' for x in r.values())]
        paired.append({'model': model, 'reserved_en_ko_pairs': len(both), 'completed_en_ko_pairs': len(complete),
                       'raw_meta_conformant_on_completed_pairs': {lang: sum(r[lang]['meta']['status'] == 'meta_conformant' for r in complete) for lang in ('en', 'ko')},
                       'unpaired_reserved_ids': sorted(k for k, r in by_id.items() if set(r) != {'en', 'ko'})})
    common = {}
    models = sorted({r['model'] for r in rows})
    for language in ('en', 'ko'):
        sets = [{r['id'] for r in rows if r['model'] == model and r['language'] == language and r['status'] == 'completed'} for model in models]
        ids = set.intersection(*sets) if sets else set()
        common[language] = {'completed_ids_shared_across_all_models': sorted(ids),
                            'raw_meta_conformant_on_shared_ids': {model: sum(r['model'] == model and r['language'] == language and r['id'] in ids and r['meta']['status'] == 'meta_conformant' for r in rows) for model in models}}
    return {'model_language': groups, 'paired': paired, 'across_model_matched_cases': common}


def run(ledger_path, output, source_root=DEFAULT_SOURCE, run_upstream=False):
    ledger_path, output, source_root = Path(ledger_path), Path(output), Path(source_root).resolve()
    artifacts = output.with_name(output.stem + '-artifacts')
    if output.exists() or artifacts.exists():
        raise FileExistsError('Audit output or artifact directory already exists')
    pins = verify_sources(source_root)
    post = load_postprocessor(source_root, pins)
    ledger_hash = sha(ledger_path)
    ledger = json.loads(ledger_path.read_text())
    generation = Path(ledger['output'])
    if not generation.is_absolute():
        generation = Path.cwd() / generation
    rows, processed, seen = [], defaultdict(list), set()
    hashes = {str(ledger_path): ledger_hash, str(source_root / 'source-hashes.json'): sha(source_root / 'source-hashes.json')}
    for index, item in enumerate(ledger['reservations']):
        key = (item['model'], item['id'], item['language'])
        if key in seen:
            raise ValueError(f'Duplicate reservation: {key}')
        seen.add(key)
        if not re.fullmatch(r'[A-Za-z0-9]+-\d+', item['id']) or item['language'] not in ('en', 'ko'):
            raise ValueError('Invalid case ID or language')
        row = {k: item[k] for k in ('model', 'id', 'language', 'status')}
        row.update(reservation_index=index, reported_usd=item.get('reported_usd'), upper_usd=item.get('upper_usd'),
                   meta={'status': 'not_evaluated'})
        rows.append(row)
        if item['status'] != 'completed':
            row['classification'] = 'provider_failure' if item['status'] == 'failed' else 'noncompleted'
            row['classification_note'] = 'Transport/provider or runner failure; no inference about generated semantics.'
            continue
        folder = generation / f'call-{index:04d}'
        raw_path, response_path = folder / 'output.ttl', folder / 'response.json'
        # Completed reservations must have both raw artifacts; never substitute empty output.
        raw_bytes = raw_path.read_bytes()
        raw = raw_bytes.decode('utf-8')
        response = json.loads(response_path.read_text())
        choice = response['choices'][0]
        if choice['message']['content'] != raw:
            raise ValueError(f'Raw response/output mismatch: {folder}')
        for path in (raw_path, response_path):
            hashes[str(path)] = sha(path)
        row.update(raw_sha256=hashes[str(raw_path)], provider=response.get('provider'),
                   response_model=response.get('model'), finish_reason=choice.get('finish_reason'),
                   usage=response.get('usage'), empty_output=not raw.strip(), meta=check(raw))
        row['classification'] = ('truncation' if choice.get('finish_reason') in ('length', 'max_tokens')
                                 else 'empty_output' if not raw.strip() else row['meta']['status'])
        cleaned = post.cleanup_output(raw)
        row['cleaned_sha256'] = hashlib.sha256(cleaned.encode()).hexdigest()
        row['postprocessing_changed_nonwhitespace'] = cleaned != raw.strip()
        subset = post.ID_PREFIX_TO_SUBSET.get(item['id'].split('-')[0])
        reference_name = f'dataset/{subset}/shacl/{item["id"]}.ttl'
        if reference_name not in pins:
            raise ValueError(f'Unpinned reference: {reference_name}')
        reference = source_root / reference_name
        row['reference_sha256'] = pins[reference_name]
        processed[item['model']].append({'id': item['id'] + '-' + item['language'],
                                        'output_shacl': cleaned, 'reference_shacl': reference.read_text()})
    if verify_sources(source_root) != pins or sha(ledger_path) != ledger_hash:
        raise ValueError('Inputs changed during audit')
    artifacts.mkdir(parents=True)
    cli_runs = []
    for index, (model, records) in enumerate(sorted(processed.items())):
        path = artifacts / f'cohort_model{index:03d}_processed.jsonl'
        with path.open('x', encoding='utf-8') as stream:
            for record in records:
                stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n')
        hashes[str(path)] = sha(path)
        cli = source_root / 'framework/Shapes-Evaluation/run_evaluation.py'
        command = [sys.executable, str(cli), '--input', str(path.resolve()), '--output_dir', str((artifacts / 'upstream').resolve()), '--run', 'structural']
        entry = {'model': model, 'processed_input': str(path), 'command': command, 'status': 'not_run'}
        cli_runs.append(entry)
        if not run_upstream:
            continue
        if 'framework/Shapes-Evaluation/run_evaluation.py' not in pins:
            raise ValueError('Unpinned evaluation CLI')
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        (artifacts / f'model{index:03d}.stdout.txt').write_text(result.stdout)
        (artifacts / f'model{index:03d}.stderr.txt').write_text(result.stderr)
        entry.update(exit_code=result.returncode, status='completed' if result.returncode == 0 else 'failed')
        if result.returncode:
            raise RuntimeError(f'Original evaluator failed; logs preserved at {artifacts}')
        eval_path = artifacts / 'upstream' / path.name.replace('_processed.jsonl', '_eval.jsonl')
        evaluated = [json.loads(line) for line in eval_path.read_text().splitlines()]
        by_id = {x['id']: x for x in evaluated}
        if len(by_id) != len(evaluated) or set(by_id) != {x['id'] for x in records}:
            raise ValueError('Upstream result IDs do not match processed inputs')
        hashes[str(eval_path)] = sha(eval_path)
        for row in rows:
            if row['model'] == model and row['status'] == 'completed':
                score = by_id[row['id'] + '-' + row['language']]
                row['upstream'] = {k: score[k] for k in ('status', 'validity', 'structural')}
    if verify_sources(source_root) != pins or any(sha(p) != h for p, h in hashes.items()):
        raise ValueError('Inputs/artifacts changed during evaluation')
    result = {'scope': 'Saved raw Turtle meta-SHACL versus cleaned original validity/structure; no semantic accuracy claim.',
              'paid_calls': 0, 'ledger': str(ledger_path), 'source_files_verified': len(pins),
              'versions': {p: importlib.metadata.version(p) for p in ('rdflib', 'pyshacl')},
              'meta_operation': 'pyshacl.entrypoints.meta_validate, inference=rdfs, do_owl_imports=False',
              'source_hashes': pins, 'hashes': hashes, 'upstream_runs': cli_runs,
              'summary': summarize(rows), 'rows': rows}
    write_json(output, result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledger', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--source-root', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--run-upstream', action='store_true')
    args = parser.parse_args()
    result = run(args.ledger, args.output, args.source_root, args.run_upstream)
    print(json.dumps(result['summary'], ensure_ascii=False, sort_keys=True))
