"""Attach an evidence-only report to an unchanged saved C envelope; no source reader."""
import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
from scripts.graphrag_check import check_evidence, canonical_bytes


def attach_report(envelope, count):
    before=canonical_bytes(envelope)
    report=check_evidence(envelope,max_report_bytes=32000)
    if canonical_bytes(envelope)!=before:raise ValueError('checker mutated input')
    raw=canonical_bytes(report)
    if len(raw)>32000:raise ValueError('report receipt exceeds byte cap')
    if report['evidence_sha256']!=envelope.get('evidence_sha256'):raise ValueError('report evidence mismatch')
    ids=set(envelope.get('selected_chunk_ids',[]))
    if any(not set(r['evidence_ids'])<=ids for r in report['results']):raise ValueError('report cites unselected evidence')
    evidence=canonical_bytes(envelope.get('selected_chunks',[]))
    bundle=canonical_bytes({'selected_chunks':envelope.get('selected_chunks',[]),'report':report})
    counts=[count(x.decode()) for x in (evidence,raw,bundle)]
    if any(type(n) is not int or n<1 for n in counts):raise ValueError('invalid accounting count')
    return dict(question_id=envelope['question_id'],arm='D',evidence=envelope,
                report=report,report_sha256=hashlib.sha256(raw).hexdigest(),report_bytes=len(raw),
                source_evidence_accounting_tokens=counts[0],report_accounting_tokens=counts[1],
                combined_accounting_tokens=counts[2],combined_bytes=len(bundle),
                accounting_tokenizer='pinned-E5-not-generator',generator_tokens=None,
                generation_executed=False,combined_generator_budget_enforced=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    rows=[];summary={'status':'started','planned_questions':24,'new_model_calls':0}
    try:
        m=json.loads(a.manifest.read_text())
        for path,h in m['hashes'].items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=h:raise ValueError('hash mismatch: '+path)
        if importlib.metadata.version('tokenizers')!='0.22.1':raise ValueError('tokenizer runtime mismatch')
        from tokenizers import Tokenizer
        t=Tokenizer.from_file(m['paths']['tokenizer']);t.no_padding();t.no_truncation()
        inputs=[json.loads(x) for x in Path(m['paths']['C']).read_text().splitlines()]
        if [x['question_id'] for x in inputs]!=m['question_ids'] or len(inputs)!=24 or len(set(m['question_ids']))!=24:raise ValueError('question universe mismatch')
        frozen=a.output/'frozen';frozen.mkdir()
        for path in m['hashes']:
            if path!=m['paths']['tokenizer']:shutil.copyfile(path,frozen/Path(path).name)
        shutil.copyfile(a.manifest,a.output/'manifest.json')
        with (a.output/'reports.jsonl').open('w') as f:
            for source in inputs:
                try:row=attach_report(source,lambda text:len(t.encode(text).ids));row['attachment_status']='ok'
                except Exception as exc:row={'question_id':source['question_id'],'arm':'D','evidence':source,'attachment_status':'error','error':str(exc)}
                rows.append(row);f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush()
        for path,h in m['hashes'].items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=h:raise ValueError('input changed')
        good=[r for r in rows if r['attachment_status']=='ok']
        summary.update(status='completed',attachment_ok=len(good),checker_status_counts=dict(Counter(r['report']['status'] for r in good)),check_result_counts=dict(Counter(x['status'] for r in good for x in r['report']['results'])))
    except Exception as exc:summary.update(status='failed',error=str(exc));raise
    finally:
        summary['saved_rows']=len(rows);summary['attachment_failed_or_unexecuted']=24-sum(r['attachment_status']=='ok' for r in rows)
        if summary['status']=='completed' and summary['attachment_failed_or_unexecuted']:summary['status']='partial_failure'
        (a.output/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))

if __name__=='__main__':main()
