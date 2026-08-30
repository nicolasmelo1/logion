"""Sandbox backends that execute one job payload in isolation.

Two backends implement the same protocol:

- :class:`LocalTestBackend` — a plain subprocess for development and
  the deterministic test path. It enforces the wall-clock limit and an
  environment allowlist, but it is *not* an isolation boundary and is
  never used for adversarial jobs.
- :class:`DockerBackend` — the sandbox profile v0 execution path: a
  rootless-style container with pinned image digest, read-only root
  filesystem, tmpfs workspace and tmp, all capabilities dropped,
  ``no-new-privileges``, a non-root UID, no network unless the job's
  profile allows it, and memory/PID limits. The job payload enters via
  a tmpfs file; outputs are collected from the workspace ``out`` dir.

The job program receives a payload JSON file (argv[1]) describing the
job and writes artifacts to ``<workspace>/out``. Both backends speak
that contract.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from logion_runner._json import JsonObject
from logion_runner.job import Lease

#: Environment variables a job process may see. Everything else starts
#: empty: ambient credentials do not leak into the sandbox by default.
ENV_ALLOWLIST = frozenset({"PATH", "LANG", "LC_ALL", "TZ", "PYTHON_VERSION"})

SANDBOX_PROFILE_V0 = "isolated-runner-v0"

CANARY_PATHS: tuple[str, ...] = (
    str(Path.home() / ".logion-runner-canary"),
    "/etc/logion-runner-canary",
)

#: Default per-job resource bounds, overridable by the lease limits.
DEFAULT_MEMORY_BYTES = 512 * 1024 * 1024
DEFAULT_PIDS = 128
DEFAULT_OUTPUT_BYTES = 32 * 1024 * 1024


class SandboxUnavailable(RuntimeError):
    """The backend cannot run (e.g. the docker CLI is missing)."""


class SandboxExecutionError(RuntimeError):
    """The payload process itself failed (exec error)."""


@dataclass(frozen=True)
class ExecutionResult:
    """What one sandboxed attempt produced."""

    status: str
    exit_code: int | None
    stdout: str
    stderr: str
    output_files: dict[str, bytes]
    output_digests: dict[str, str]
    truncated_output: bool = False
    denied_effect: dict | None = None


class SandboxBackend(Protocol):
    """Execute one job payload inside a declared isolation level."""

    name: str

    def execute(
        self,
        lease: Lease,
        payload: JsonObject,
        *,
        on_heartbeat: callable | None = None,  # type: ignore[valid-type]
    ) -> ExecutionResult: ...


def _sha256_hex(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _allowlisted_env(extra: dict[str, str] | None) -> dict[str, str]:
    """Build the job env: allowlisted host values plus explicit extras."""
    env: dict[str, str] = {}
    for key in ENV_ALLOWLIST:
        value = os.environ.get(key)
        if value is not None:
            env[key] = value
    if extra:
        for key, value in extra.items():
            if key not in ENV_ALLOWLIST and not key.startswith("LOGION_JOB_"):
                raise ValueError(
                    f"env var {key!r} is not on the job allowlist"
                )
            env[key] = value
    return env


class LocalTestBackend:
    """Run the payload as a local subprocess with soft limits.

    The "runner entry" is ``python -m logion_runner.job_payload``,
    which reads the payload file and performs the job's declared work.
    This backend exists so the lease loop, receipt signing, and CLI are
    testable without a container runtime; it is not an isolation
    boundary and the scenario gates only assert canary outcomes on it.
    """

    name = "local-test"

    #: Marker content the canary probes look for. The payload process
    #: never receives host values: the allowlist already strips them.
    def __init__(
        self,
        *,
        python_executable: str | None = None,
        state_root: Path | None = None,
    ) -> None:
        self._python = python_executable or "python3"
        self._state_root = state_root

    def execute(
        self,
        lease: Lease,
        payload: JsonObject,
        *,
        on_heartbeat=None,  # noqa: ARG002 - parity with DockerBackend
    ) -> ExecutionResult:
        wall = max(1, lease.limits.wall_seconds)
        workspace = Path(tempfile.mkdtemp(prefix="logion-runner-")).resolve()
        try:
            out_dir = Path(workspace) / "out"
            out_dir.mkdir()
            payload_path = Path(workspace) / "job-payload.json"
            payload_path.write_text(json.dumps(payload), encoding="utf-8")
            env = _allowlisted_env({"LOGION_JOB_ID": lease.job_id})
            try:
                proc = subprocess.Popen(
                    [
                        self._python,
                        "-m",
                        "logion_runner.job_payload",
                        str(payload_path),
                    ],
                    cwd=workspace,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            except OSError as exc:
                raise SandboxExecutionError(
                    f"cannot start payload process: {exc}"
                ) from exc
            timed_out = False
            try:
                stdout, stderr = proc.communicate(timeout=wall)
            except subprocess.TimeoutExpired:
                timed_out = True
                proc.send_signal(signal.SIGTERM)
                try:
                    stdout, stderr = proc.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, stderr = proc.communicate()
            output_files, truncated = _collect_out(out_dir, lease)
            if timed_out:
                return ExecutionResult(
                    status="timed_out",
                    exit_code=None,
                    stdout=stdout,
                    stderr=stderr,
                    output_files=output_files,
                    output_digests={
                        name: _sha256_hex(data)
                        for name, data in output_files.items()
                    },
                    truncated_output=truncated,
                )
            status = "succeeded" if proc.returncode == 0 else "failed"
            denied = _denied_effect_from_stderr(stderr)
            return ExecutionResult(
                status=status,
                exit_code=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                output_files=output_files,
                output_digests={
                    name: _sha256_hex(data)
                    for name, data in output_files.items()
                },
                truncated_output=truncated,
                denied_effect=denied,
            )
        finally:
            shutil.rmtree(workspace, ignore_errors=True)


def _denied_effect_from_stderr(stderr: str) -> dict | None:
    """Parse the payload's structured denied-effect marker, if any.

    The sandboxed payload reports a blocked effect by writing one JSON
    line ``{"effect_blocked": true, ...}`` to stderr. The lease loop
    records those fields inside the receipt and the job ends ``failed``.
    """
    for line in stderr.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            parsed = json.loads(stripped)
        except ValueError:
            continue
        if isinstance(parsed, dict) and parsed.get("effect_blocked") is True:
            return {
                "effect_blocked": True,
                "effect_kind": parsed.get("effect_kind"),
                "effect_detail": parsed.get("effect_detail"),
            }
    return None


def _collect_out(out_dir: Path, lease: Lease) -> tuple[dict[str, bytes], bool]:
    """Read every file the job wrote into ``out``, up to the cap."""
    limit = max(1, lease.limits.output_bytes)
    files: dict[str, bytes] = {}
    total = 0
    truncated = False
    for path in sorted(out_dir.rglob("*")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        if total + len(data) > limit:
            truncated = True
            break
        relative = path.relative_to(out_dir).as_posix()
        files[relative] = data
        total += len(data)
    return files, truncated


class DockerBackend:
    """Execute one job inside the sandbox profile v0 container.

    Mapping from the profile to ``docker run`` flags:

    - image pinned by digest        -> ``image@sha256:...``
    - read-only base filesystem     -> ``--read-only``
    - tmpfs workspace and tmp       -> ``--tmpfs /workspace --tmpfs /tmp``
    - dropped capabilities          -> ``--cap-drop ALL``
    - no-new-privileges             -> ``--security-opt no-new-privileges``
    - non-root UID                  -> ``--user 10005:10005``
    - network none unless allowed   -> ``--network none``
    - memory / PID limits           -> ``--memory`` / ``--pids-limit``
    - job payload via tmpfs file    -> payload written into the tmpfs
      workspace before start by the ``sh -c`` wrapper
    """

    name = "docker"

    def __init__(
        self,
        *,
        uid: int = 10005,
        allow_network: bool = False,
        docker_cli: str = "docker",
        payload_entrypoint: str = ("python -m logion_runner.job_payload"),
        image: str | None = None,
    ) -> None:
        self._uid = uid
        self._allow_network = allow_network
        self._docker = docker_cli
        self._entrypoint = payload_entrypoint
        self._image = image

    def available(self) -> bool:
        """True when the docker CLI answers; else the guard fires."""
        if shutil.which(self._docker) is None:
            return False
        probe = subprocess.run(
            [self._docker, "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        return probe.returncode == 0

    def _require_docker(self) -> None:
        if not self.available():
            raise SandboxUnavailable(
                "docker CLI is unavailable; the sandbox profile v0 "
                "backend cannot run. Install Docker Desktop or Podman's "
                "docker shim, or run with the local test backend for "
                "development fixtures only."
            )

    def execute(
        self,
        lease: Lease,
        payload: JsonObject,
        *,
        on_heartbeat=None,  # noqa: ARG002 - heartbeat parity hook
    ) -> ExecutionResult:
        self._require_docker()

        wall = max(1, lease.limits.wall_seconds)
        workspace = Path(
            tempfile.mkdtemp(prefix="logion-runner-docker-")
        ).resolve()
        try:
            out_dir = workspace / "out"
            out_dir.mkdir()
            payload_path = Path(workspace) / "job-payload.json"
            payload_path.write_text(json.dumps(payload), encoding="utf-8")
            image = self._image or _image_for_lease(lease)
            env = _allowlisted_env({"LOGION_JOB_ID": lease.job_id})
            command = self._docker_command(
                lease, image, workspace, payload_path, env, wall
            )
            timed_out = False
            try:
                proc = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            except OSError as exc:
                raise SandboxExecutionError(
                    f"cannot start docker: {exc}"
                ) from exc
            try:
                stdout, stderr = proc.communicate(timeout=wall)
            except subprocess.TimeoutExpired:
                timed_out = True
                proc.send_signal(signal.SIGTERM)
                try:
                    stdout, stderr = proc.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, stderr = proc.communicate()
            output_files, truncated = _collect_out(out_dir, lease)
            if timed_out:
                status = "timed_out"
            else:
                status = "succeeded" if proc.returncode == 0 else "failed"
            denied = _denied_effect_from_stderr(stderr)
            if denied is not None and status == "failed":
                pass
            return ExecutionResult(
                status=status,
                exit_code=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                output_files=output_files,
                output_digests={
                    name: _sha256_hex(data)
                    for name, data in output_files.items()
                },
                truncated_output=truncated,
                denied_effect=denied,
            )
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def _docker_command(
        self,
        lease: Lease,
        image: str,
        workspace: Path,
        payload_path: Path,
        env: dict[str, str],
        wall: int,
    ) -> list[str]:
        flags = [
            "run",
            "--rm",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            f"{self._uid}:{self._uid}",
            "--network",
            "none" if not self._allow_network else "bridge",
            "--memory",
            str(max(lease.limits.memory_bytes, 64 * 1024 * 1024)),
            "--pids-limit",
            str(DEFAULT_PIDS),
            "--tmpfs",
            "/workspace:rw,noexec,nosuid,size=64m",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=16m",  # nosec B108 - container tmpfs
            "-v",
            f"{workspace}/out:/workspace/out:rw",
            "-w",
            "/workspace",
        ]
        for key, value in env.items():
            flags.extend(["-e", f"{key}={value}"])
        # The container root filesystem is read-only; the payload file
        # is materialized into the tmpfs workspace at start so the job
        # never sees a host bind of its own input.
        inner = (
            f"cp /logion/payload.json /workspace/job-payload.json "
            f"&& timeout --signal=TERM {wall} {self._entrypoint} "
            f"/workspace/job-payload.json"
        )
        flags.extend(["-v", f"{payload_path}:/logion/payload.json:ro"])
        flags.extend([image, "sh", "-c", inner])
        return flags


def _image_for_lease(lease: Lease) -> str:
    """Resolve the pinned image reference for *lease*.

    The sandbox profile carried by the coordinator names an image and a
    digest; the runner refuses to run when either is missing so no job
    ever executes on an unpinned image.
    """
    from logion_runner.sandbox.profiles import image_for_profile

    return image_for_profile(
        lease.sandbox_profile, lease.sandbox_profile_digest
    )
