from __future__ import annotations

import shutil
from typing import Any, ClassVar

from logion_agent_proving_ground.drivers.base import (
    AgentDriver,
    AgentLaunch,
    AgentTurnResult,
)
from logion_agent_proving_ground.drivers.local_process import _build_prompt
from logion_agent_proving_ground.drivers.process import ChildProcessSession


class ProviderDriver(AgentDriver):
    """Base for real provider CLIs (opencode, codex, claude-code)."""

    name: str
    provider_name: ClassVar[str]
    default_command: ClassVar[str]
    default_args: ClassVar[list[str]]

    def __init__(
        self,
        driver_config: dict[str, Any] | None = None,
    ) -> None:
        self._driver_config = driver_config or {}
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
            raise RuntimeError(f"{self.provider_name} driver not started")

        executable = self._resolve_executable()
        if executable is None:
            return AgentTurnResult(
                status="inconclusive",
                transcript_path=self._launch.workspace / "transcript.md",
                summary=f"{self.provider_name} executable not available",
                raw_exit_code=None,
            )

        command = [executable, *self._effective_args()]
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

    def _resolve_executable(self) -> str | None:
        provider_cfg = self._driver_config.get(self.provider_name, {})
        explicit = provider_cfg.get("command")
        if explicit:
            path = shutil.which(str(explicit))
            return path if path else None
        return shutil.which(self.default_command)

    def _effective_args(self) -> list[str]:
        provider_cfg = self._driver_config.get(self.provider_name, {})
        args = self._coerce_arg_list(
            provider_cfg.get("args", self.default_args)
        )
        extra = self._coerce_arg_list(provider_cfg.get("extra_args", []))
        return [*args, *extra]

    @staticmethod
    def _coerce_arg_list(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        return [str(item) for item in value]


class OpencodeDriver(ProviderDriver):
    name = "opencode"
    provider_name = "opencode"
    default_command = "opencode"
    default_args: ClassVar[list[str]] = [
        "run",
        "--model",
        "qwen/qwen3-coder",
    ]


class CodexDriver(ProviderDriver):
    name = "codex"
    provider_name = "codex"
    default_command = "codex"
    default_args: ClassVar[list[str]] = ["--model", "gpt-5-codex"]


class ClaudeCodeDriver(ProviderDriver):
    name = "claude-code"
    provider_name = "claude-code"
    default_command = "claude"
    default_args: ClassVar[list[str]] = [
        "--model",
        "claude-sonnet-4-20250514",
    ]
