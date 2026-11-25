"""Offline native Auto-Ontology export boundary. Every imported item is a proposal.

Schema reference: NVIDIA/auto-ontology ee42eff638ebd136c1c4fe4ab290785f912bb4bc,
server/model_interchange/schemas.py. No SQL or upstream approval is executable.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re

import yaml

UPSTREAM = {'repository': 'https://github.com/NVIDIA/auto-ontology',
            'commit': 'ee42eff638ebd136c1c4fe4ab290785f912bb4bc', 'version': '1.3.0'}
MAX_BYTES = 1_000_000
MAX_NODES = 20000
MAX_DEPTH = 32


class ExtensionParseError(ValueError):
    """Invalid YAML, ambiguous mapping, or exceeded input safety limit."""


class UnsupportedExport(ValueError):
    """Well-formed input that does not match the supported native structure."""


def _digest(value):
    return hashlib.sha256(value).hexdigest()


def _load(raw):
    if not isinstance(raw, bytes):
        raise TypeError('raw must be bytes to preserve exact provenance')
    if len(raw) > MAX_BYTES:
        raise ExtensionParseError('export exceeds byte limit')
    try:
        text = raw.decode('utf-8')
        depth = count = 0
        for event in yaml.parse(text, Loader=yaml.SafeLoader):
            count += 1
            if count > MAX_NODES or isinstance(event, yaml.AliasEvent):
                raise ExtensionParseError('aliases or excessive YAML nodes are not accepted')
            if isinstance(event, (yaml.MappingStartEvent, yaml.SequenceStartEvent)):
                depth += 1
                if depth > MAX_DEPTH:
                    raise ExtensionParseError('export exceeds nesting limit')
            elif isinstance(event, (yaml.MappingEndEvent, yaml.SequenceEndEvent)):
                depth -= 1
        class Loader(yaml.SafeLoader):
            pass

        def mapping(loader, node):
            result = {}
            for key_node, value_node in node.value:
                key = loader.construct_object(key_node)
                if not isinstance(key, str) or key in result:
                    raise ExtensionParseError('mapping keys must be unique strings')
                result[key] = loader.construct_object(value_node)
            return result
        Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
        value = yaml.load(text, Loader=Loader)
        # Keep the proposal JSON-compatible; dates, binary and nonfinite values
        # require an explicit adapter rather than implicit lossy conversion.
        json.dumps(value, allow_nan=False)
        return value
    except ExtensionParseError:
        raise
    except (UnicodeError, yaml.YAMLError, ValueError, TypeError, RecursionError) as exc:
        raise ExtensionParseError('invalid or unsupported YAML scalar encoding') from exc


def import_auto_ontology(raw: bytes, *, base_workspace_digest: str,
                         source_hashes: dict[str, str]) -> dict:
    """Return a neutral pending envelope without mutating a workspace.

    Caller supplies the workspace binding. Export fields cannot overwrite it.
    Unknown content remains in ``raw_document`` and explicit diagnostics.
    """
    if not isinstance(base_workspace_digest, str) or not re.fullmatch(r'[a-f0-9]{64}', base_workspace_digest):
        raise ValueError('base_workspace_digest must be a SHA-256 hex digest')
    if not isinstance(source_hashes, dict) or any(
        not isinstance(k, str) or not isinstance(v, str) or not re.fullmatch(r'[a-f0-9]{64}', v)
        for k, v in source_hashes.items()
    ):
        raise ValueError('source_hashes must map source identifiers to SHA-256 hex digests')
    document = _load(raw)
    if not isinstance(document, dict) or not {'data_layer', 'semantic_layer'} <= document.keys():
        raise UnsupportedExport('expected native data_layer and semantic_layer mappings')
    result = {'format': 'workspace-extension-proposal-v1', 'status': 'pending',
              'upstream': dict(UPSTREAM),
              'identity_basis': 'converter_schema_target', 'producer_authenticated': False,
              'base_workspace_digest': base_workspace_digest,
              'source_hashes': dict(sorted(source_hashes.items())),
              'raw_sha256': _digest(raw), 'raw_base64': base64.b64encode(raw).decode('ascii'),
              'raw_document': document, 'concepts': [], 'fields': [], 'relations': [],
              'unsupported': [], 'unresolved_references': []}
    registry = {}
    references = []

    def unsupported(path, reason, value):
        result['unsupported'].append({'path': path, 'reason': reason, 'value': value})

    def obj(value, path, known):
        if not isinstance(value, dict):
            raise UnsupportedExport(f'{path} must be a mapping')
        for key in value.keys() - set(known):
            unsupported(f'{path}.{key}', 'unknown_field_not_applied', value[key])
        return value

    def rows(parent, key, path):
        value = parent.get(key, [])
        if not isinstance(value, list) or any(not isinstance(v, dict) for v in value):
            raise UnsupportedExport(f'{path}.{key} must be a list of mappings')
        return value

    def add(value, path, kind, bucket, known, parent=None):
        obj(value, path, known)
        sid = value.get('id')
        if not isinstance(sid, str) or not sid:
            raise UnsupportedExport(f'{path}.id must be a nonempty string')
        identity = (kind, sid)
        if identity in registry:
            raise UnsupportedExport(f'duplicate {kind} source id: {sid}')
        stable = 'auto-ontology:' + _digest(json.dumps(identity, separators=(',', ':')).encode())
        item = {'id': stable, 'source_id': sid, 'kind': kind, 'status': 'pending',
                'source_path': path, 'parent_id': parent, 'source_payload': value}
        registry[identity] = stable
        result[bucket].append(item)
        return stable

    def ref(value, key, target, path, many=False):
        values = value.get(key, [] if many else '')
        if many:
            if not isinstance(values, list) or any(not isinstance(x, str) for x in values):
                raise UnsupportedExport(f'{path}.{key} must be a list of IDs')
        elif not isinstance(values, str):
            raise UnsupportedExport(f'{path}.{key} must be an ID')
        else:
            values = [values] if values else []
        for sid in values:
            references.append((path + '.' + key, target, sid))

    obj(document, '$', ['data_layer', 'semantic_layer', 'zones'])
    data = obj(document['data_layer'], '$.data_layer', ['databases', 'foreign_keys', 'joins'])
    semantic = obj(document['semantic_layer'], '$.semantic_layer',
                   ['terms', 'concepts', 'semantic_fks', 'sql_attributes', 'custom_analyses'])
    for di, db in enumerate(rows(data, 'databases', '$.data_layer')):
        dp = f'$.data_layer.databases[{di}]'
        did = add(db, dp, 'database', 'concepts', ['id', 'dialect', 'schemas'])
        for si, schema in enumerate(rows(db, 'schemas', dp)):
            sp = f'{dp}.schemas[{si}]'
            scid = add(schema, sp, 'schema', 'concepts', ['id', 'name', 'database_name', 'tables'], did)
            for ti, table in enumerate(rows(schema, 'tables', sp)):
                tp = f'{sp}.tables[{ti}]'
                tid = add(table, tp, 'table', 'concepts', ['id', 'name', 'description', 'pk', 'type', 'columns'], scid)
                for ci, col in enumerate(rows(table, 'columns', tp)):
                    add(col, f'{tp}.columns[{ci}]', 'column', 'fields',
                        ['id', 'name', 'description', 'type', 'sample_values', 'is_nullable', 'is_unique'], tid)
                if table.get('pk'):
                    unsupported(tp + '.pk', 'physical_key_names_preserved_not_promoted', table['pk'])
    for i, term in enumerate(rows(semantic, 'terms', '$.semantic_layer')):
        p = f'$.semantic_layer.terms[{i}]'
        tid = add(term, p, 'term', 'concepts', ['id', 'name', 'description', 'represents', 'columns_attributes'])
        ref(term, 'represents', 'table', p, True)
        for j, attr in enumerate(rows(term, 'columns_attributes', p)):
            ap = f'{p}.columns_attributes[{j}]'
            add(attr, ap, 'column_attribute', 'fields', ['id', 'name', 'description', 'column_id'], tid)
            ref(attr, 'column_id', 'column', ap)
    for i, concept in enumerate(rows(semantic, 'concepts', '$.semantic_layer')):
        p = f'$.semantic_layer.concepts[{i}]'
        cid = add(concept, p, 'concept', 'concepts', ['id', 'name', 'description', 'term_ids', 'keys'])
        ref(concept, 'term_ids', 'term', p, True)
        for j, key in enumerate(rows(concept, 'keys', p)):
            kp = f'{p}.keys[{j}]'
            add(key, kp, 'concept_key', 'fields', ['id', 'name', 'column_ids'], cid)
            ref(key, 'column_ids', 'column', kp, True)
    relation_specs = [(data, 'foreign_keys', {'source_column_id': 'column', 'target_column_id': 'column'}),
                      (data, 'joins', {'source_table_id': 'table', 'target_table_id': 'table'}),
                      (semantic, 'semantic_fks', {'column_id': 'column', 'concept_key_id': 'concept_key', 'column_attribute_id': 'column_attribute'})]
    for parent, name, spec in relation_specs:
        layer = 'data_layer' if parent is data else 'semantic_layer'
        for i, relation in enumerate(rows(parent, name, '$.' + layer)):
            p = f'$.{layer}.{name}[{i}]'
            obj(relation, p, list(spec) + ['join_columns', 'use_in_join_paths'])
            result['relations'].append({'id': 'auto-ontology:' + _digest((name + json.dumps(relation, sort_keys=True)).encode()),
                                        'kind': name, 'status': 'pending', 'source_path': p, 'source_payload': relation})
            for key, target in spec.items():
                if not relation.get(key) and (name != 'semantic_fks' or key == 'column_id'):
                    raise UnsupportedExport(f'{p}.{key} must be a nonempty ID')
                ref(relation, key, target, p)
            if name == 'semantic_fks' and not (relation.get('concept_key_id') or relation.get('column_attribute_id')):
                unsupported(p, 'missing_semantic_reference_target', relation)
            if relation.get('join_columns'):
                unsupported(p + '.join_columns', 'join_expressions_preserved_not_executed', relation['join_columns'])
    for key in ['sql_attributes', 'custom_analyses']:
        if semantic.get(key):
            unsupported('$.semantic_layer.' + key, 'sql_or_analysis_preserved_not_executed', semantic[key])
    if document.get('zones'):
        unsupported('$.zones', 'upstream_policy_not_inherited', document['zones'])
    result['references'] = []
    for path, kind, sid in references:
        binding = {'path': path, 'target_kind': kind, 'source_id': sid, 'target_id': registry.get((kind, sid))}
        result['references'].append(binding)
        if binding['target_id'] is None:
            result['unresolved_references'].append(dict(binding))
    result['validation_state'] = 'needs_review' if result['unsupported'] or result['unresolved_references'] else 'parsed'
    return result
