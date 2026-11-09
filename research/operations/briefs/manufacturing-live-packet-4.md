# _workspace/manufacturing-continuation-20261107/live-control/shacl-manufacturing-stop-20261107.timer
```
[Unit]
Description=Fixed manufacturing database stop at 16:30 UTC
[Timer]
OnCalendar=2026-11-07 16:30:00 UTC
Persistent=true
AccuracySec=1s
Unit=shacl-manufacturing-stop-20261107.service
[Install]
WantedBy=timers.target

```
