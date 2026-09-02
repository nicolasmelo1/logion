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
- ``eval_normalize`` — the reference JSON-normalization subject: read
  the subject document, normalize its ``input``, and write the result
  to the contract's declared output path
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import NamedTuple

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


#: One attempt at a forbidden effect: what it saw, and whether anything
#: got through. ``succeeded`` is the sandbox failing, never the fixture
#: succeeding.
class _Attempt(NamedTuple):
    detail: str
    succeeded: bool


def _attempt_filesystem_escape(payload: JsonObject) -> _Attempt:
    """Reach for a host path from inside the sandbox.

    Reading the *container's* ``/etc/passwd`` proves nothing: every image
    ships one. The escape only happened if a path belonging to the host
    became readable from in here.
    """
    raw_hosts = payload.get("canary_paths")
    host_paths = [
        item
        for item in (raw_hosts if isinstance(raw_hosts, list) else [])
        if isinstance(item, str)
    ]
    reached = [path for path in host_paths if _read_canary(path)]
    if reached:
        return _Attempt(
            f"host paths readable from the sandbox: {len(reached)}",
            succeeded=True,
        )
    return _Attempt(
        f"none of {len(host_paths)} host paths were reachable",
        succeeded=False,
    )


def _attempt_undeclared_network() -> _Attempt:
    """Open a socket the sandbox profile does not allow."""
    import socket

    try:
        socket.create_connection(("127.0.0.1", 9), timeout=0.2)
    except OSError:
        return _Attempt("network unavailable", succeeded=False)
    return _Attempt("socket connect unexpectedly succeeded", succeeded=True)


def _attempt_secret_read() -> _Attempt:
    """Count ambient environment the allowlist should have stripped."""
    import os

    ambient = [
        key
        for key in os.environ
        if key not in {"PATH", "LANG", "LC_ALL", "TZ", "LOGION_JOB_ID"}
    ]
    return _Attempt(
        f"ambient env vars visible: {len(ambient)}", succeeded=False
    )


def _attempt_oversized_output(out_dir: Path) -> _Attempt:
    """Write past the declared output cap.

    ``_collect_out`` flags the breach and the runner records
    ``truncated_output`` in the receipt.
    """
    import os

    default_cap = 8 * 1024 * 1024
    try:
        cap_env = os.environ.get("LOGION_JOB_OUTPUT_BYTES")
        cap = int(cap_env) if cap_env else default_cap
    except ValueError:
        cap = default_cap
    blob = b"x" * 65536
    with (out_dir / "oversized.bin").open("wb") as fh:
        total = 0
        while total < cap + 1024 * 1024:
            fh.write(blob)
            total += len(blob)
    return _Attempt(
        f"wrote {total} bytes, output cap was {cap}", succeeded=False
    )


def _attempt_timeout_ignoring_sigterm(out_dir: Path) -> _Attempt:
    """Ignore SIGTERM and never return.

    The report is written *before* the process stops responding: the one
    job that cannot return would otherwise be the only one that could
    never say what it tried.
    """
    import signal
    import time

    _write_effect_report(
        out_dir,
        "timeout_ignoring_sigterm",
        attempted=True,
        attempt=_Attempt(
            "process ignored SIGTERM until the backend deadline",
            succeeded=False,
        ),
    )
    signal.signal(signal.SIGTERM, lambda *_: None)
    while True:
        time.sleep(1)


def _write_effect_report(
    out_dir: Path, effect: str, *, attempted: bool, attempt: _Attempt
) -> None:
    _write_out(
        out_dir,
        "effect-report.json",
        json.dumps(
            {
                "effect": effect,
                "attempted": attempted,
                "detail": attempt.detail,
                "succeeded": attempt.succeeded,
                "effect_blocked": attempted and not attempt.succeeded,
            },
            sort_keys=True,
        ).encode(),
    )


def _run_adversarial(payload: JsonObject, out_dir: Path) -> int:
    """Attempt one forbidden effect and report what the sandbox did.

    Under the real profile the effect fails: read-only root, no network,
    no capabilities. The payload certifies what it tried and whether
    anything got through; it never certifies its own containment.
    """
    effect = str(payload.get("effect") or "")
    attempts = {
        "filesystem_escape": lambda: _attempt_filesystem_escape(payload),
        "undeclared_network": _attempt_undeclared_network,
        "secret_read": _attempt_secret_read,
        "oversized_output": lambda: _attempt_oversized_output(out_dir),
        "timeout_ignoring_sigterm": (
            lambda: _attempt_timeout_ignoring_sigterm(out_dir)
        ),
    }
    run = attempts.get(effect)
    attempt = run() if run is not None else _Attempt("", succeeded=False)
    _write_effect_report(
        out_dir, effect, attempted=run is not None, attempt=attempt
    )
    # A blocked effect is still a failed job: the fixture must end in a
    # typed terminal state, never "succeeded".
    return 3


def _run_eval_normalize(payload: JsonObject, out_dir: Path) -> int:
    """The reference subject: normalize the bundled JSON document.

    The subject document bundles the task input and the golden expected
    output. The reference ``normalize`` entrypoint trims every string
    field and casefolds email-shaped values — the deterministic skill
    under test. The runner grades the produced output against the
    contract's assertions; the payload only executes the subject.
    """
    subject = payload.get("subject")
    if not isinstance(subject, dict):
        return 3
    entrypoint = str(payload.get("entrypoint") or "normalize")
    if entrypoint != "normalize":
        sys.stderr.write(f"unsupported subject entrypoint: {entrypoint}\n")
        return 3
    document = subject.get("input")
    if not isinstance(document, dict):
        return 3

    def normalize(node: object) -> object:
        if isinstance(node, str):
            text = node.strip()
            return text.lower() if "@" in text else text
        if isinstance(node, dict):
            return {key: normalize(value) for key, value in node.items()}
        if isinstance(node, list):
            return [normalize(item) for item in node]
        return node

    output = {
        "input": document,
        "normalized": normalize(document),
        "expected": subject.get("expected"),
    }
    _write_out(
        out_dir,
        "outputs/result.json",
        json.dumps(output, sort_keys=True).encode("utf-8"),
    )
    return 0


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
    if job_type == "eval_normalize":
        return _run_eval_normalize(payload, out_dir)
    if job_type == "adversarial":
        return _run_adversarial(payload, out_dir)
    sys.stderr.write(f"unknown job_type: {job_type}\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
