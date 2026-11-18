"""Literal column mentions for human review, never semantic assertions."""
import re


def column_references(draft, limit=5):
    """Link saved document paragraphs to exact, case-sensitive column names.

    Word boundaries exclude longer identifiers. A shared column name can refer
    to any table: these are search results, not verified definitions. Retain
    whole paragraphs (including negation) and the source snapshot hash.
    """
    documents = [s for s in draft['sources'] if s['kind'] == 'document']
    out = {}
    for source in draft['sources']:
        if source['kind'] != 'table':
            continue
        columns = {}
        for column in source['headers']:
            pattern = re.compile(r'(?<!\w)' + re.escape(column) + r'(?!\w)')
            matches = []
            for document in documents:
                for paragraph in document['paragraphs']:
                    if pattern.search(paragraph['text']):
                        matches.append({k: paragraph[k] for k in ('paragraph', 'line_start', 'line_end')})
                        matches[-1].update(file=document['name'], sha256=document['sha256'])
            columns[column] = {'matches': matches[:limit], 'total': len(matches),
                               'match_kind': 'literal_column_mention'}
        out[source['name']] = columns
    return out
