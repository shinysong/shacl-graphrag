"""Source-only field-aligned search projection; never reads questions or references."""
import hashlib
import json
import re


def value(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def project(corpus, count, limit=512):
    if type(limit) is not int or not 1 <= limit <= 512:
        raise ValueError('invalid limit')
    children = []
    seen = set()
    for chunk in corpus['chunks']:
        parent = chunk['chunk_id']
        if parent in seen:
            raise ValueError('duplicate parent')
        seen.add(parent)
        data = json.loads(chunk['text'])
        if chunk['chunk_type'] == 'node':
            context = f"record={data['id']}; workbook={data['coupon']}; sheet={data['sheet']}; Excel row={data['excel_row']}"
            headers = {}
            for row in data['header_rows']:
                for cell in row['cells']:
                    col = re.fullmatch(r'([A-Z]+)[0-9]+', cell['cell']).group(1)
                    if cell['value'] is not None:
                        headers.setdefault(col, []).append(str(cell['value']))
            fields = []
            for cell in data['cells']:
                col = re.fullmatch(r'([A-Z]+)[0-9]+', cell['cell']).group(1)
                label = ' / '.join(headers.get(col, [col]))
                fields.append(f"{label} [{cell['cell']}] = {value(cell['value'])}")
                if cell.get('formula') is not None:
                    fields.append(f"formula [{cell['cell']}] = {value(cell['formula'])}; cached_value={value(cell.get('cached_value'))}")
            for field, target in sorted(data.get('dictionary_refs', {}).items()):
                fields.append(f"{field} reference = {target}")
        elif chunk['chunk_type'] == 'edge':
            p = data['provenance']
            context = f"relation; workbook={p['coupon']}; sheet={p['sheet']}; cell={p['cell']}"
            fields = [f"subject = {data['subject']}", f"field = {data['field']}",
                      f"relation_type = {data['relation_type']}", f"code = {value(data['code'])}",
                      f"target = {data['target']}", f"target_sheet = {p['target_sheet']}",
                      f"target_Excel_row = {p['target_excel_row']}"]
        else:
            raise ValueError('unknown chunk type')
        prefix = f'passage: {context}\n'
        groups, pending = [], []
        for line in fields:
            if count(prefix + line) > limit:
                raise ValueError(f'atomic field overflow: {parent}')
            if pending and count(prefix + '\n'.join(pending + [line])) > limit:
                groups.append(pending)
                pending = []
            pending.append(line)
        if pending:
            groups.append(pending)
        if not groups:
            raise ValueError('empty projection')
        for ordinal, group in enumerate(groups):
            text = prefix + '\n'.join(group)
            children.append({'child_id': f'v1:{len(parent)}:{parent}:{ordinal}',
                             'parent_id': parent, 'ordinal': ordinal,
                             'parent_sha256': hashlib.sha256(chunk['text'].encode()).hexdigest(),
                             'chunk_type': chunk['chunk_type'], 'search_text': text,
                             'token_count': count(text), 'field_lines': group})
    return children
