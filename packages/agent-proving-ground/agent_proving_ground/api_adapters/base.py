from __future__ import annotations

from typing import Protocol

from agent_proving_ground._json import JsonObject
from agent_proving_ground.models import World


class ApiAdapter(Protocol):
    name: str

    async def start(self) -> None: ...

    async def create_world(
        self,
        run_id: str,
        scenario_name: str,
        agent_ids: list[str],
        agent_roles: dict[str, str] | None = None,
    ) -> World: ...

    async def snapshot(self, world: World) -> JsonObject: ...

    async def query(self, world: World, query: JsonObject) -> JsonObject: ...

    async def stop(self) -> None: ...
