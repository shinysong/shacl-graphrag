"""Profile the pinned official Korean public-domain CSV without inferring rules."""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rule_workbench.core import new_project,validate_project

PIN=Path(__file__).resolve().parents[1]/'research/sources/korean-public-domains.json'
HEADERS=['공통표준도메인그룹명','공통표준도메인분류명','공통표준도메인명','공통표준도메인설명','데이터타입','데이터길이','데이터소수점길이','저장형식','표현형식','단위','허용값','제정차수','개정구분명(폐기 또는 변경)','개정항목','개정사유']


def parse_csv(raw):
    reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig'),newline=''))
    if reader.fieldnames!=HEADERS:raise ValueError('Unexpected official CSV headers.')
    rows=list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError('Malformed CSV row width.')
    return rows


def profile(raw):
    pin=json.loads(PIN.read_text())
    if len(raw)!=pin['bytes'] or hashlib.sha256(raw).hexdigest()!=pin['sha256']:
        raise ValueError('Source differs from pinned original CSV.')
    rows=parse_csv(raw)
    if len(rows)!=pin['expected_rows']:raise ValueError('Unexpected row count.')
    names=Counter(r['공통표준도메인명'] for r in rows)
    summary={'source':pin,'rows':len(rows),'columns':HEADERS,
             'types':dict(Counter(r['데이터타입'] for r in rows)),
             'revision_markers':dict(Counter(r['개정구분명(폐기 또는 변경)'] for r in rows)),
             'blank_cells_by_column':{h:sum(r[h]=='' for r in rows) for h in HEADERS},
             'duplicate_domain_names':{k:v for k,v in names.items() if v>1},
             'interpretation':'Raw strings preserved. Blanks are not violations. No length/format/unit constraints inferred; byte-length convention needs explicit policy, not Unicode character count.'}
    project=new_project('Official public-data domain dictionary, 8th revision')
    project['tables'].append({'id':'public-domain-dictionary','name':'공공데이터 공통표준도메인',
                              'columns':HEADERS,'rows':rows,'source':{'kind':'official_dictionary_snapshot',
                              'complete':True,'url':pin['landing_url'],'sha256':pin['sha256'],
                              'scope':'Complete downloaded CSV only, not all current standards'}})
    validate_project(project)
    return summary,project


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    with a.source.open('rb') as f:raw=f.read(100000)
    summary,project=profile(raw)
    a.output.mkdir(parents=True,exist_ok=False)
    for name,obj in [('profile',summary),('project',project)]:
        (a.output/f'{name}.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:summary[k] for k in ['rows','types','revision_markers','duplicate_domain_names']},ensure_ascii=False))
