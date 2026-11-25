"""Optional local upstream CLI boundary; receipts never grant workspace approval.

The executable is operator-configured, never selected by imported content.
Only fixed load/reason/save commands are exposed, not arbitrary batch commands.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import signal
import tempfile
import time

MAX_OUTPUT_BYTES = 16 * 1024 * 1024
# The CLI initializes a SQLite state database even with an in-memory graph.
# This per-file process ceiling is independent of returned evidence size. It is
# not a total disk quota; deployment isolation must provide that if required.
PROCESS_FILE_BYTES = 16 * 1024 * 1024


def _read_evidence(path, limit):
    """Read at most limit bytes, retaining a prefix and explicit truncation facts."""
    if not path.is_file():
        return None
    with path.open("rb") as stream:
        size = os.fstat(stream.fileno()).st_size
        raw = stream.read(limit)
    return raw, {"file_bytes": size, "retained_bytes": len(raw),
                 "truncated": size > len(raw),
                 "limit_reached": size >= limit,
                 "sha256_scope": "retained_prefix" if size > len(raw) else "whole_file"}


def reason_snapshot(binary, asserted_turtle, *, profile="rdfs", timeout=60, max_output_bytes=MAX_OUTPUT_BYTES, cancel_requested=None):
    """Return raw upstream evidence, including failures, for a bounded snapshot.

    This boundary is not a network/process sandbox. The caller must configure a
    trusted binary and enforce deployment isolation. No imports are fetched here.
    """
    if profile not in {"rdfs", "owl-rl"}:
        raise ValueError("Unsupported reasoning profile")
    if not isinstance(asserted_turtle, bytes) or len(asserted_turtle) > 1_000_000:
        raise ValueError("Expected at most 1 MB of Turtle bytes")
    if type(timeout) is not int or not 1 <= timeout <= 120:
        raise ValueError("Timeout must be 1..120 seconds")
    if type(max_output_bytes) is not int or not 1024 <= max_output_bytes <= MAX_OUTPUT_BYTES:
        raise ValueError("Output limit must be 1024..16777216 bytes")
    executable = Path(binary).resolve(strict=True)
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ValueError("Configured upstream binary is not executable")
    receipt = {
        "format": "open-ontologies-receipt-1", "provider": "open-ontologies",
        "binary_sha256": sha256(executable.read_bytes()).hexdigest(),
        "input_sha256": sha256(asserted_turtle).hexdigest(),
        "input_bytes": len(asserted_turtle), "profile": profile,
        "approval": "not_granted", "policy": "advisory",
        "scope": "supplied snapshot only", "status": "running",
        "asserted_turtle": asserted_turtle.decode("utf-8", "strict"),
        "limits": {"address_space_bytes": 2 * 1024**3, "file_bytes": PROCESS_FILE_BYTES,
                   "returned_file_bytes": max_output_bytes, "total_disk_quota": "not_enforced",
                   "wall_seconds": timeout},
        "certificate_verification": "not_run",
    }
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="factory-oo-") as folder:
        root = Path(folder)
        source, closure = root / "asserted.ttl", root / "closure.ttl"
        source.write_bytes(asserted_turtle)
        batch = json.dumps([
            {"command": "load", "args": [str(source)]},
            {"command": "reason", "args": ["--profile", profile, "--track-derivations", "--certificate", str(root / "certificate")]},
            {"command": "save", "args": [str(closure)]},
        ])
        # Do not inherit provider keys, daemon settings or a shared HOME config.
        env = {"PATH": os.defpath, "HOME": folder, "LANG": "C.UTF-8",
               "OPEN_ONTOLOGIES_STORAGE_MODE": "memory"}
        try:
            # Linux deployment boundary: hard per-file and address-space limits.
            # Files avoid unbounded PIPE accumulation. This does not block networking.
            with (root / "stdout").open("wb") as out, (root / "stderr").open("wb") as err:
                if cancel_requested is not None and cancel_requested():
                    receipt.update(status="cancelled", process_started=False)
                else:
                    # Own one process group, with file-backed stdin/output so no
                    # pipe write can block cancellation. Always reap our child.
                    (root / "batch.json").write_bytes(batch.encode())
                    with (root / "batch.json").open("rb") as commands:
                        process = subprocess.Popen(
                            ["/usr/bin/prlimit", "--as=2147483648", f"--fsize={PROCESS_FILE_BYTES}",
                             f"--cpu={timeout + 5}", "--", str(executable), "--no-connect",
                             "--data-dir", str(root / "state"), "batch", "-", "--bail"],
                            stdin=commands, stdout=out, stderr=err, env=env,
                            cwd=folder, start_new_session=True)
                        receipt['process_started'] = True
                        receipt['termination'] = {'cause': None, 'signal_sent': False, 'signal': None}
                        try:
                            while process.poll() is None:
                                if cancel_requested is not None and cancel_requested():
                                    receipt['termination']['cause'] = 'cancel_requested'
                                    break
                                if time.monotonic() - started >= timeout:
                                    receipt['termination']['cause'] = 'timeout'
                                    break
                                time.sleep(0.05)
                        finally:
                            # Trusted executable must not leave descendants after exiting.
                            # This boundary reaps its direct child, not a system cgroup.
                            # SIGKILL is bounded even for an uncooperative native
                            # child. Signal only the group this invocation created.
                            if process.poll() is None:
                                try:
                                    os.killpg(process.pid, signal.SIGKILL)
                                    receipt['termination'].update(signal_sent=True, signal=int(signal.SIGKILL))
                                except ProcessLookupError:
                                    pass
                            process.wait()
                            receipt['process_reaped'] = True
                            receipt['exit_code'] = process.returncode
                        receipt['exit_code'] = process.returncode
                        if receipt['status'] == 'running':
                            termination = receipt['termination']
                            if termination['signal_sent'] and process.returncode == -signal.SIGKILL:
                                receipt['status'] = {'cancel_requested': 'cancelled', 'timeout': 'timed_out'}.get(termination['cause'], 'failed')
                            else:
                                receipt['status'] = 'failed'  # natural exit: parse its actual result below
        except OSError:
            receipt.update(status="failed", error="Local reasoning process could not start")
        except Exception as exc:
            receipt.update(status="failed", error="Local reasoning execution failed (" + type(exc).__name__ + ")")
        receipt["output_files"] = {}
        for name in ("stdout", "stderr"):
            evidence = _read_evidence(root / name, max_output_bytes)
            raw, metadata = evidence if evidence is not None else (b"", None)
            receipt[name] = raw.decode("utf-8", "replace")
            if metadata is not None:
                receipt["output_files"][name] = metadata
        receipt["events"] = []
        receipt["reasoning_complete"] = None
        if "exit_code" in receipt and receipt["status"] not in ("cancelled", "timed_out") and "error" not in receipt:
            try:
                if receipt["output_files"].get("stdout", {}).get("limit_reached"):
                    raise ValueError("Cannot parse incomplete or limit-sized event stream")
                events = [json.loads(line) for line in receipt["stdout"].splitlines() if line.strip()]
                valid = (len(events) == 3 and
                         [e.get("command") for e in events] == ["load", "reason", "save"] and
                         all(isinstance(e.get("result"), dict) and "error" not in e["result"] for e in events))
            except (ValueError, AttributeError, TypeError, RecursionError):
                events, valid = [], False
            receipt["events"] = events
            receipt["status"] = "completed" if receipt["exit_code"] == 0 and valid and closure.is_file() else "failed"
            receipt["reasoning_complete"] = events[1]["result"].get("fixpoint_reached") if valid else None
            if receipt["status"] == "completed" and receipt["reasoning_complete"] is not True:
                receipt["status"] = "partial"
        # Failed and timed-out upstream runs can already have written evidence.
        # Retain it before temporary cleanup without promoting partial output.
        receipt["artifact_completeness"] = "complete" if receipt["status"] == "completed" else "unverified_partial"
        evidence = _read_evidence(closure, max_output_bytes)
        if evidence is not None:
            output, metadata = evidence
            receipt["output_files"]["closure.ttl"] = metadata
            receipt.update(closure_turtle=output.decode("utf-8", "replace"),
                           closure_sha256=sha256(output).hexdigest())
        receipt["derivation_artifacts"] = {}
        for name in ("asserted.tsv", "asserted.sha256", "scope.tsv", "derivations.tsv", "refutation.tsv"):
            path = root / "certificate" / name
            evidence = _read_evidence(path, max_output_bytes)
            if evidence is not None:
                raw, metadata = evidence
                receipt["output_files"]["certificate/" + name] = metadata
                receipt["derivation_artifacts"][name] = {
                    "sha256": sha256(raw).hexdigest(), "text": raw.decode("utf-8", "replace")}
        receipt["output_limit_reached"] = any(
            metadata["limit_reached"] for metadata in receipt["output_files"].values())
        if receipt["output_limit_reached"]:
            if receipt["status"] not in ("timed_out", "cancelled"):
                receipt["status"] = "failed"
            receipt["artifact_completeness"] = "unverified_partial"
        receipt["elapsed_seconds"] = time.monotonic() - started
    return receipt
