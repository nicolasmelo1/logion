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
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from logion_runner._json import JsonObject
from logion_runner.job import Lease

#: Environment variables a job process may see. Everything else starts
#: empty: ambient credentials do not leak into the sandbox by default.
ENV_ALLOWLIST = frozenset({"LANG", "LC_ALL", "TZ", "PYTHON_VERSION"})

SANDBOX_PROFILE_V0 = "isolated-runner-v0"

#: Host paths the ``canary_probe`` job is told to read. Each one holds a
#: real decoy secret planted outside the sandbox, one per canary role the
#: 15.15 contract names, so "not readable" is an observation about the
#: boundary rather than an artefact of never having looked.
CANARY_PATHS: tuple[str, ...] = (
    str(Path.home() / ".logion-runner-canary"),  # host_home
    "/etc/logion-runner-canary",  # etc_shadow
    str(Path.home() / ".logion-runner-canary-etc"),  # etc_shadow, unrooted
    str(Path.home() / ".logion-runner-canary-token"),  # coordinator_token
    str(Path.home() / ".logion-runner-canary-env"),  # canary_env
    str(Path.home() / ".logion-runner-canary-imds"),  # cloud_metadata
    str(Path.home() / ".logion-runner-canary-parent"),  # parent_path
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
        self, lease: Lease, payload: JsonObject, *, on_heartbeat=None
    ) -> ExecutionResult:
        if lease.job_type == "adversarial":
            raise SandboxUnavailable(
                "local-test backend is development-only and cannot execute "
                "adversarial jobs"
            )
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
            stdout, stderr, timed_out, logs_truncated = _communicate_bounded(
                proc, wall, lease.limits.log_bytes, on_heartbeat
            )
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
                    truncated_output=truncated or logs_truncated,
                )
            status = "succeeded" if proc.returncode == 0 else "failed"
            denied = _denied_effect_from_observed_output(output_files)
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
                truncated_output=truncated or logs_truncated,
                denied_effect=denied,
            )
        finally:
            shutil.rmtree(workspace, ignore_errors=True)


def _denied_effect_from_observed_output(
    output_files: dict[str, bytes],
) -> dict | None:
    """Derive denial only from the backend-observed effect report."""
    raw = output_files.get("effect-report.json")
    if raw is None:
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if (
        not isinstance(parsed, dict)
        or parsed.get("effect_blocked") is not True
    ):
        return None
    if parsed.get("succeeded") is True:
        return None
    return {
        "effect_blocked": True,
        "effect_kind": parsed.get("effect"),
        "effect_detail": parsed.get("detail"),
    }


def _communicate_bounded(
    proc: subprocess.Popen[str],
    wall: int,
    log_limit: int,
    on_heartbeat,
) -> tuple[str, str, bool, bool]:
    """Poll a child, heartbeat while it runs, and cap retained logs."""
    deadline = time.monotonic() + max(1, wall)
    log_limit = max(1, log_limit)
    while proc.poll() is None and time.monotonic() < deadline:
        if on_heartbeat is not None:
            on_heartbeat()
        try:
            stdout, stderr = proc.communicate(timeout=0.25)
            return (
                stdout[-log_limit:],
                stderr[-log_limit:],
                False,
                len(stdout) > log_limit or len(stderr) > log_limit,
            )
        except subprocess.TimeoutExpired:
            continue
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
        return (
            stdout[-log_limit:],
            stderr[-log_limit:],
            True,
            len(stdout) > log_limit or len(stderr) > log_limit,
        )
    stdout, stderr = proc.communicate()
    return (
        stdout[-log_limit:],
        stderr[-log_limit:],
        False,
        len(stdout) > log_limit or len(stderr) > log_limit,
    )


def _collect_out(out_dir: Path, lease: Lease) -> tuple[dict[str, bytes], bool]:
    """Read every file the job wrote into ``out``, up to the cap."""
    limit = max(1, lease.limits.output_bytes)
    files: dict[str, bytes] = {}
    total = 0
    truncated = False
    for path in sorted(out_dir.rglob("*")):
        if path.is_symlink():
            raise SandboxExecutionError("symlink in output tree is forbidden")
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

    def _require_pinned_image(self, image: str) -> str:
        """Verify the pinned image is present locally, byte for byte.

        The profile names ``logion-runner-job@sha256:<hex>``. The runtime
        cannot resolve that form for a locally built image, so resolve the
        bare content digest and require the daemon to hold exactly it. A
        missing or mismatched image fails closed: the job never falls back
        to "whatever is tagged nearby".
        """
        from logion_runner.sandbox.profiles import runnable_reference

        runnable = runnable_reference(image)
        probe = subprocess.run(
            [
                self._docker,
                "image",
                "inspect",
                runnable,
                "--format",
                "{{.Id}}",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        if probe.returncode != 0:
            raise SandboxUnavailable(
                f"pinned sandbox image {image} is not present locally; "
                "build it with `make runner-image`, which prints the digest "
                "the coordinator must put in the job's sandbox profile"
            )
        resolved = probe.stdout.strip()
        if resolved != runnable:
            raise SandboxUnavailable(
                f"sandbox image digest mismatch: profile pinned {runnable}, "
                f"the daemon resolved {resolved}"
            )
        return runnable

    def execute(
        self,
        lease: Lease,
        payload: JsonObject,
        *,
        on_heartbeat=None,
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
            runnable = self._require_pinned_image(image)
            env = _allowlisted_env({"LOGION_JOB_ID": lease.job_id})
            command = self._docker_command(
                lease, runnable, workspace, payload_path, env, wall
            )
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
            stdout, stderr, timed_out, logs_truncated = _communicate_bounded(
                proc, wall, lease.limits.log_bytes, on_heartbeat
            )
            output_files, truncated = _collect_out(out_dir, lease)
            if timed_out:
                status = "timed_out"
            else:
                status = "succeeded" if proc.returncode == 0 else "failed"
            denied = _denied_effect_from_observed_output(output_files)
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
                truncated_output=truncated or logs_truncated,
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
            self._docker,
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
            # The job runs as a non-root UID, so the tmpfs workspace it
            # writes into (including the job payload copy) must be owned
            # by that same UID.
            f"/workspace:rw,noexec,nosuid,size=64m,uid={self._uid}",
            "--tmpfs",
            f"/tmp:rw,noexec,nosuid,size=16m,uid={self._uid}",
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
        flags.extend(["--entrypoint", "sh", image, "-c", inner])
        return flags


def _image_for_lease(lease: Lease) -> str:
    """Resolve the pinned image reference for *lease*.

    The sandbox profile carried by the coordinator names an image and a
    digest; the runner refuses to run when either is missing so no job
    ever executes on an unpinned image.
    """
    from logion_runner.sandbox.profiles import image_for_profile

    return image_for_profile(lease.sandbox_profile)
