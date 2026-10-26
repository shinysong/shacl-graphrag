"""Construct isolated development submissions; never execute or score an arm."""
import difflib
import hashlib
import json
import shutil
import sys
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
FROZEN=ROOT/'_workspace/technology-selection/maintenance-1/frozen'
ARMS=('python_indexed','sqlite_recursive','rdf_owl_shacl')


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def replace(root,path,old,new):
    p=root/path;s=p.read_text()
    if s.count(old)!=1:raise ValueError('ambiguous edit '+path)
    p.write_text(s.replace(old,new))


def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((FROZEN/'manifest.json').read_text());submissions=[]
    for path,h in manifest['baseline'].items():
        if sha(FROZEN/'baseline'/path)!=h:raise ValueError('baseline changed')
    for task in ('M1','M2','M3','M4','M5'):
        for arm in ARMS:
            name=task+'-'+arm;dest=out/name;shutil.copytree(FROZEN/'baseline',dest)
            common='scripts/technology_selection_common.py'
            if task=='M1':
                if arm=='python_indexed':
                    replace(dest,'research/technology-selection/python-rules-v1.json','start_lte_received_lt_end','start_lte_received_lte_end')
                    replace(dest,'scripts/technology_selection_python.py',"rule == 'start_lte_received_lt_end':\n                ok = v[0] <= v[1] < v[2]","rule == 'start_lte_received_lte_end':\n                ok = v[0] <= v[1] <= v[2]")
                elif arm=='sqlite_recursive':replace(dest,'research/technology-selection/receipt-query-v1.sql','a<=b AND b<c','a<=b AND b<=c')
                else:replace(dest,'research/technology-selection/receipt-shapes-v1.ttl','sh:path ex:b; sh:lessThan ex:c','sh:path ex:b; sh:lessThanOrEquals ex:c')
            elif task=='M2':
                replace(dest,'scripts/industrial_question_python.py',"    required = product.get('requires_current_certificate')","    required = product.get('requires_current_certificate')\n    if product.get('category') == 'service_spare':\n        required = False")
            elif task=='M3':
                replace(dest,common,"    adjacency, complete, excluded = base.graph(t, p['coverage'])",'''    dated_tables = deepcopy(t)
    as_of = base.day(q.get('as_of'))
    for edge in dated_tables['component_edge']:
        start, end = base.day(edge.get('valid_from')), base.day(edge.get('valid_to'))
        if not start or not end or start >= end or not as_of:
            edge['active'] = None  # malformed evidence remains excluded/incomplete
        elif type(edge.get('active')) is bool and not (start <= as_of < end):
            edge['active'] = False
    adjacency, complete, excluded = base.graph(dated_tables, p['coverage'])''')
            elif task=='M4':
                if arm=='python_indexed':
                    config=dest/'research/technology-selection/python-rules-v1.json';r=json.loads(config.read_text());r['quantity_cap']=8;config.write_text(json.dumps(r,indent=2)+'\n')
                    replace(dest,'scripts/technology_selection_python.py','ok = 0 < v[0] <= v[1]',"ok = 0 < v[0] <= min(v[1], self.rules['quantity_cap'])")
                elif arm=='sqlite_recursive':replace(dest,'research/technology-selection/receipt-query-v1.sql','a>0 AND a<=b','a>0 AND a<=b AND a<=8')
                else:replace(dest,'research/technology-selection/receipt-shapes-v1.ttl','sh:minExclusive 0;','sh:minExclusive 0; sh:maxInclusive 8;')
            elif task=='M5':
                replace(dest,common,"    return dict(scene_id=p['scene_id'], receipt_id=p['tables']['receipt'][0]['id'],",'''    evaluated = [dict(rule_id=c['rule_id'], support=c['support'], policy_version='v2',
                      result='unknown' if c['values'] is None else 'violation' if c['rule_id'] in failed else 'pass')
                 for c in sorted(checks, key=lambda c: c['rule_id'])]
    return dict(evaluated_checks=evaluated, scene_id=p['scene_id'], receipt_id=p['tables']['receipt'][0]['id'],''')
            changed=[];diff=[]
            for path,h in manifest['baseline'].items():
                p=dest/path
                if sha(p)==h:continue
                before=(FROZEN/'baseline'/path).read_text().splitlines();after=p.read_text().splitlines()
                lines=list(difflib.unified_diff(before,after,fromfile='baseline/'+path,tofile=name+'/'+path,lineterm=''))
                added=sum(bool(s[1:].strip()) for s in lines if s.startswith('+') and not s.startswith('+++'))
                deleted=sum(bool(s[1:].strip()) for s in lines if s.startswith('-') and not s.startswith('---'))
                changed.append(dict(path=path,kind='code' if path.endswith('.py') else 'config',added_nonblank=added,deleted_nonblank=deleted,sha256=sha(p)))
                diff.extend(lines)
            patch=out/(name+'.patch');patch.write_text('\n'.join(diff)+'\n')
            submissions.append(dict(id=name,task=task,arm=arm,attempt=1,root=str(dest),changed=changed,patch_sha256=sha(patch),
                source_hashes={path:sha(dest/path) for path in manifest['baseline']},
                shared_change=task in ('M2','M3','M5'),
                shared_location={'M2':'industrial_question_python.recheck','M3':'technology_selection_common.normalize','M5':'technology_selection_common.assemble'}.get(task)))
    result=dict(created_at=datetime.now(timezone.utc).isoformat(),baseline_manifest_sha256=sha(FROZEN/'manifest.json'),submissions=submissions,
        interpretation='Single coordinator authored in fixed M1..M5 and Python/SQL/RDF order; not independent developers or human maintenance labor. Shared identical helper patches deduplicate by task/path/hash.',
        tests='Shared acceptance harness separate from implementation diffs; added test code reported separately, not charged three times.')
    (out/'submissions.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Prepared15isolated submissions;0arm executions')


if __name__=='__main__':main()
