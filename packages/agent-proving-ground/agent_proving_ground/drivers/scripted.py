from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal

from agent_proving_ground._json import (
    JsonObject,
    child,
)
from agent_proving_ground.drivers.base import (
    AgentDriver,
    AgentLaunch,
    AgentTurnResult,
)

ScriptedOperation = str | JsonObject
ApplyOperation = Callable[[str, str, JsonObject], None]


class ScriptedDriver(AgentDriver):
    name = "scripted"

    def __init__(
        self,
        operations: dict[str, list[ScriptedOperation]] | None = None,
        apply_operation: ApplyOperation | None = None,
    ) -> None:
        self._operations = operations or {}
        self._apply_operation = apply_operation
        self._launch: AgentLaunch | None = None
        self._transcript: Path | None = None

    async def start(self, launch: AgentLaunch) -> None:
        self._launch = launch
        launch.workspace.mkdir(parents=True, exist_ok=True)
        self._transcript = launch.workspace / "transcript.md"
        self._transcript.write_text(
            f"# Agent {launch.agent_id}\n\nRole: {launch.role}\n\n",
            encoding="utf-8",
        )

    async def send_goal(
        self,
        *,
        phase_id: str,
        goal: str,
        success_hint: str | None = None,
        timeout_seconds: int = 900,  # noqa: ARG002
    ) -> AgentTurnResult:
        if self._launch is None or self._transcript is None:
            raise RuntimeError("scripted driver not started")
        ops = self._operations.get(phase_id, [])
        status: Literal["completed", "failed"] = "completed"
        lines = [
            f"# Step {phase_id}\n",
            "Received goal:",
            goal,
            "",
        ]
        if success_hint:
            lines.extend(["Success hint:", success_hint, ""])
        if ops:
            lines.append("Actions:")
            for op in ops:
                if isinstance(op, dict):
                    name = str(op.get("operation", ""))
                    params = dict(child(op, "params"))
                    if name and self._apply_operation is not None:
                        self._apply_operation(
                            self._launch.agent_id, name, params
                        )
                    lines.append(f"- {name} {params}")
                else:
                    lines.append(f"- {op}")
        else:
            lines.append("Actions: none")
        lines.append("")
        lines.append(f"Result: {status}")
        lines.append("")
        text = "\n".join(lines)
        self._transcript.write_text(
            self._transcript.read_text(encoding="utf-8") + text,
            encoding="utf-8",
        )
        return AgentTurnResult(
            status=status,
            transcript_path=self._transcript,
            summary=f"completed step {phase_id}",
            raw_exit_code=0,
        )

    async def stop(self) -> None:
        self._launch = None
