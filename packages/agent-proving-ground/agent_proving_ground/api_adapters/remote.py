from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from agent_proving_ground.api_adapters._http import (
    HealthCheckError,
    health_check_endpoint,
)
from agent_proving_ground.api_adapters._queries import (
    LogionApiQueries,
    RoleKeyStore,
)
from agent_proving_ground.api_adapters.base import ApiAdapter, World


class RemoteApiAdapter(ApiAdapter):
    """Adapter that attaches to any reachable Logion API endpoint.

    This adapter never assumes database access. It can health-check the
    configured endpoint and will answer portable queries when the API
    exposes the needed public surface; otherwise it returns
    ``unsupported`` so assertions can be marked optional.
    """

    name = "remote"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        admin_key: str | None = None,
        api_config: dict[str, Any] | None = None,
    ) -> None:
        self._base_url = _resolve_base_url(base_url, api_config)
        self._admin_key = admin_key or _resolve_admin_key(api_config)
        self._api_config = api_config or {}
        self._queries = LogionApiQueries(
            self._base_url, RoleKeyStore.from_env()
        )

    async def start(self) -> None:
        await health_check_endpoint(self._base_url)

    async def create_world(
        self,
        run_id: str,
        scenario_name: str,  # noqa: ARG002
        agent_ids: list[str],
        agent_roles: dict[str, str] | None = None,
    ) -> World:
        agent_env: dict[str, dict[str, str]] = {}
        for agent_id in agent_ids:
            env: dict[str, str] = {
                "LOGION_BASE_URL": self._base_url,
                "LOGION_API_BASE_URL": self._base_url,
                "LOGION_PROVING_GROUND_RUN_ID": run_id,
                "LOGION_PROVING_GROUND_AGENT_ID": agent_id,
            }
            if self._admin_key:
                env["LOGION_PROVING_GROUND_ADMIN_KEY"] = self._admin_key
            agent_env[agent_id] = env
        baseline = {}
        if self._queries.configured:
            baseline = await self._queries.baseline(agent_roles or {})

        return World(
            run_id=run_id,
            base_url=self._base_url,
            root_dir=Path(),
            agent_env=agent_env,
            handles={aid: f"agent_{aid}" for aid in agent_ids},
            data={
                "api_config": self._api_config,
                "agent_roles": agent_roles or {},
                "baseline": baseline,
            },
        )

    async def snapshot(self, world: World) -> dict[str, Any]:  # noqa: ARG002
        return {"base_url": self._base_url}

    async def query(
        self,
        world: World,
        query: dict[str, Any],
    ) -> dict[str, Any]:
        query_type = query.get("type")
        if query_type == "health_ok":
            try:
                await health_check_endpoint(self._base_url)
            except HealthCheckError as exc:
                return {"found": False, "error": str(exc)}
            return {"found": True, "evidence": {"source": "api"}}
        if self._queries.configured:
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
                "remote adapter has no proving-ground API keys; set "
                "LOGION_PROVING_GROUND_ROLE_KEYS_FILE or "
                "LOGION_PROVING_GROUND_API_KEY to enable "
                "observed-effect queries"
            ),
        }

    async def stop(self) -> None:
        pass


def _resolve_base_url(
    explicit: str | None, api_config: dict[str, Any] | None
) -> str:
    if explicit:
        return explicit.rstrip("/")
    env_name = (api_config or {}).get("base_url_env")
    if env_name:
        env_value = os.environ.get(env_name)
        if env_value:
            return env_value.rstrip("/")
    env_value = os.environ.get("LOGION_PROVING_GROUND_BASE_URL")
    if env_value:
        return env_value.rstrip("/")
    raise HealthCheckError(
        "remote adapter requires a base URL: set "
        "LOGION_PROVING_GROUND_BASE_URL, scenario api_config.base_url_env, "
        "or pass --api-base-url"
    )


def _resolve_admin_key(api_config: dict[str, Any] | None) -> str | None:
    env_name = (api_config or {}).get("admin_key_env")
    if env_name:
        return os.environ.get(env_name)
    return os.environ.get("LOGION_PROVING_GROUND_ADMIN_KEY")
