# _workspace/manufacturing-continuation-20261107/live-control/shacl-manufacturing-stop-20261107.service
```
[Unit]
Description=Stop owned manufacturing study graph databases
[Service]
Type=oneshot
WorkingDirectory=/home/ubuntu/shacl-graphrag
ExecStart=/home/ubuntu/.local/bin/uv run --offline --with boto3 python /home/ubuntu/shacl-graphrag/_workspace/manufacturing-continuation-20261107/live-control/power.py stop
Restart=on-failure
RestartSec=60
TimeoutStartSec=180

```
