# Resource controls v2
Previous job synthesis exceeded context limit; originalreviews preserved. No runtime changes. New explicitforegroundlauncher andtimerdescriptioncorrection. ExistingAWSaccount985658740608 Seoul clusteronly;ownedtemporaryn10s container shacl-n10s-subtype-20261107 labelresearch-owner=subtype-20261107,loopback7475/7688,2CPU2GB,512MBheap256MBcache,cachedimagef1e52d4dc6da122468c4a3c1050a4f5e117f6d3268625237c34d49166f0d6082 andcachedn10sjarSHA509bec192befce6224a7e3bf78a0e6b74aeb8bf61eb7a1e009b7b62e0737900b. No newAWSresources/downloads/paidcalls. Beforelaunch verifyinstalleddeadline/ExecStart/activeguard/containerlimits; freezehashes. Stopby18:00UTC, startnotbefore17:05. TerminalAWSstopnotmerelystopping;removeownedtemporarycontainer+volumes,keepGUIuntouched. LocalguarddependsEC2.

Controlsplanned, bodiesomittedunverified: sixpower mocks guard/wrongaccount/stop/alreadystopped/APIerror/localstoperror; RDFLibmock992slots868completed124unsupported; sourcefailure992notrun; cleanupfailure434completed62unsupported496notrun; loadfailure868dependentfailed124unsupported. No liveeffects inchecks. Sourcehierarchyhelper omittedpreviouslyreviewed; currentreviewdoesnotindependentlyverifyit.

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
## Foregroundlauncher
```python
"""Foreground launcher: fixed readiness deadline and unconditional stop attempt."""
import datetime as dt,json,time
from pathlib import Path
import live,power,transport
root=Path(__file__).parent
try:
 if dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat('2026-11-07T17:05:00+00:00'):raise RuntimeError('before_frozen_start')
 power.main('start');store=transport.NeptuneStore('backend-subtype-readiness-20261107');neo=live.Neo('backend-subtype-readiness-20261107');receipts=[]
 while dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat('2026-11-07T17:45:00+00:00'):
  r={'at':dt.datetime.now(dt.timezone.utc).isoformat()}
  try:r['neptune_ready']=store.request('ASK {}').get('boolean') is True
  except Exception as e:r['neptune_ready']=False;r['neptune_error']=type(e).__name__+': '+str(e)
  try:r['neo4j_ready']=neo.request('RETURN 1 AS ready')==[{'ready':1}]
  except Exception as e:r['neo4j_ready']=False;r['neo4j_error']=type(e).__name__+': '+str(e)
  receipts.append(r);(root/'readiness.json').write_text(json.dumps(receipts,indent=2)+'\n');print(json.dumps(r),flush=True)
  if r['neptune_ready'] and r['neo4j_ready']:break
  time.sleep(20)
 else:raise RuntimeError('readiness_deadline')
 capability={'at':dt.datetime.now(dt.timezone.utc).isoformat(),'components':neo.request('CALL dbms.components() YIELD name,versions RETURN name,versions'),'procedures':neo.request("SHOW PROCEDURES YIELD name WHERE name='n10s.inference.nodesInCategory' RETURN name")}
 (root/'capability.json').write_text(json.dumps(capability,indent=2)+'\n')
 print(live.run('research/manufacturing-model-change-1/subtype-offline-001/config.json','research/manufacturing-model-change-1/subtype-live-001'),flush=True)
finally:
 power.main('stop')

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
Description=Fixed manufacturing database stop at 18:00 UTC
[Timer]
OnCalendar=2026-11-07 18:00:00 UTC
Persistent=true
AccuracySec=1s
Unit=shacl-subtype-stop-20261107.service
[Install]
WantedBy=timers.target
