# _workspace/manufacturing-continuation-20261107/live-control/check_power.py
```
import importlib.util,json,tempfile
from pathlib import Path
from unittest.mock import MagicMock,patch
from botocore.exceptions import ClientError
spec=importlib.util.spec_from_file_location('control',Path(__file__).with_name('power.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
checks=[]
with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
 m.ROOT=Path(tmp)
 for mode in ['start_guard_failure','wrong_account','stop_accepted','already_stopped','other_stop_fault']:
  session=MagicMock();sts=MagicMock();client=MagicMock()
  sts.get_caller_identity.return_value={'Account':'bad' if mode=='wrong_account' else m.ACCOUNT}
  session.client.side_effect=lambda name,**kw:sts if name=='sts' else client
  client.stop_db_cluster.return_value={'DBCluster':{'Status':'stopping'},'ResponseMetadata':{'RequestId':'mock'}}
  if mode in ('already_stopped','other_stop_fault'):
   message=f'DbCluster {m.CLUSTER} is in stopped state but expected it to be one of available.' if mode=='already_stopped' else 'not permitted'
   client.stop_db_cluster.side_effect=ClientError({'Error':{'Code':'InvalidDBClusterStateFault','Message':message}},'StopDBCluster')
  info=json.dumps([{'Config':{'Labels':{'research-owner':'neptune-gui-20261106'}}}]).encode()
  with patch.object(m.boto3,'Session',return_value=session),patch.object(m.subprocess,'check_output',return_value=info),patch.object(m.subprocess,'run') as run:
   if mode=='start_guard_failure':run.side_effect=RuntimeError('inactive timer')
   failed=False
   try:m.main('start' if mode=='start_guard_failure' else 'stop')
   except Exception:failed=True
   assert failed==(mode in ('start_guard_failure','wrong_account','other_stop_fault'))
   if mode in ('start_guard_failure','wrong_account'):assert not client.start_db_cluster.called and not client.stop_db_cluster.called
   checks.append({'case':mode,'passed':True})
Path(__file__).with_name('mock-checks.json').write_text(json.dumps(checks,indent=2)+'\n')

```
