"""Explicit modelling-rule inventory only; never a conformance checker."""
import xml.etree.ElementTree as ET
import hashlib
import json
from collections import Counter
from pathlib import Path
import source_projection as projection

P = Path(__file__).parent
UA = 'http://opcfoundation.org/UA/'


def run(config):
    labels = json.loads((P / 'labels.json').read_text())['labels']
    relation = json.dumps([UA, 'i=37'], separators=(',', ':'))
    slots = []
    for spec in config['sources']:
        slot = {'source': spec, 'status': 'source_failed', 'declarations': []}
        try:
            raw = Path(spec['path']).read_bytes()
            if hashlib.sha256(raw).hexdigest() != spec['sha256']:
                raise ValueError('source_hash_mismatch')
            parsed = projection.parse(spec['path'])
            declarations = []
            for key, node in sorted(parsed['nodes'].items()):
                targets = sorted({target for kind, forward, target in node['references']
                                  if kind == relation and forward})
                if not targets:
                    continue
                declarations.append({
                    'key': key, 'class': node['class'], 'browse': node['browse'],
                    'parent': node['parent'], 'rules': targets,
                    'rule_labels': [labels.get(json.loads(t)[1][2:], 'unmapped')
                                    if json.loads(t)[0] == UA else 'external_unmapped'
                                    for t in targets],
                    'explicit_type_targets': sorted({target for kind, forward, target in node['references']
                        if forward and kind == json.dumps([UA, 'i=40'], separators=(',', ':'))}),
                })
            slot.update(status='completed', declarations=declarations,
                        nodes=len(parsed['nodes']), marked_nodes=len(declarations),
                        rule_occurrences=dict(sorted(Counter(label for d in declarations
                            for label in d['rule_labels']).items())),
                        class_counts=dict(sorted(Counter(d['class'] for d in declarations).items())),
                        multi_rule_nodes=sum(len(d['rules']) != 1 for d in declarations))
        except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as exc:
            slot['error'] = type(exc).__name__ + ': ' + str(exc)
        slots.append(slot)
    return {'scope': config['scope'], 'planned_source_slots': len(config['sources']),
            'slots': slots, 'conformance_evaluated': False,
            'inherited_declarations_computed': False, 'physical_assets_evaluated': False}


if __name__ == '__main__':
    result = run(json.loads((P / 'config.json').read_text()))
    (P / 'observed.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print([{k: s.get(k) for k in ('status', 'nodes', 'marked_nodes', 'rule_occurrences')}
           for s in result['slots']])
