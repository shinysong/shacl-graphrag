"""Fixed local CPU GTE smoke; parent must enforce 180s timeout with 5s grace."""
import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import time


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda: f.read(1048576), b''):
            h.update(data)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    summary = {'status': 'started', 'model_executed': False, 'paid_calls': 0}
    results = []
    try:
        # Bound address space before importing numerical/custom libraries.
        resource.setrlimit(resource.RLIMIT_AS, (8 * 1024**3, 8 * 1024**3))
        os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                          OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2')
        manifest = json.loads(args.manifest.read_text())
        for path, expected in manifest['hashes'].items():
            if digest(path) != expected:
                raise ValueError('hash mismatch: ' + path)
        shutil.copyfile(args.manifest, args.output / 'manifest.json')
        shutil.copyfile(__file__, args.output / 'runner.py')
        for name, version in manifest['runtime'].items():
            if importlib.metadata.version(name) != version:
                raise ValueError('runtime mismatch: ' + name)
        import torch
        from tokenizers import Tokenizer
        from safetensors.torch import load_file
        if torch.version.cuda is not None:
            raise ValueError('CPU build required')
        torch.set_num_threads(2)
        torch.set_num_interop_threads(1)
        torch.set_default_dtype(torch.float32)
        torch.manual_seed(0)
        paths = manifest['paths']
        tokenizer = Tokenizer.from_file(paths['tokenizer'])
        tokenizer.no_padding()
        tokenizer.no_truncation()
        questions = json.loads(Path(paths['questions']).read_text())['questions']
        children = json.loads(Path(paths['children']).read_text())
        if len(questions) != 24 or len(children) != 1483:
            raise ValueError('input count mismatch')
        question = questions[0]
        encoded = [(len(tokenizer.encode(question['question'], c['search_text']).ids),
                    c['child_id'], c) for c in children]
        shortest = min(encoded, key=lambda x: (x[0], x[1]))
        longest = min(encoded, key=lambda x: (-x[0], x[1]))
        pairs = [shortest, longest, shortest, longest]
        if any(not 1 <= n <= 1024 for n, _, _ in pairs):
            raise ValueError('pair token cap exceeded')
        (args.output / 'selected-pairs.json').write_text(json.dumps([
            {'question_id': question['question_id'], 'child_id': i, 'tokens': n}
            for n, i, _ in pairs], indent=2))
        package = args.output / 'pinned_gte'
        package.mkdir()
        (package / '__init__.py').write_text('')
        for key, filename in [('configuration', 'configuration.py'), ('modeling', 'modeling.py')]:
            shutil.copyfile(paths[key], package / filename)
            if digest(package / filename) != manifest['hashes'][paths[key]]:
                raise ValueError('copied code mismatch')
        sys.path.insert(0, str(args.output.resolve()))
        config_class = importlib.import_module('pinned_gte.configuration').NewConfig
        model_class = importlib.import_module('pinned_gte.modeling').NewForSequenceClassification
        config = config_class(**json.loads(Path(paths['config']).read_text()))
        config._attn_implementation = 'eager'
        config.use_memory_efficient_attention = False
        config.unpad_inputs = False
        model = model_class(config).cpu().float()
        state = load_file(paths['weights'], device='cpu')
        model.load_state_dict(state, strict=True)
        del state
        model.eval()
        if any(p.device.type != 'cpu' or p.dtype != torch.float32 for p in model.parameters()):
            raise ValueError('effective parameter dtype/device mismatch')
        if any(m.training for m in model.modules()):
            raise ValueError('training enabled')
        if any(layer.attention.__class__.__name__ != 'NewAttention' for layer in model.new.encoder.layer):
            raise ValueError('non-eager attention')
        summary['effective'] = {'dtype': 'float32', 'device': 'cpu', 'attention': 'eager',
                                'eval': True, 'threads': torch.get_num_threads(),
                                'interop': torch.get_num_interop_threads(),
                                'address_space_limit': resource.getrlimit(resource.RLIMIT_AS)}
        with torch.inference_mode(), (args.output / 'progress.jsonl').open('w') as log:
            for n, child_id, child in pairs:
                e = tokenizer.encode(question['question'], child['search_text'])
                inputs = {k: torch.tensor([v], dtype=torch.int64) for k, v in
                          [('input_ids', e.ids), ('attention_mask', e.attention_mask),
                           ('token_type_ids', e.type_ids)]}
                summary['model_executed'] = True
                logits = model(**inputs, return_dict=True).logits
                if tuple(logits.shape) != (1, 1) or not torch.isfinite(logits).all():
                    raise ValueError('invalid logits')
                row = {'question_id': question['question_id'], 'child_id': child_id,
                       'tokens': n, 'logit': float(logits.item())}
                results.append(row)
                log.write(json.dumps(row) + '\n')
                log.flush()
        diffs = [abs(results[i]['logit'] - results[i+2]['logit']) for i in (0, 1)]
        if max(diffs) > 1e-5:
            raise ValueError('repeat tolerance exceeded')
        summary.update(status='completed', repeat_differences=diffs, encodings=len(results))
    except Exception as exc:
        summary.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        summary.update(elapsed_seconds=time.monotonic()-started,
                       process_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        (args.output / 'results.json').write_text(json.dumps(results, indent=2))
        (args.output / 'summary.json').write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary))


if __name__ == '__main__':
    main()
