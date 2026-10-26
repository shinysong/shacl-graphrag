"""Exact official term lookup; preserves all linked domain candidates."""
import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path
from .domain_candidates import find_domain_candidates

PIN = Path(__file__).resolve().parents[1] / 'research/sources/korean-public-terms.json'
HEADERS = ['공통표준용어명','공통표준용어설명','공통표준용어영문약어명','공통표준도메인명','허용값','저장 형식','표현 형식','행정표준코드명','소관기관명','용어 이음동의어 목록','제정차수','개정구분명(폐기 또는 변경)','개정항목','개정사유']


def find_term_candidates(raw_terms, raw_domains, requests):
    """Requests contain column_id and exact term_name. No synonym expansion."""
    if not isinstance(requests, list) or len(requests)>100:
        raise ValueError('Supply at most 100 requests.')
    seen=set()
    for r in requests:
        if (not isinstance(r,dict) or set(r)!={'column_id','term_name'}
                or any(not isinstance(v,str) or not v.strip() or len(v)>1000 for v in r.values())):
            raise ValueError('Supply nonblank column_id and term_name, at most 1000 characters each.')
        if r['column_id'] in seen:raise ValueError('Duplicate column_id.')
        seen.add(r['column_id'])
    pin=json.loads(PIN.read_text())
    if not isinstance(raw_terms,bytes) or len(raw_terms)!=pin['bytes'] or hashlib.sha256(raw_terms).hexdigest()!=pin['sha256']:
        raise ValueError('Terms differ from pinned original.')
    reader=csv.DictReader(io.StringIO(raw_terms.decode('utf-8-sig'),newline=''))
    if reader.fieldnames!=HEADERS:raise ValueError('Unexpected term headers.')
    rows=list(reader)
    if len(rows)!=pin['expected_rows'] or any(None in r or any(v is None for v in r.values()) for r in rows):
        raise ValueError('Unexpected term rows.')
    names={r['term_name'] for r in requests}
    selected=[(i,row) for i,row in enumerate(rows,1) if row['공통표준용어명'] in names]
    # One domain lookup per selected term row, with no type-based pruning.
    domains=find_domain_candidates(raw_domains,[{'column_id':str(i),'domain_name':r['공통표준도메인명']} for i,r in selected])
    domain_map={r['request']['column_id']:r for r in domains['results']}
    results=[]
    for request in requests:
        candidates=[{'snapshot_row_id':f"{pin['sha256']}:{i}",'source_record':i,
                     'official_fields':dict(row),'domain_lookup':domain_map[str(i)]}
                    for i,row in selected if row['공통표준용어명']==request['term_name']]
        results.append({'request':dict(request),'approval_status':'unreviewed',
                        'status':'not_found_in_snapshot' if not candidates else 'ambiguous_name' if len(candidates)>1 else 'single_candidate',
                        'candidates':candidates})
    return {'schema_version':1,'term_sha256':pin['sha256'],'domain_sha256':domains['source_sha256'],
            'counts':dict(Counter(r['status'] for r in results)),'results':results,
            'scope':'Exact supplied term names only. Original revision and synonym fields retained, not interpreted. Single term can link to multiple domains. No approval, generated rules or semantic column mapping.'}
