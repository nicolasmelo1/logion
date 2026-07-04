from __future__ import annotations

from logion_agent_proving_ground.api_adapters.mock import MockApiAdapter


class FakeApiAdapter(MockApiAdapter):
    def __init__(self) -> None:
        super().__init__(seed_course=True)
