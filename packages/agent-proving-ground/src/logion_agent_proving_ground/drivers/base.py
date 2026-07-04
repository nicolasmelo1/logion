from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol


@dataclass(frozen=True)
class AgentLaunch:
    run_id: str
    agent_id: str
    role: str
    workspace: Path
    env: dict[str, str]
    system_prompt: str | None
    timeout_seconds: int


@dataclass(frozen=True)
class AgentTurnResult:
    status: Literal["completed", "failed", "inconclusive", "timed_out"]
    transcript_path: Path
    summary: str | None = None
    raw_exit_code: int | None = None


class AgentDriver(Protocol):
    name: str

    async def start(self, launch: AgentLaunch) -> None: ...

    async def send_goal(
        self,
        *,
        phase_id: str,
        goal: str,
        success_hint: str | None,
        timeout_seconds: int,
    ) -> AgentTurnResult: ...

    async def stop(self) -> None: ...
