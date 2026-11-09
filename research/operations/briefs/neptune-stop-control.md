Scope: configure EC2-local Neptune shutdown, not research efficacy. User granted existing role start/stop for ONLY cluster shacl-graphrag-research in ap-northeast-2 account985658740608. No automatic starts or new cloud resources. Current fixed authorization deadline2026-11-06T10:10:52Z. Power script stop saves accepted/error receipts; run wraps foreground command with timeout and finally stop. User systemd persistent deadline timer retries stop failure every120s; requires EC2/user-manager alive. EC2 outage is explicitly not covered. Stop response is accepted/stopping, not verified stopped, because DescribeDBClusters permission denied; do not claim IAM tested before actual stop. Future windows require new authorization, not automatic extension. Planned checks: offline mocked success/failure/timeout/expired wrapper and systemd-analyze verify; install only after reviews. No paid API calls, no publication. Review supplied files only.

Revision: client initialization is inside receipt try/finally. Wrapper covers foreground direct child, not SIGKILL/EC2 outage; deadline timer is separate. Already-stopped state may produce retry logs because management describe is unavailable; no starts occur.

FILE power_control.py
"""Owned Neptune stop control; does not start resources or extend authorization."""
import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import boto3
from botocore.config import Config

ROOT = Path(__file__).resolve().parent
CLUSTER = 'shacl-graphrag-research'
REGION = 'ap-northeast-2'
DEADLINE = dt.datetime.fromisoformat('2026-11-06T10:10:52+00:00')

def stop():
    stamp = dt.datetime.now(dt.timezone.utc)
    receipt = {'at': stamp.isoformat(), 'cluster': CLUSTER, 'region': REGION, 'action': 'stop'}
    try:
        client = boto3.client('neptune', region_name=REGION, config=Config(connect_timeout=10, read_timeout=30, retries={'max_attempts': 2}))
        result = client.stop_db_cluster(DBClusterIdentifier=CLUSTER)
        receipt.update(status=result['DBCluster']['Status'], request_id=result['ResponseMetadata']['RequestId'], accepted=True)
    except Exception as exc:
        receipt.update(accepted=False, error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        path = ROOT / ('power-stop-' + stamp.strftime('%Y%m%dT%H%M%S%fZ') + '.json')
        path.write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt), flush=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['stop', 'run'])
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.action == 'stop':
        stop()
        return
    command = args.command
    if command and command[0] == '--':
        command = command[1:]
    remaining = (DEADLINE - dt.datetime.now(dt.timezone.utc)).total_seconds()
    if not command or remaining <= 0:
        parser.error('A command and an unexpired authorized window are required; no automatic start.')
    try:
        result = subprocess.run(command, timeout=remaining, check=False)
    finally:
        stop()
    raise SystemExit(result.returncode)

if __name__ == '__main__':
    main()

FILE neptune-stop.service
[Unit]
Description=Stop owned research Neptune cluster
StartLimitIntervalSec=0
[Service]
Type=oneshot
WorkingDirectory=/home/ubuntu/shacl-graphrag
ExecStart=/home/ubuntu/.local/bin/uv run --offline --with boto3 python /home/ubuntu/shacl-graphrag/_workspace/neptune-setup-20261106/power_control.py stop
Restart=on-failure
RestartSec=120
TimeoutStartSec=120

FILE neptune-stop.timer
[Unit]
Description=Authorized Neptune window deadline (UTC)
[Timer]
OnCalendar=2026-11-06 10:10:52 UTC
Persistent=true
Unit=shacl-neptune-stop-20261106.service
[Install]
WantedBy=timers.target
