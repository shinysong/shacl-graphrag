# Startup and terminal cleanup
Cachedimage f1e52d4dc6da122468c4a3c1050a4f5e117f6d3268625237c34d49166f0d6082 andjar509bec192befce6224a7e3bf78a0e6b74aeb8bf61eb7a1e009b7b62e0737900b. Ownedcontainer shacl-n10s-subtype-20261107,owner subtype-20261107,localhost7475/7688,2CPU2GB,512MBheap256MBcache. ExistingGUIuntouched. Coordinatorverifiesinstalledguarddeadline/ExecStart/limits/hashbeforelaunch. Powerstartonlyexcerpt below; CONFIG5–30sectimeouts,ACCOUNT985658740608,REGIONSeoul,CLUSTERsameasfinish. STARTguardactive required; final receipts written in finally. Actualstopusesfinish.py,notoldpowerstop.

```python
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

```
## Launcher
```python
"""Plan before startup; fixed readiness cutoff; independent terminal cleanup."""
import datetime as dt,json,time
from pathlib import Path
import live,power,transport,finish
ROOT=Path(__file__).parent
CONFIG=Path('research/manufacturing-model-change-1/subtype-offline-001/config.json')
OUT=Path('research/manufacturing-model-change-1/subtype-live-001')
def preserve_remaining(out,error):
 plan=json.loads((out/'plan.json').read_text());rows=[json.loads(l) for l in (out/'rows.jsonl').read_text().splitlines()] if (out/'rows.jsonl').exists() else []
 identity=lambda r:(r['source_index'],r['kind'],r['target'],r['arm']);done={identity(r) for r in rows}
 with (out/'rows.jsonl').open('a') as f:
  for q in plan:
   if identity(q) not in done:r={**q,'status':'infrastructure_not_run','error':error,'values':[]};f.write(json.dumps(r)+'\n');rows.append(r)
 (out/'launcher-failure.json').write_text(json.dumps({'error':error,'planned':len(plan),'emitted':len(rows),'statuses':{s:sum(r['status']==s for r in rows) for s in {r['status'] for r in rows}}},indent=2)+'\n')
def main():
 live.prepare(CONFIG,OUT) # durable denominator precedes every cloud/local start
 try:
  now=dt.datetime.now(dt.timezone.utc)
  if not dt.datetime.fromisoformat('2026-11-07T17:05:00+00:00')<=now<dt.datetime.fromisoformat('2026-11-07T17:15:00+00:00'):raise RuntimeError('outside_start_window')
  power.main('start');store=transport.NeptuneStore('backend-subtype-readiness-20261107');neo=live.Neo('backend-subtype-readiness-20261107');receipts=[]
  while dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat('2026-11-07T17:25:00+00:00'):
   r={'at':dt.datetime.now(dt.timezone.utc).isoformat()}
   try:r['neptune_ready']=store.request('ASK {}').get('boolean') is True
   except Exception as e:r['neptune_ready']=False;r['neptune_error']=type(e).__name__+': '+str(e)
   try:r['neo4j_ready']=neo.request('RETURN 1 AS ready')==[{'ready':1}]
   except Exception as e:r['neo4j_ready']=False;r['neo4j_error']=type(e).__name__+': '+str(e)
   receipts.append(r);(ROOT/'readiness.json').write_text(json.dumps(receipts,indent=2)+'\n');print(json.dumps(r),flush=True)
   if r['neptune_ready'] and r['neo4j_ready']:break
   time.sleep(20)
  else:raise RuntimeError('readiness_deadline')
  capability={'at':dt.datetime.now(dt.timezone.utc).isoformat(),'components':neo.request('CALL dbms.components() YIELD name,versions RETURN name,versions'),'procedures':neo.request("SHOW PROCEDURES YIELD name WHERE name='n10s.inference.nodesInCategory' RETURN name")}
  (ROOT/'capability.json').write_text(json.dumps(capability,indent=2)+'\n');print(live.run(CONFIG,OUT,prepared=True),flush=True)
 except Exception as e:
  preserve_remaining(OUT,type(e).__name__+': '+str(e));raise
 finally:finish.finish()
if __name__=='__main__':main()

```
## Terminal cleanup
```python
"""Independent stop attempts; terminal AWS status and owned removal receipts."""
import datetime as dt,json,time,subprocess
from pathlib import Path
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
ROOT=Path(__file__).parent;CLUSTER='shacl-graphrag-research';CONTAINER='shacl-n10s-subtype-20261107';OWNER='subtype-20261107'
TARGET=dt.datetime.fromisoformat('2026-11-07T18:00:00+00:00')
def local_remove():
 r=subprocess.run(['docker','inspect',CONTAINER],capture_output=True,text=True,timeout=10)
 if r.returncode:
  if 'No such object: '+CONTAINER in r.stderr:return {'status':'already_absent'}
  raise RuntimeError('docker_inspect_failed:'+r.stderr)
 info=json.loads(r.stdout)[0]
 if info['Config']['Labels'].get('research-owner')!=OWNER:raise RuntimeError('owner_mismatch')
 subprocess.run(['docker','stop','--time','20',CONTAINER],check=True,capture_output=True,text=True,timeout=30)
 subprocess.run(['docker','rm','-v',CONTAINER],check=True,capture_output=True,text=True,timeout=30)
 r=subprocess.run(['docker','inspect',CONTAINER],capture_output=True,text=True,timeout=10)
 if r.returncode==0 or 'No such object: '+CONTAINER not in r.stderr:raise RuntimeError('removal_not_verified')
 return {'status':'removed_verified','anonymous_volume_removal_requested':True}
def stop_once():
 cfg=Config(connect_timeout=5,read_timeout=15,retries={'max_attempts':0});s=boto3.Session(region_name='ap-northeast-2')
 if s.client('sts',config=cfg).get_caller_identity()['Account']!='985658740608':raise RuntimeError('wrong_account')
 try:
  r=s.client('neptune',config=cfg).stop_db_cluster(DBClusterIdentifier=CLUSTER)
  return {'status':r['DBCluster']['Status'],'request_id':r['ResponseMetadata']['RequestId'],'terminal':r['DBCluster']['Status']=='stopped'}
 except ClientError as e:
  if e.response['Error'].get('Code')=='InvalidDBClusterStateFault' and f'DbCluster {CLUSTER} is in stopped state' in e.response['Error'].get('Message',''):return {'status':'stopped_confirmed_by_api_error','terminal':True}
  raise
def finish(max_seconds=600,poll_seconds=30):
 started=dt.datetime.now(dt.timezone.utc);end=min(TARGET,started+dt.timedelta(seconds=max_seconds));receipt={'started':started.isoformat(),'terminal_target':TARGET.isoformat(),'attempts':[]};terminal=False;local_ok=False
 # Local cleanup is independent of AWS credentials/network/service state.
 try:receipt['local']=local_remove();local_ok=True
 except Exception as e:receipt['local']={'status':'unresolved','error':type(e).__name__+': '+str(e)}
 path=ROOT/('finish-'+started.strftime('%Y%m%dT%H%M%S%fZ')+'.json')
 while dt.datetime.now(dt.timezone.utc)<end:
  try:r=stop_once();terminal=r['terminal']
  except Exception as e:r={'status':'unresolved','terminal':False,'error':type(e).__name__+': '+str(e)}
  receipt['attempts'].append({'at':dt.datetime.now(dt.timezone.utc).isoformat(),**r});receipt.update(terminal_stopped=terminal,local_cleanup_verified=local_ok);path.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt['attempts'][-1]),flush=True)
  if terminal:break
  time.sleep(min(poll_seconds,max(0,(end-dt.datetime.now(dt.timezone.utc)).total_seconds())))
 receipt.update(terminal_stopped=terminal,local_cleanup_verified=local_ok,finished=dt.datetime.now(dt.timezone.utc).isoformat(),status='completed' if terminal and local_ok else 'unresolved');path.write_text(json.dumps(receipt,indent=2)+'\n')
 if not terminal or not local_ok:raise RuntimeError('resource_cleanup_unresolved:'+str(path))
 return receipt
if __name__=='__main__':finish()

```
## Guard
[Unit]
Description=Stop owned published hierarchy study graph databases
[Service]
Type=oneshot
WorkingDirectory=/home/ubuntu/shacl-graphrag
ExecStart=/home/ubuntu/.local/bin/uv run --offline --with boto3 python /home/ubuntu/shacl-graphrag/_workspace/manufacturing-continuation-20261107/subtype-live/finish.py
Restart=on-failure
RestartSec=60
TimeoutStartSec=700

[Unit]
Description=Fixed manufacturing database stop at 17:35 UTC
[Timer]
OnCalendar=2026-11-07 17:35:00 UTC
Persistent=true
AccuracySec=1s
Unit=shacl-subtype-stop-20261107.service
[Install]
WantedBy=timers.target

Controlsplannednotrun, bodiesomittedunverified: all992slotmock path/materializationchecks; sourcefail992notrun;cleanupfail496remainingnotrun;loadfailure868depfailed124unsupported;6previouspowerchecks;newpending→stopped,timeoutunresolved,owner-mismatchnostop,localfailurestillAWS;start/readiness/capabilityfailures992infrastructurenotrun each. Input/resultsourcefidelity andactualresources omitted. Registeredchecks empty. Hardkills/diskfailures mayleavepartialrows, planretained. No engineclaimsfrommocks.
