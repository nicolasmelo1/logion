"""Runner orchestrator: wires config, key store, client, and backend.

This is the object the CLI subcommands drive. It owns the lifecycle:
enroll (create identity + credentials), doctor (self-check), run
(one iteration or a polling loop), jobs (local history), and
rotate-key.
"""

from __future__ import annotations

import json
import platform
from dataclasses import dataclass

from logion_runner._json import JsonObject
from logion_runner.config import RunnerConfig, job_history_path
from logion_runner.coordinator_client import (
    CoordinatorClient,
)
from logion_runner.key_store import (
    EnrollSecrets,
    KeyStore,
    KeyStoreError,
    load_enroll_secrets,
)
from logion_runner.lease_loop import (
    JsonlStateStore,
    LoopError,
    run_loop,
    run_one_iteration,
)
from logion_runner.sandbox.backends import (
    DockerBackend,
    LocalTestBackend,
    SandboxUnavailable,
)


class RunnerNotEnrolled(KeyStoreError):
    """No local runner credentials; run ``enroll`` first."""


@dataclass(frozen=True)
class DoctorCheck:
    """One named self-check result for ``doctor``."""

    name: str
    ok: bool
    detail: str


@dataclass
class RunnerNode:
    """The runner process state rooted at a state directory."""

    config: RunnerConfig
    backend_name: str = "local-test"

    def __post_init__(self) -> None:
        self.store = KeyStore(self.config.state_dir)

    # ── construction helpers ────────────────────────────────────

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> RunnerNode:
        return cls(config=RunnerConfig.from_env(env))

    def client(self) -> CoordinatorClient:
        return CoordinatorClient(self.config.base_url)

    def _require_secrets(self) -> EnrollSecrets:
        if not self.store.exists():
            raise RunnerNotEnrolled(
                f"no runner credential at {self.store.path}; "
                "run `logion-node enroll` first"
            )
        return self.store.load_secrets()

    def _backend(self):
        if self.backend_name == "docker":
            return DockerBackend()
        return LocalTestBackend()

    # ── enroll / rotate ─────────────────────────────────────────

    def enroll(self, name: str, capabilities: list[str]) -> JsonObject:
        """Enroll with the coordinator and persist the credentials."""
        client = self.client()
        try:
            response = client.enroll(name or _default_name(), capabilities)
        finally:
            client.close()
        secrets = load_enroll_secrets(response)
        self.store.save(secrets)
        return {
            "runner_id": secrets.runner_id,
            "key_fingerprint": secrets.key_fingerprint,
            "signing_key_fingerprint": secrets.signing_key_fingerprint,
            "state_dir": str(self.config.state_dir),
        }

    def rotate_key(self, capabilities: list[str]) -> JsonObject:
        """Rotate the runner key via the coordinator, persist it."""
        secrets = self._require_secrets()
        client = self.client()
        try:
            response = client.rotate_key(
                secrets.runner_key, secrets.runner_id, capabilities
            )
        finally:
            client.close()
        new_secrets = load_enroll_secrets(response)
        self.store.save(new_secrets)
        return {
            "runner_id": new_secrets.runner_id,
            "key_fingerprint": new_secrets.key_fingerprint,
            "rotated": True,
        }

    # ── doctor ──────────────────────────────────────────────────

    def doctor(self) -> list[DoctorCheck]:
        """Self-check: state dir, keys, coordinator, docker."""
        checks: list[DoctorCheck] = []
        state_dir = self.config.state_dir
        state_ok = state_dir.is_dir()
        if state_ok:
            import stat as stat_mod

            state_ok = not (stat_mod.S_IMODE(state_dir.stat().st_mode) & 0o077)
        checks.append(
            DoctorCheck(
                "state_dir",
                state_ok,
                str(state_dir),
            )
        )
        checks.append(
            DoctorCheck(
                "credentials",
                self.store.exists(),
                str(self.store.path),
            )
        )
        if self.store.exists():
            try:
                self.store.load_secrets()
                checks.append(
                    DoctorCheck(
                        name="credentials_valid", ok=True, detail="loaded"
                    )
                )
            except KeyStoreError as exc:
                checks.append(
                    DoctorCheck(
                        name="credentials_valid", ok=False, detail=str(exc)
                    )
                )
        client = self.client()
        try:
            reachable = client.health()
        finally:
            client.close()
        checks.append(
            DoctorCheck(
                "coordinator_reachable",
                reachable,
                self.config.base_url,
            )
        )
        docker_backend = DockerBackend()
        checks.append(
            DoctorCheck(
                "docker_available",
                docker_backend.available(),
                "docker CLI" if docker_backend.available() else "missing",
            )
        )
        return checks

    # ── run ─────────────────────────────────────────────────────

    def run(
        self,
        *,
        once: bool = True,
        poll_seconds: int = 5,
        capabilities: list[str] | None = None,
        stop=None,
    ) -> JsonObject:
        """Drive the lease loop once or continuously."""
        secrets = self._require_secrets()
        if capabilities is None:
            capabilities = []
        store = JsonlStateStore(job_history_path(self.config.state_dir))
        client = self.client()
        backend = self._backend()
        try:
            if once:
                return run_one_iteration(
                    client,
                    backend,
                    runner_id=secrets.runner_id,
                    runner_key=secrets.runner_key,
                    signing_key=self.store.signing_key(),
                    capabilities=capabilities,
                    runtime_digest=_runtime_digest(),
                    state_store=store,
                )
            iterations = run_loop(
                client,
                backend,
                runner_id=secrets.runner_id,
                runner_key=secrets.runner_key,
                signing_key=self.store.signing_key(),
                capabilities=capabilities,
                runtime_digest=_runtime_digest(),
                poll_seconds=poll_seconds,
                stop=stop or (lambda: False),
                state_store=store,
            )
        except LoopError as exc:
            raise RunnerNotEnrolled(str(exc)) from exc
        else:
            return {"iterations": iterations}
        finally:
            client.close()

    # ── jobs (local history) ────────────────────────────────────

    def jobs(self, limit: int = 20) -> list[JsonObject]:
        """Return the most recent local run-history entries."""
        path = job_history_path(self.config.state_dir)
        if not path.is_file():
            return []
        entries: list[JsonObject] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if isinstance(entry, dict):
                entries.append(entry)
        return entries[-limit:]


def _runtime_digest() -> str:
    """Stable digest of the runner runtime (version + python)."""
    import hashlib

    import logion_runner

    material = (
        f"logion-runner/{logion_runner.package_version()}"
        f" python/{platform.python_version()}"
    )
    return hashlib.sha256(material.encode()).hexdigest()


def _default_name() -> str:
    return f"runner-{platform.node()}"


__all__ = [
    "DoctorCheck",
    "RunnerNode",
    "RunnerNotEnrolled",
    "SandboxUnavailable",
]
