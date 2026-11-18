"""Save both lexical-selection arms before any separate evaluator scoring."""
import argparse
import hashlib
import json
from pathlib import Path
from experiments.factory_complexity.tools import Views, RDFStudyTools, SQLStudyTools
from experiments.query_contracts.competing import CompetingTools
from experiments.query_contracts.selection import run_request


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--requests',required=True); p.add_argument('--catalog',required=True)
    p.add_argument('--views',required=True); p.add_argument('--output',required=True)
    args = p.parse_args(); output = Path(args.output)
    if output.exists(): raise ValueError('Output already exists')
    requests = json.loads(Path(args.requests).read_text())
    catalog = json.loads(Path(args.catalog).read_text())['catalog']
    slots = [{'request_id':r['id'],'arm':arm,'backend':backend,'status':'unattempted'}
             for r in requests for arm in ('top1','typed_top3') for backend in ('sqlite','rdflib')]
    record = {'scope':'authored development selector diagnostic; not LLM or answer evaluation',
        'new_paid_calls':0,'calls_per_slot_cap':12,'same_catalog_and_rankings':True,
        'inputs_sha256':{f:hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in (args.requests,args.catalog)},
        'slots':slots}
    output.parent.mkdir(parents=True,exist_ok=True)
    def save():
        temp=output.with_suffix('.tmp'); temp.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');temp.replace(output)
    save()
    sql = None
    try:
        try:
            views = Views(args.views); sql = SQLStudyTools(views); rdf = RDFStudyTools(views)
            record['setup_status'] = 'completed'
        except Exception as exc:
            record['setup_status'] = 'failed'; record['setup_error'] = str(exc)
            save()
            raise
        by_id={r['id']:r for r in requests}
        for slot in slots:
            try:
                backend=sql if slot['backend']=='sqlite' else rdf
                slot['result']=run_request(by_id[slot['request_id']],catalog,CompetingTools(backend),slot['arm']=='typed_top3')
                slot['status']='recorded'
            except Exception as exc:
                slot['status']='failed';slot['error']=str(exc)
            save()
    finally:
        if sql is not None: sql.close()
        save()

if __name__=='__main__': main()
