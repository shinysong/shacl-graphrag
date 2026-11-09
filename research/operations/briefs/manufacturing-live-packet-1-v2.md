# power.py
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
DEADLINE=dt.datetime.fromisoformat('2026-11-07T16:30:00+00:00')
CLUSTER='shacl-graphrag-research'
REGION='ap-northeast-2'
ACCOUNT='985658740608'
CONTAINER='shacl-neo4j-browser-20261106'
TIMER='shacl-manufacturing-stop-20261107.timer'
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
            if info['Config']['Labels'].get('research-owner')!='neptune-gui-20261106':raise RuntimeError('container_owner_mismatch')
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
                if info['Config']['Labels'].get('research-owner')!='neptune-gui-20261106':raise RuntimeError('container_owner_mismatch')
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
