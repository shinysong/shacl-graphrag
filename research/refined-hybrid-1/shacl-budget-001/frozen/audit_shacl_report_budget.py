"""Audit exact-C evidence plus lossless operational report using E5 accounting only."""
import argparse
import hashlib
import importlib.metadata
import json
import shutil
from pathlib import Path
from tokenizers import Tokenizer


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def compact(report):
    # Python comparator duplicates and raw RDF stay archived, outside the proposed prompt.
    keys = ('raw_conforms', 'results', 'applicable_bindings', 'coverage', 'no_bindings_status')
    result = {key: report[key] for key in keys}
    if not report['parity'] or report['results'] != report['python_results']:
        raise ValueError('SHACL/Python mismatch')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    summary = {'status': 'failed', 'planned': 24, 'generation_executed': False,
               'accounting_tokenizer': 'pinned-E5-not-generator',
               'token_cap': 4096, 'byte_cap': 64000,
               'generator_readiness': 'unmeasured: generator tokenizer, question and prompt overhead not included'}
    rows = []
    try:
        m = json.loads(Path(args.manifest).read_text())
        def verify():
            for path, digest in m['hashes'].items():
                if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
                    raise ValueError('hash mismatch: ' + path)
        verify()
        if importlib.metadata.version('tokenizers') != '0.22.1':
            raise ValueError('tokenizers version mismatch')
        tokenizer = Tokenizer.from_file(m['tokenizer'])
        tokenizer.no_padding()
        tokenizer.no_truncation()
        inputs = [json.loads(x) for x in Path(m['input']).read_text().splitlines()]
        evidence = [json.loads(x) for x in Path(m['evidence']).read_text().splitlines()]
        if len(inputs) != 24 or len(evidence) != 24 or len({x['question_id'] for x in inputs}) != 24:
            raise ValueError('question universe')
        if [x['question_id'] for x in inputs] != [x['question_id'] for x in evidence]:
            raise ValueError('question order')
        frozen = out / 'frozen'
        frozen.mkdir()
        for path in m['hashes']:
            shutil.copyfile(path, frozen / Path(path).name)
        shutil.copyfile(args.manifest, out / 'manifest.json')
        for source, envelope in zip(inputs, evidence):
            row = {'question_id': source['question_id'], 'status': 'error'}
            try:
                if source['status'] != 'ok' or source['evidence'] != envelope:
                    raise ValueError('input failure or altered C evidence')
                report = compact(source['report'])
                chunks = envelope['selected_chunks']
                variants = {'evidence_only': chunks,
                            'wrapped_evidence': {'evidence': chunks},
                            'full_report': {'evidence': chunks, 'validation': source['report']},
                            'compact_report': {'evidence': chunks, 'validation': report}}
                metrics = {}
                for name, payload in variants.items():
                    raw = canonical(payload)
                    n = len(tokenizer.encode(raw.decode()).ids)
                    metrics[name] = {'tokens': n, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                                     'within_accounting_cap': n <= 4096 and len(raw) <= 64000}
                    artifact = out / (source['question_id'] + '.' + name + '.json')
                    artifact.write_bytes(raw)
                    saved = artifact.read_bytes()
                    if len(saved) != len(raw) or hashlib.sha256(saved).hexdigest() != metrics[name]['sha256']:
                        raise ValueError('saved payload mismatch')
                if metrics['evidence_only']['tokens'] != envelope['accounting_tokens']:
                    raise ValueError('stored evidence accounting mismatch')
                row.update(status='ok', metrics=metrics)
            except Exception as exc:
                row['error'] = f'{type(exc).__name__}: {exc}'
            rows.append(row)
            (out / 'results.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
        verify()
        good = [r for r in rows if r['status'] == 'ok']
        summary.update(status='completed' if len(good) == 24 else 'partial_failure', ok=len(good), failed=24-len(good),
                       variants={name: {'within_cap': sum(r['metrics'][name]['within_accounting_cap'] for r in good),
                                        'over_cap': sum(not r['metrics'][name]['within_accounting_cap'] for r in good),
                                        'max_tokens': max((r['metrics'][name]['tokens'] for r in good), default=None)}
                                 for name in ('evidence_only', 'wrapped_evidence', 'full_report', 'compact_report')})
    except Exception as exc:
        summary.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        summary.update(processed=len(rows), unprocessed=24-len(rows))
        (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        print(json.dumps(summary))


if __name__ == '__main__':
    main()
