"""The job payload entry point executed inside a sandbox.

Both backends launch ``python -m logion_runner.job_payload <payload>``,
where *payload* is a JSON file written by the backend. The payload
declares the job's work; the runner never passes shell-interpreted
arguments into the sandboxed process.

Supported job types (deterministic fixtures):

- ``echo``       — copy inputs to outputs (acceptance fixture)
- ``canary_probe`` — read canary paths and report what was readable
- ``adversarial``  — attempt a declared forbidden effect; the sandbox
  is expected to block it, and the payload reports the blocked effect
  on stderr as one JSON line for the receipt
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from logion_runner._json import JsonObject


def _read_payload(path_text: str) -> JsonObject:
    payload = json.loads(Path(path_text).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("job payload is not a JSON object")
    return payload


def _write_out(out_dir: Path, name: str, data: bytes) -> None:
    target = (out_dir / name).resolve()
    if not str(target).startswith(str(out_dir.resolve())):
        raise ValueError("output path escapes the out directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def _sha256_hex(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _read_canary(path_text: str) -> bytes | None:
    """Best-effort canary read; returns None when unreadable."""
    try:
        return Path(path_text).read_bytes()
    except OSError:
        return None


def _run_echo(payload: JsonObject, out_dir: Path) -> int:
    inputs = payload.get("inputs") or {}
    if not isinstance(inputs, dict):
        inputs = {}
    for name, value in inputs.items():
        _write_out(out_dir, f"{name}.txt", str(value).encode("utf-8"))
    _write_out(
        out_dir,
        "echo-result.json",
        json.dumps({"echoed": sorted(inputs)}, sort_keys=True).encode(),
    )
    return 0


def _run_canary_probe(payload: JsonObject, out_dir: Path) -> int:
    raw_paths = payload.get("canary_paths") or []
    paths = [
        item
        for item in (raw_paths if isinstance(raw_paths, list) else [])
        if isinstance(item, str)
    ]
    report: dict[str, bool] = {}
    leaked: list[str] = []
    for path in paths:
        content = _read_canary(path)
        report[path] = content is not None
        if content:
            leaked.append(path)
    for path in leaked:
        if content := _read_canary(path):
            _write_out(out_dir, f"leaked-{Path(path).name}", content)
    _write_out(
        out_dir,
        "canary-report.json",
        json.dumps({"readable": report}, sort_keys=True).encode(),
    )
    return 0


def _run_adversarial(payload: JsonObject, out_dir: Path) -> int:
    """Attempt one forbidden effect and report it as blocked.

    Under the real sandbox profile the effect *fails* (read-only root,
    no network, no capabilities). The payload certifies what it tried
    and whether anything got through, on stderr as one JSON line.
    """
    effect = payload.get("effect") or ""
    blocked_kinds = {
        "filesystem_escape",
        "undeclared_network",
        "secret_read",
        "oversized_output",
        "timeout_ignoring_sigterm",
    }
    detail = ""
    succeeded = False
    attempted = effect in blocked_kinds
    if effect == "filesystem_escape":
        try:
            Path("/etc/passwd").read_text()
            detail = "root filesystem was readable"
            succeeded = True
        except OSError:
            detail = "root path unreadable"
    elif effect == "undeclared_network":
        import socket

        try:
            socket.create_connection(("127.0.0.1", 9), timeout=0.2)
            detail = "socket connect unexpectedly succeeded"
            succeeded = True
        except OSError:
            detail = "network unavailable"
    elif effect == "secret_read":
        import os

        ambient = [
            key
            for key in os.environ
            if key not in {"PATH", "LANG", "LC_ALL", "TZ", "LOGION_JOB_ID"}
        ]
        detail = f"ambient env vars visible: {len(ambient)}"
        succeeded = False
    elif effect == "timeout_ignoring_sigterm":
        import signal
        import time

        signal.signal(signal.SIGTERM, lambda *_: None)
        detail = "process ignored SIGTERM until the backend deadline"
        attempted = True
        while True:
            time.sleep(1)
    _write_out(
        out_dir,
        "effect-report.json",
        json.dumps(
            {
                "effect": effect,
                "attempted": attempted,
                "detail": detail,
                "succeeded": succeeded,
                "effect_blocked": attempted and not succeeded,
            },
            sort_keys=True,
        ).encode(),
    )
    # A blocked effect is still a failed job: the fixture must end in a
    # typed terminal state, never "succeeded".
    return 3


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        sys.stderr.write("usage: job_payload <payload.json>\n")
        return 2
    payload = _read_payload(args[0])
    raw_out = payload.get("out_dir")
    out_dir = Path(raw_out if isinstance(raw_out, str) else "./out")
    job_type = payload.get("job_type") or "echo"
    if job_type == "echo":
        return _run_echo(payload, out_dir)
    if job_type == "canary_probe":
        return _run_canary_probe(payload, out_dir)
    if job_type == "adversarial":
        return _run_adversarial(payload, out_dir)
    sys.stderr.write(f"unknown job_type: {job_type}\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
