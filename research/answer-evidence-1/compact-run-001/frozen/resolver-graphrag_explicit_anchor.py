"""Literal source locator candidates, not question interpretation or retrieval."""
import hashlib
import json
import re

from graphrag_expand import _index

VERSION = 'explicit-anchor-contract-1'
LOCATOR = re.compile(r'^제공된 자료 안에서 (?P<coupon>PP[1-9][0-9]*) 작업표 (?P<row>[1-9][0-9]*)행')
COUPON = re.compile(r'PP[+-]?[0-9]+')
ROW = re.compile(r'[+-]?[0-9]+\s*행')


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def _constant(value):
    raise ValueError('nonfinite JSON constant')


def resolve(question, source_bytes):
    """Return a literal candidate; no filesystem, scorer, network or ID lookup."""
    if not isinstance(question, str) or type(source_bytes) is not bytes:
        raise TypeError('expected question string and source bytes')
    encoded = question.encode('utf-8')
    result = dict(status='locator_unsupported', reason='locator_syntax',
                  contract_version=VERSION,
                  question_sha256=hashlib.sha256(encoded).hexdigest(),
                  source_sha256=hashlib.sha256(source_bytes).hexdigest(),
                  matched_span_start=None, matched_span_end=None, matched_text=None,
                  candidate_node_ids=[], candidate_chunk_ids=[], source_locators=[])
    if len(question) > 4096:
        result['reason'] = 'question_too_long'
        return result
    match = LOCATOR.match(question)
    if match is None:
        return result
    coupons, rows = list(COUPON.finditer(question)), list(ROW.finditer(question))
    if (len(coupons) != 1 or len(rows) != 1
            or coupons[0].span() != match.span('coupon')
            or rows[0].span() != (match.start('row'), match.end('row') + 1)):
        result['reason'] = 'locator_mentions'
        return result
    result.update(matched_span_start=match.start(), matched_span_end=match.end(),
                  matched_text=match.group())
    try:
        corpus = json.loads(source_bytes.decode('utf-8'), object_pairs_hook=_pairs,
                            parse_constant=_constant)
        if not isinstance(corpus, dict):
            raise ValueError('corpus must be object')
        nodes, _, _, node_chunks, _ = _index(corpus)
        candidates = []
        coupon, row = match.group('coupon'), int(match.group('row'))
        for nid, node in nodes.items():
            if node.get('node_type') != 'annotation':
                continue
            source = node['source']
            if not isinstance(source, dict):
                raise ValueError('annotation source must be object')
            if (not isinstance(source.get('coupon'), str)
                    or re.fullmatch(r'PP[1-9][0-9]*', source['coupon']) is None
                    or any(not isinstance(source.get(k), str) or not source[k]
                           for k in ('sheet', 'archive_path'))
                    or type(source.get('excel_row')) is not int
                    or source['excel_row'] <= 0):
                raise ValueError('annotation locator metadata invalid')
            if (source['coupon'] == coupon and source['sheet'] == coupon
                    and source['excel_row'] == row):
                candidates.append((nid, node_chunks[nid], source))
        # Populate only after every annotation was validated: no partial success.
        for nid, cid, source in sorted(candidates, key=lambda item: item[0]):
            result['candidate_node_ids'].append(nid)
            result['candidate_chunk_ids'].append(cid)
            result['source_locators'].append(dict(node_id=nid, chunk_id=cid,
                **{k: source[k] for k in ('archive_path', 'sheet', 'coupon', 'excel_row')}))
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError):
        result.update(status='source_invalid', reason='source_validation',
                      candidate_node_ids=[], candidate_chunk_ids=[], source_locators=[])
        return result
    count = len(result['candidate_node_ids'])
    result.update(status=('source_not_found' if count == 0 else
                          'resolved_unique' if count == 1 else 'source_ambiguous'),
                  reason=('no_match_in_bundle' if count == 0 else
                          'unique_literal_candidate' if count == 1 else 'multiple_matches_in_bundle'))
    return result
