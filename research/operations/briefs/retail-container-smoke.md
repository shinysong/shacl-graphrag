# Existing-container Python smoke

Current authorized next step is generated-code comparison, but no model-generated
code may execute yet. Review scripts/retail_container_smoke.py. This bounded
offline step stages only public installed Python3.12 runtime/library bytes into
ignored workspace, then mounts only that staged directory readonly into one
temporary container on the existing local Docker daemon. Cached image80259ba83f86
was inventoried earlier as ruby3.4-bookworm. --pull=never: no image download,
build, package installation, new service, infrastructure provisioning or API call.

Run only fixed authored PROBE, not supplied/generated code. Nonroot65534,
networknone, readonlyroot, capdropALL, no-new-privileges,256MiBmem,32pids,1CPU,
16MiBtemporary storage. Hostworkspace/socket/secrets are not mounted or forwarded.
The bind source contains copied runtime only, not inputs, references or credentials.
Host childenv restricted PATH/LANG. Unique owned container cleanup in finally.
30s execution timeout and10s cleanup. stdout/stderr capture is not output-bounded:
acceptable for this fixed small authored probe only, not a general runner.

After independent reviews main executes with uv offline workbench. Preserve any
runtime/dependency failure rather than installing more software or retrying.
Record actualdecimalexecution and probes: rootwrite refusal, no hostMEMORY path,
noDocker socket, noexperimentsecret env, blocked externalconnect andtmpwrite.
These are narrow observed checks, not proof of complete sandbox security.
Resource flags are configured, not stress-tested. No pySHACL support or generated
code compatibility claim. A future runner requires separate resource/output-limit
and adversarial review. No heldout reads, modelcalls, push or schedule changes.
