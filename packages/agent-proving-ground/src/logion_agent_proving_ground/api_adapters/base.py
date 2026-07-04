from __future__ import annotations

from typing import Any, Protocol

from logion_agent_proving_ground.models import World


class ApiAdapter(Protocol):
    name: str

    async def start(self) -> None: ...

    async def create_world(
        self,
        run_id: str,
        scenario_name: str,
        agent_ids: list[str],
    ) -> World: ...

    async def snapshot(self, world: World) -> dict[str, Any]: ...

    async def query(
        self, world: World, query: dict[str, Any]
    ) -> dict[str, Any]: ...

    async def stop(self) -> None: ...
