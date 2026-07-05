from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from logion_agent_proving_ground.api_adapters._env import (
    DevrigEnvError,
    build_devrig_env_for_agent,
    env_file_description,
    parse_export_env_file,
    validate_devrig_env,
)
from logion_agent_proving_ground.api_adapters._http import (
    HealthCheckError,
    health_check_endpoint,
)
from logion_agent_proving_ground.api_adapters._queries import (
    LogionApiQueries,
    RoleKeyStore,
)
from logion_agent_proving_ground.api_adapters.base import ApiAdapter, World


class LocalDevrigAdapter(ApiAdapter):
    """Attach-only adapter for the existing public ``logion/`` dev rig.

    This adapter does not start Docker, Postgres, MinIO, the API, or a
    second devrig. It expects ``make dev-up MODE=mock|prod ROLE=...`` to
    have already produced ``.devrig/devrig.env`` in the public repo root.
    It validates that env, health-checks the configured API/mock endpoint,
    and materializes per-agent environments by overriding
    ``LOGION_DEVRIG_ROLE``.
    """

    name = "local-devrig"

    def __init__(
        self,
        *,
        devrig_root: Path | str | None = None,
        api_log_path: Path | str | None = None,
    ) -> None:
        self._root = _resolve_devrig_root(devrig_root)
        self._env_path = self._root / ".devrig" / "devrig.env"
        self._api_log_path = (
            Path(api_log_path)
            if api_log_path
            else self._root / ".devrig" / "prism.log"
        )
        self._base_env: dict[str, str] = {}
        self._queries: LogionApiQueries | None = None

    async def start(self) -> None:
        self._base_env = parse_export_env_file(self._env_path)
        validate_devrig_env(self._base_env, label=str(self._env_path))
        await health_check_endpoint(self._base_env["LOGION_API_BASE_URL"])
        self._queries = LogionApiQueries(
            self._base_env["LOGION_API_BASE_URL"],
            RoleKeyStore.from_env(self._base_env),
        )

    async def create_world(
        self,
        run_id: str,
        scenario_name: str,  # noqa: ARG002
        agent_ids: list[str],
        agent_roles: dict[str, str] | None = None,
    ) -> World:
        if not self._base_env:
            self._base_env = parse_export_env_file(self._env_path)
            validate_devrig_env(self._base_env, label=str(self._env_path))

        role_keys = RoleKeyStore.from_env(self._base_env)
        agent_env: dict[str, dict[str, str]] = {}
        for agent_id in agent_ids:
            role = (agent_roles or {}).get(agent_id)
            env = build_devrig_env_for_agent(
                self._base_env, agent_id, role, run_id
            )
            api_key = role_keys.api_key(env.get("LOGION_DEVRIG_ROLE"))
            if api_key:
                env["LOGION_API_KEY"] = api_key
            agent_env[agent_id] = env
        baseline = {}
        if self._queries is not None and self._queries.configured:
            baseline = await self._queries.baseline(agent_roles or {})

        return World(
            run_id=run_id,
            base_url=self._base_env["LOGION_API_BASE_URL"],
            root_dir=self._root,
            agent_env=agent_env,
            handles={aid: f"agent_{aid}" for aid in agent_ids},
            data={
                "devrig_env": env_file_description(self._base_env),
                "api_log_present": self._api_log_path.is_file(),
                "agent_roles": agent_roles or {},
                "baseline": baseline,
            },
        )

    async def snapshot(
        self,
        world: World,  # noqa: ARG002
    ) -> dict[str, Any]:
        snapshot: dict[str, Any] = {
            "base_url": self._base_env.get("LOGION_API_BASE_URL"),
            "devrig_env": env_file_description(self._base_env),
        }
        if self._api_log_path.is_file():
            snapshot["api_log_tail"] = _tail_text(self._api_log_path, 200)
        return snapshot

    async def query(
        self,
        world: World,
        query: dict[str, Any],
    ) -> dict[str, Any]:
        query_type = query.get("type")
        if query_type == "health_ok":
            try:
                await health_check_endpoint(
                    self._base_env["LOGION_API_BASE_URL"]
                )
            except HealthCheckError as exc:
                return {"found": False, "error": str(exc)}
            return {"found": True, "evidence": {"source": "api"}}
        if query_type == "api_log_present":
            return {
                "found": self._api_log_path.is_file(),
                "path": str(self._api_log_path),
            }
        if self._queries is not None and self._queries.configured:
            agent_roles = world.data.get("agent_roles") or {}
            query_with_baseline = {
                **query,
                "_baseline": world.data.get("baseline") or {},
            }
            return await self._queries.query(
                query_with_baseline, dict(agent_roles)
            )
        return {
            "found": False,
            "unsupported": True,
            "reason": (
                "local-devrig adapter has no proving-ground API keys; "
                "set LOGION_PROVING_GROUND_ROLE_KEYS_FILE or LOGION_API_KEY "
                "to enable observed-effect queries"
            ),
        }

    async def stop(self) -> None:
        pass


def _resolve_devrig_root(explicit: Path | str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env_root = _env_root()
    if env_root:
        return env_root
    cwd = Path.cwd().resolve()
    if (cwd / "scripts" / "devrig.py").is_file() and (
        cwd / ".devrig" / "devrig.env"
    ).is_file():
        return cwd
    for parent in cwd.parents:
        if (parent / "scripts" / "devrig.py").is_file() and (
            parent / ".devrig" / "devrig.env"
        ).is_file():
            return parent
    raise DevrigEnvError(
        "local-devrig adapter could not find a public logion repo root. "
        "Pass --devrig-root or set LOGION_PUBLIC_REPO_PATH."
    )


def _env_root() -> Path | None:
    value = os.environ.get("LOGION_PUBLIC_REPO_PATH")
    if value:
        candidate = Path(value).expanduser().resolve()
        if (candidate / "scripts" / "devrig.py").is_file():
            return candidate
    return None


def _tail_text(path: Path, max_bytes: int = 65536) -> str:
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            if size <= max_bytes:
                f.seek(0)
            else:
                f.seek(-max_bytes, os.SEEK_END)
            data = f.read()
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")


def _copy_api_log_to_artifacts(
    api_log_path: Path, artifacts_root: Path
) -> Path | None:
    if not api_log_path.is_file():
        return None
    destination = artifacts_root / "services" / "api.log"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(api_log_path, destination)
    return destination
