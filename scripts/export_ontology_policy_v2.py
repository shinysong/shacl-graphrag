"""Export a new policy-only development input version; never rewrite v1 artifacts."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/experiments/records/20261015-llm-ontology-tools-inputs.json'
SOURCE_SHA256 = '8ad4737a54ebdda6912f067a4067a25b6aa0fcfd85f131dbacb17003e558a4d1'
OLD = 'Follow current BOM membership transitively from part to containing products, reversing part_of edges.'
NEW = ('Follow current BOM membership transitively from part to containing products: '
       'traverse part_of from subject to object and contains from object to subject.')
VERSION_OLD = 'authored-business-policy-1'
VERSION_NEW = 'authored-business-policy-2'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def export(output, source=SOURCE):
    """Pinned consumed runtime-only snapshot; no scorer, model client or network."""
    raw = Path(source).read_bytes()
    if sha(raw) != SOURCE_SHA256:
        raise ValueError('SourceHashMismatch')
    original = json.loads(raw)
    revised = copy.deepcopy(original)
    changes = []
    for before, after in zip(original, revised, strict=True):
        policy = before['runtime']['public_policies']
        rule = policy['impact']['rule']
        if not rule.startswith(OLD) or rule.count(OLD) != 1 or policy['version'] != VERSION_OLD:
            raise ValueError('UnexpectedOriginalPolicy')
        new_policy = after['runtime']['public_policies']
        new_policy['impact']['rule'] = NEW + rule[len(OLD):]
        new_policy['version'] = VERSION_NEW
        changes.append({'case_id': before['case_id'],
                        'old_policy_sha256': sha(encoded(policy)),
                        'new_policy_sha256': sha(encoded(new_policy)),
                        'source_turtle_sha256': sha(before['runtime']['source_turtle'].encode()),
                        'shapes_turtle_sha256': sha(before['runtime']['shapes_turtle'].encode())})
        restored = copy.deepcopy(after)
        restored['runtime']['public_policies']['impact']['rule'] = rule
        restored['runtime']['public_policies']['version'] = VERSION_OLD
        if restored != before:
            raise ValueError('UnexpectedChange')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'protocol': 'llm-ontology-tools-2-policy-inputs', 'status': 'writing',
                'source_sha256': sha(raw), 'source_name': Path(source).name,
                'case_count': len(revised), 'consumed_development': True,
                'allowed_changed_paths': ['runtime.public_policies.impact.rule',
                                          'runtime.public_policies.version'],
                'sentence_replacement': {'old': OLD, 'new': NEW},
                'version_replacement': {'old': VERSION_OLD, 'new': VERSION_NEW},
                'cases': changes, 'new_model_results': False,
                'scope': 'Policy correction only. No lookup adapter or scorer generated. '
                         'No change to source, shapes, questions, other policy clauses or historical scores.'}
    manifest_path = output / 'manifest.json'
    manifest_path.write_bytes(encoded(manifest))
    try:
        payload = encoded(revised)
        with (output / 'runtime.json').open('xb') as handle:
            handle.write(payload)
        manifest.update(status='completed', runtime_sha256=sha(payload))
        manifest_path.write_bytes(encoded(manifest))
    except BaseException as exc:
        manifest.update(status='failed', error_type=type(exc).__name__)
        manifest_path.write_bytes(encoded(manifest))
        raise
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.output), indent=2))
