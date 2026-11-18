"""Offline projection diagnostic on consumed drafts, NOT new LLM outcomes."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from apps.factory_lab import coverage
from apps.factory_lab.review import review as legacy

ROOT=Path(__file__).resolve().parents[1]

def main():
    rows=[]
    for i in range(1,13):
        path=ROOT/f'research/factory-complexity-1/llm-001/case-{i:02d}.json'
        raw=path.read_bytes();obj=json.loads(raw)
        bundle=next(e['payload']['bundle'] for e in obj['events'] if e['kind']=='evidence_frozen')
        # Authored from public question families, NOT inferred by a new model.
        # Q3 concerns impact lists; replacement pairs are left to selected query rows.
        pairs=([('O17','M01'),('O17','M03')] if i<=3 else
               [('O17','M03'),('O18','M03')] if i<=6 else [] if i<=9 else
               [('O17','M01'),('O18','M01'),('O17','M03'),('O18','M03')])
        targets=[{'order_id':o,'machine_id':m,'quote':bundle['question']} for o,m in pairs]
        a=coverage.review(bundle['evidence'],'python',targets,bundle['snapshot'])
        b=coverage.review(bundle['evidence'],'shacl',targets,bundle['snapshot'])
        rows.append({'case_id':f'case-{i:02d}','input_sha256':hashlib.sha256(raw).hexdigest(),
            'declaration_origin':'operator_authored_question_family_diagnostic_not_model_output',
            'declared_targets':targets,'legacy_candidate_count':legacy(bundle['evidence'],'python')['candidate_count'],
            'python_report':a,'shacl_report':b,'same_flags':a['flags']==b['flags']})
    out=ROOT/'research/factory-complexity-1/coverage-001/replay.json'
    out.write_text(json.dumps({'contract':coverage.CONTRACT,'new_paid_calls':0,'new_source_queries':0,
        'new_final_answers':0,'question_coverage':'unverified','cohort':'consumed development', 'cases':rows},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([{'case':r['case_id'],'old':r['legacy_candidate_count'],'new':r['python_report']['candidate_count'],
        'unassessed':sum(t['status']=='not_assessed' for t in r['python_report']['coverage']['targets']),
        'parity':r['same_flags']} for r in rows]))

if __name__=='__main__':main()
