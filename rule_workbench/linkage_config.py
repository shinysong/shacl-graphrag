"""Portable linkage selections; loading never restores a review or executes."""
import copy
import json
import re
from .core import validate_project
from .linkage import table_digest
from .linkage_ui import parse_aliases

SELECTION = {'source_table', 'source_column', 'target_table', 'target_column'}
FIELDS = {'format', 'version', 'selection', 'aliases', 'equality_pairs', 'snapshot'}


def _selections(project, selection, pairs):
    validate_project(project)
    if not isinstance(selection, dict) or set(selection) != SELECTION or any(
            not isinstance(v, str) for v in selection.values()):
        raise ValueError('Invalid linkage selection.')
    tables = {t['id']: t for t in project['tables']}
    source, target = tables.get(selection['source_table']), tables.get(selection['target_table'])
    if (source is None or target is None or source is target
            or selection['source_column'] not in source['columns']
            or selection['target_column'] not in target['columns']):
        raise ValueError('Selected tables or columns are unavailable.')
    if not isinstance(pairs, list) or len(pairs) > 1:
        raise ValueError('Portable configuration supports zero or one equality pair.')
    for pair in pairs:
        if (not isinstance(pair, dict) or set(pair) != {'source_column','target_column'}
                or pair['source_column'] not in source['columns']
                or pair['target_column'] not in target['columns']):
            raise ValueError('Comparison columns are unavailable.')
    return source, target


def encode_linkage_config(project, selection, aliases=(), equality_pairs=()):
    pairs = list(equality_pairs)
    source,target = _selections(project,selection,pairs)
    checked_aliases = parse_aliases(json.dumps(list(aliases),ensure_ascii=False,allow_nan=False))
    config = {'format':'workbench-linkage-config','version':1,
              'selection':copy.deepcopy(selection),'aliases':checked_aliases,
              'equality_pairs':copy.deepcopy(pairs),
              'snapshot':{'source_digest':table_digest(source),'target_digest':table_digest(target)}}
    raw = json.dumps(config,ensure_ascii=False,indent=2,allow_nan=False).encode()
    if len(raw)>100000:
        raise ValueError('Configuration exceeds 100KB.')
    return raw


def decode_linkage_config(project, raw):
    if not isinstance(raw, bytes) or len(raw)>100000:
        raise ValueError('Configuration must be at most 100KB of JSON.')
    def unique_fields(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate JSON field.')
            result[key]=value
        return result
    try:
        config=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique_fields)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('Invalid configuration JSON.') from exc
    if (not isinstance(config,dict) or set(config)!=FIELDS
            or config['format']!='workbench-linkage-config' or type(config['version']) is not int
            or config['version']!=1):
        raise ValueError('Unsupported linkage configuration.')
    source,target=_selections(project,config['selection'],config['equality_pairs'])
    config['aliases']=parse_aliases(json.dumps(config['aliases'],ensure_ascii=False,allow_nan=False))
    snapshot=config['snapshot']
    if (not isinstance(snapshot,dict) or set(snapshot)!={'source_digest','target_digest'}
            or any(not isinstance(v,str) or not re.fullmatch('[0-9a-f]{64}',v) for v in snapshot.values())):
        raise ValueError('Invalid snapshot reference.')
    same=(snapshot['source_digest']==table_digest(source) and snapshot['target_digest']==table_digest(target))
    return {'config':config,'snapshot_status':'same_snapshot' if same else 'changed_snapshot',
            'review_status':'draft','equality_review_status':'draft','target_complete':False,
            'notice':'Reconfirm mapping, equality and reference scope before execution. Hashes are supplied consistency references, not authenticated approval.'}
