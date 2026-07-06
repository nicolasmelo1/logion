from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from agent_proving_ground.api_adapters.base import ApiAdapter, World
from agent_proving_ground.models import AssertionOutcome
from agent_proving_ground.timeline import Timeline


@dataclass
class AssertionContext:
    scenario_name: str
    phase_id: str | None
    world: World
    api: ApiAdapter
    artifacts_dir: Path
    timeline: Timeline


class Assertion(Protocol):
    type: str

    async def evaluate(
        self,
        ctx: AssertionContext,
        params: dict,
    ) -> AssertionOutcome: ...
