# Resource control and offline checks

Create one owned temporary cached Neo4j5.26.32/n10s5.26.0 container, owner subtype-20261107, localhost7475/7688,2CPU2GB,512MBheap256MBpagecache. ExistingGUIcontainer untouched. Cached image and jar only, no new download. Name shacl-n10s-subtype-20261107. Fixed stopguard18:00UTC installed/active before startingAWS/container. Existing AWSaccount985658740608 Seoul shacl-graphrag-research only. Max55min livewindow, cumulative billedcost not independently available; no newAWSresources. foregroundfinally stop, later explicitterminalstopreceipt and remove ownedtemporarycontainer+volumes. Localtimer dependsEC2availability. Stop independently attemptsAWSandlocal evenifAWSfailure; retry60sec. Source/runtimefrozenhashesbeforelaunch. Allchecks below plannednotrun.

```python
"""Existing owned resources only; fixed short window and explicit receipts."""
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

ROOT=Path(__file__).resolve().parent
DEADLINE=dt.datetime.fromisoformat('2026-11-07T18:00:00+00:00')
CLUSTER='shacl-graphrag-research'
REGION='ap-northeast-2'
ACCOUNT='985658740608'
CONTAINER='shacl-n10s-subtype-20261107'
TIMER='shacl-subtype-stop-20261107.timer'
CONFIG=Config(connect_timeout=10,read_timeout=30,retries={'max_attempts':1})


def main(action):
    stamp=dt.datetime.now(dt.timezone.utc)
    receipt={'at':stamp.isoformat(),'action':action,'deadline':DEADLINE.isoformat(),'cluster':CLUSTER,'region':REGION}
    try:
        if action not in ('start','stop'):raise ValueError('unsupported_action')
        if action=='start':
            session=boto3.Session(region_name=REGION)
            if session.client('sts',config=CONFIG).get_caller_identity()['Account']!=ACCOUNT:raise RuntimeError('wrong_account')
            client=session.client('neptune',config=CONFIG)
            if stamp >= DEADLINE-dt.timedelta(minutes=10):raise RuntimeError('too_late_to_start')
            subprocess.run(['systemctl','--user','is-active','--quiet',TIMER],check=True,timeout=10)
            info=json.loads(subprocess.check_output(['docker','inspect',CONTAINER],timeout=10))[0]
            if info['Config']['Labels'].get('research-owner')!='subtype-20261107':raise RuntimeError('container_owner_mismatch')
            result=client.start_db_cluster(DBClusterIdentifier=CLUSTER)
            receipt['neptune_status']=result['DBCluster']['Status']
            receipt['request_id']=result['ResponseMetadata']['RequestId']
            subprocess.run(['docker','start',CONTAINER],check=True,timeout=30)
            receipt['neo4j_started']=True
        else:
            errors=[]
            try:
                session=boto3.Session(region_name=REGION)
                if session.client('sts',config=CONFIG).get_caller_identity()['Account']!=ACCOUNT:raise RuntimeError('wrong_account')
                client=session.client('neptune',config=CONFIG)
                try:
                    result=client.stop_db_cluster(DBClusterIdentifier=CLUSTER)
                    receipt['neptune_status']=result['DBCluster']['Status']
                    receipt['request_id']=result['ResponseMetadata']['RequestId']
                except ClientError as exc:
                    message=exc.response['Error'].get('Message','')
                    if exc.response['Error'].get('Code')=='InvalidDBClusterStateFault' and f'DbCluster {CLUSTER} is in stopped state' in message:
                        receipt['neptune_status']='stopped_confirmed_by_api_error'
                    else:raise
            except Exception as exc:
                receipt['neptune_stop_error']=type(exc).__name__+':'+str(exc);errors.append('neptune')
            # Local stop is attempted even when AWS credentials/network/API fail.
            try:
                info=json.loads(subprocess.check_output(['docker','inspect',CONTAINER],timeout=10))[0]
                if info['Config']['Labels'].get('research-owner')!='subtype-20261107':raise RuntimeError('container_owner_mismatch')
                subprocess.run(['docker','stop','--time','20',CONTAINER],check=True,timeout=30)
                receipt['neo4j_stopped']=True
            except Exception as exc:
                receipt['neo4j_stop_error']=type(exc).__name__+':'+str(exc);errors.append('neo4j')
            if errors:raise RuntimeError('unresolved_stop:'+','.join(errors))
        receipt['accepted']=True
    except Exception as exc:
        receipt.update(accepted=False,error_type=type(exc).__name__,error=str(exc))
        raise
    finally:
        path=ROOT/(action+'-'+stamp.strftime('%Y%m%dT%H%M%S%fZ')+'.json')
        path.write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps(receipt),flush=True)

if __name__=='__main__':main(sys.argv[1])

```
## Power controls
```python
import importlib.util,json,tempfile
from pathlib import Path
from unittest.mock import MagicMock,patch
from botocore.exceptions import ClientError
spec=importlib.util.spec_from_file_location('control',Path(__file__).with_name('power.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class FixedDateTime(m.dt.datetime):
 @classmethod
 def now(cls,tz=None):return cls.fromisoformat('2026-11-07T17:05:00+00:00')
m.dt.datetime=FixedDateTime
checks=[]
with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
 m.ROOT=Path(tmp)
 for mode in ['start_guard_failure','wrong_account','stop_accepted','already_stopped','other_stop_fault','local_stop_failure']:
  session=MagicMock();sts=MagicMock();client=MagicMock()
  sts.get_caller_identity.return_value={'Account':'bad' if mode=='wrong_account' else m.ACCOUNT}
  session.client.side_effect=lambda name,**kw:sts if name=='sts' else client
  client.stop_db_cluster.return_value={'DBCluster':{'Status':'stopping'},'ResponseMetadata':{'RequestId':'mock'}}
  if mode in ('already_stopped','other_stop_fault'):
   message=f'DbCluster {m.CLUSTER} is in stopped state but expected it to be one of available.' if mode=='already_stopped' else 'not permitted'
   client.stop_db_cluster.side_effect=ClientError({'Error':{'Code':'InvalidDBClusterStateFault','Message':message}},'StopDBCluster')
  info=json.dumps([{'Config':{'Labels':{'research-owner':'subtype-20261107'}}}]).encode()
  with patch.object(m.boto3,'Session',return_value=session),patch.object(m.subprocess,'check_output',return_value=info),patch.object(m.subprocess,'run') as run:
   if mode=='start_guard_failure':run.side_effect=RuntimeError('inactive timer')
   if mode=='local_stop_failure':run.side_effect=RuntimeError('docker failure')
   failed=False
   try:m.main('start' if mode=='start_guard_failure' else 'stop')
   except Exception:failed=True
   assert failed==(mode in ('start_guard_failure','wrong_account','other_stop_fault','local_stop_failure'))
   if mode in ('start_guard_failure','wrong_account'):assert not client.start_db_cluster.called and not client.stop_db_cluster.called
   if mode in ('wrong_account','other_stop_fault'):assert any(call.args[0][:2]==['docker','stop'] for call in run.call_args_list)
   checks.append({'case':mode,'passed':True})
Path(__file__).with_name('mock-checks.json').write_text(json.dumps(checks,indent=2)+'\n')

```
## Live controls
```python
import json,tempfile
from pathlib import Path
from unittest.mock import patch
from rdflib import Dataset
from rdflib.util import from_n3
import live
CFG=Path('research/manufacturing-model-change-1/subtype-offline-001/config.json')
class FakeNeo:
 def __init__(self,namespace):self.owned=False
 def load(self,p):self.p=p;self.owned=True
 def query(self,q,n10s=False):return live.h.outputs(self.p,'python_transitive')[q['kind'],q['target']]
 def cleanup(self):return {'remaining':0}
class FakeNeptune:
 def __init__(self,namespace):self.owned=False;self.graph='<urn:test:'+namespace+'>';self.ds=Dataset()
 def load(self,triples):
  self.owned=True;g=self.ds.graph(from_n3(self.graph))
  for t in triples:g.add(tuple(from_n3(x) for x in t))
 def request(self,q):return json.loads(self.ds.query(q).serialize(format='json'))
 def cleanup(self):return {'remaining':False}
results=[]
with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
 tmp=Path(tmp)
 with patch.object(live,'Neo',FakeNeo),patch.object(live.t,'NeptuneStore',FakeNeptune):
  a=live.run(CFG,tmp/'good');assert a['statuses']=={'completed':868,'unsupported_selected_adapter':124};results.append(a)
  rs=[json.loads(l) for l in (tmp/'good/rows.jsonl').read_text().splitlines()];groups={}
  for r in rs:
   if r['status']=='completed':groups.setdefault((r['source_index'],r['kind'],r['target']),[]).append(r['values'])
  assert len(groups)==248 and all(all(v==vs[0] for v in vs) for vs in groups.values())
  cfg=json.loads(CFG.read_text());cfg['sources'][0]['projection_sha256']='0'*64;(tmp/'bad.json').write_text(json.dumps(cfg));b=live.run(tmp/'bad.json',tmp/'bad');assert b['statuses']=={'not_run_after_failure':992};results.append(b)
 class CleanupFailure(FakeNeo):
  def cleanup(self):raise RuntimeError('test_cleanup_failure')
 with patch.object(live,'Neo',CleanupFailure),patch.object(live.t,'NeptuneStore',FakeNeptune):
  c=live.run(CFG,tmp/'cleanup');assert c['statuses']=={'completed':434,'not_run_after_failure':496,'unsupported_selected_adapter':62};assert c['fatal'];results.append(c)
 class LoadFailure(FakeNeo):
  def load(self,p):self.owned=True;raise RuntimeError('test_load_failure')
 with patch.object(live,'Neo',LoadFailure),patch.object(live.t,'NeptuneStore',FakeNeptune):
  d=live.run(CFG,tmp/'load');assert d['statuses']=={'load_dependency_failed':868,'unsupported_selected_adapter':124};results.append(d)
Path(__file__).with_name('mock-live-results.json').write_text(json.dumps(results,indent=2)+'\n')
print('RDFLib path/materialization, mock orchestration, source failure, cleanup abort and load failure controls pass; no live DB tested')

```
[Unit]
Description=Stop owned published hierarchy study graph databases
[Service]
Type=oneshot
WorkingDirectory=/home/ubuntu/shacl-graphrag
ExecStart=/home/ubuntu/.local/bin/uv run --offline --with boto3 python /home/ubuntu/shacl-graphrag/_workspace/manufacturing-continuation-20261107/subtype-live/power.py stop
Restart=on-failure
RestartSec=60
TimeoutStartSec=180

[Unit]
Description=Fixed manufacturing database stop at 16:30 UTC
[Timer]
OnCalendar=2026-11-07 18:00:00 UTC
Persistent=true
AccuracySec=1s
Unit=shacl-subtype-stop-20261107.service
[Install]
WantedBy=timers.target
