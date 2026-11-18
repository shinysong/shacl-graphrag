"""Freeze real adapter messages offline, before any gateway call or response.

The capture callback always raises before model response processing. It does not
simulate a valid model answer. This command contains no provider client.
"""
import argparse
import hashlib
import json
from pathlib import Path
from apps.factory_lab import preparation
from apps.factory_lab.preparation_model import ModelProposalGenerator


class Captured(Exception):
    pass


def freeze(source_path, output):
    source_path=Path(source_path)
    raw=source_path.read_bytes()
    cases=json.loads(raw)['cases']
    ids=[c['id'] for c in cases]
    if len(ids)!=len(set(ids)) or any(not isinstance(i,str) or not i.isascii()
            or not i.replace('_','').isalnum() for i in ids):
        raise ValueError('Unique ASCII case IDs required')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    (output/'input.json').write_bytes(raw)
    records=[]
    for case in cases:
        record={'id':case['id'],'state':'not_started'}
        def capture(messages):
            encoded=json.dumps(messages,ensure_ascii=False).encode()
            (output/(case['id']+'-messages.json')).write_bytes(encoded)
            record.update(state='captured_before_response',message_bytes=len(encoded),
                          messages_sha256=hashlib.sha256(encoded).hexdigest())
            raise Captured()
        try:
            preparation.create(case['files'],{'snapshot_id':case['id'],
                'as_of':'2026-11-17','currency':'KRW'},
                generator=ModelProposalGenerator(capture,'offline-capture'))
        except Captured:
            pass
        except Exception as exc:
            record.update(state='capture_failed',error_type=type(exc).__name__,error=str(exc))
        else:
            raise RuntimeError('Capture must stop before response processing')
        records.append(record)
        # Retain each completed capture even if a later case fails.
        (output/'records.json').write_text(json.dumps(records,indent=2))
    files=['apps/factory_lab/preparation_model.py','apps/factory_lab/preparation.py',
           'apps/factory_lab/preparation_advisory.py','apps/factory_lab/preparation_sources.py',
           'apps/factory_lab/preparation_evidence.py','scripts/workspace_proposal_packets.py','uv.lock']
    report={'scope':'Offline exact message capture only; zero provider calls or generated answers',
            'input_sha256':hashlib.sha256(raw).hexdigest(),'attempted_cases':len(cases),
            'records':records,'implementation_sha256':{f:hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in files},
            'paid_execution_ready':False,
            'remaining':['Pin model/provider/prices and output token limit',
                         'Freeze durable nonrefunded attempt/cost ledger and bounded authorization',
                         'Review actual paid runner before calls',
                         'Keep rubric outside runtime; score all attempts including failures']}
    (output/'manifest.json').write_text(json.dumps(report,indent=2))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources');parser.add_argument('output')
    args=parser.parse_args()
    print(json.dumps(freeze(args.sources,args.output),indent=2))
