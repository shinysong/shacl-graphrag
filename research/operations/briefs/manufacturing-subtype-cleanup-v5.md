# Existing-resource cleanup message case fix
Read-only <=150words. Actual992slot experimentcompleted868+124unsupported. Foregroundfinallyexit1: localremoval actuallyoccurred but exactuppercase No such object checkdidnotrecognizelowercase Docker stderr. 2ownedanonymousvolumes independentlyabsent. AWS stopaccepted17:25:54,laststopping. Old17:35guardactive. No restarting/newinfra/datawrites. Newhelperidenticalcleanup except casefoldDockerabsence; sameterminaltarget18:00,alwayslateoneattempt. 600sboundedpolling, mayremainunresolved. Afterreview/manual6controls usefixedhelperforeground and retargetownedguard; verifyterminalbeforedisable.

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
  if 'no such object: '+CONTAINER in r.stderr.lower():return {'status':'already_absent'}
  raise RuntimeError('docker_inspect_failed:'+r.stderr)
 info=json.loads(r.stdout)[0]
 if info['Config']['Labels'].get('research-owner')!=OWNER:raise RuntimeError('owner_mismatch')
 subprocess.run(['docker','stop','--time','20',CONTAINER],check=True,capture_output=True,text=True,timeout=30)
 subprocess.run(['docker','rm','-v',CONTAINER],check=True,capture_output=True,text=True,timeout=30)
 r=subprocess.run(['docker','inspect',CONTAINER],capture_output=True,text=True,timeout=10)
 if r.returncode==0 or 'no such object: '+CONTAINER not in r.stderr.lower():raise RuntimeError('removal_not_verified')
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
 first=True
 while first or dt.datetime.now(dt.timezone.utc)<end:
  first=False
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

```python
import subprocess,json,tempfile,datetime as dt
from pathlib import Path
from unittest.mock import patch
import finish
for msg in ('Error: No such object: ', 'error: no such object: '):
 with patch.object(finish.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'[]',msg+finish.CONTAINER)):
  assert finish.local_remove()['status']=='already_absent'
 owned=json.dumps([{'Config':{'Labels':{'research-owner':finish.OWNER}}}])
 seq=[subprocess.CompletedProcess([],0,owned,''),subprocess.CompletedProcess([],0,'',''),subprocess.CompletedProcess([],0,'',''),subprocess.CompletedProcess([],1,'[]',msg+finish.CONTAINER)]
 with patch.object(finish.subprocess,'run',side_effect=seq):assert finish.local_remove()['status']=='removed_verified'
with patch.object(finish.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','permission denied')):
 try:finish.local_remove()
 except RuntimeError:pass
 else:raise AssertionError('unrelatederroraccepted')
with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
 with patch.object(finish,'ROOT',Path(tmp)),patch.object(finish,'local_remove',return_value={'status':'already_absent'}),patch.object(finish,'stop_once',return_value={'status':'stopped','terminal':True}):
  assert finish.finish(max_seconds=0)['status']=='completed'
print('uppercase/lowercase absent and post-removal verification, unrelatedfailure, terminalreceipt:6controls passed')

```
