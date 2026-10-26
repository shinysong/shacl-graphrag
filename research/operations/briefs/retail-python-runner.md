# Bounded Python artifact execution

Review scripts/retail_python_runner.py. Uses already verified staged stdlib runtime
and prior saved Docker argv (trusted local coordinator artifact), same cached image,
nonroot/networknone/readonly/capdrop/no-new-privileges/256MiB/32PIDs/1CPU/16MiBtmp.
Only copied runtime and new per-call task files mounted. No host workspace,
credentials, scorer or Docker socket. No new image/software/service.

Generated source eventually defines evaluate(packet), but this tick executes only
four fixed authored checks: success, exception, infinite loop, stdout flood.
Artifact limit65536bytes; packet1MiB; stdout+stderr capture65536bytes; wall10secs.
Selector drains both pipes, kills CLI on limit then forcibly removes unique owned
container. Save execution/output before cleanup; inspect absence, stop checks if
cleanup unresolved. Captured output is prefix onlimit and explicitly failure.
No repaired source/output; nonzeroexit preserved, no reference access.

Independent static methods/implementation review before main runs
`UV_OFFLINE=true uv run --locked --group workbench python -m scripts.retail_python_runner`.
Preserve unexpected failures, no automatic rerun. Report exact outcomes and
cleanup; configured memory/PID/CPU flags are not stress tested. Current runtime
stdlib only, no pySHACL or general sandbox security guarantee. No API/heldout/push.
