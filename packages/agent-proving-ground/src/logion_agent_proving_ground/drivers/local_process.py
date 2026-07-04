from __future__ import annotations

from logion_agent_proving_ground.drivers.base import (
    AgentDriver,
    AgentLaunch,
    AgentTurnResult,
)
from logion_agent_proving_ground.drivers.process import ChildProcessSession


def _build_prompt(goal: str, success_hint: str | None = None) -> str:
    parts = [
        "User request:",
        goal,
        "",
        "Operational constraints:",
        "- Use only the local workspace and Logion commands available here.",
        "- Use the Logion API base URL, installed CLI, and companion",
        "  already provided by your environment.",
        "- Do not use production services unless the environment",
        "  points there.",
        "- When you finish, clearly state RESULT: completed or",
        "  RESULT: failed.",
        "- If blocked, state RESULT: blocked and explain the observable",
        "  blocker.",
        "- Do not print secrets.",
    ]
    if success_hint:
        parts.extend(["", f"Success hint: {success_hint}"])
    return "\n".join(parts) + "\n"


class LocalProcessDriver(AgentDriver):
    name = "local-process"

    def __init__(self, command: list[str] | None = None) -> None:
        self._command = command
        self._launch: AgentLaunch | None = None
        self._session: ChildProcessSession | None = None

    async def start(self, launch: AgentLaunch) -> None:
        self._launch = launch

    async def send_goal(
        self,
        *,
        phase_id: str,
        goal: str,
        success_hint: str | None = None,
        timeout_seconds: int = 900,
    ) -> AgentTurnResult:
        if self._launch is None:
            raise RuntimeError("local-process driver not started")
        command = self._command
        if command is None:
            return AgentTurnResult(
                status="inconclusive",
                transcript_path=self._launch.workspace / "transcript.md",
                summary="no command configured for local-process driver",
                raw_exit_code=None,
            )

        transcript_path = self._launch.workspace / f"{phase_id}.md"
        self._session = ChildProcessSession(
            command=command,
            cwd=self._launch.workspace,
            env=self._launch.env,
            transcript_path=transcript_path,
            timeout_seconds=timeout_seconds,
        )
        return await self._session.run_once(_build_prompt(goal, success_hint))

    async def stop(self) -> None:
        self._launch = None
        self._session = None
