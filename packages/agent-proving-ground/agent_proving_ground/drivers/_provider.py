from __future__ import annotations

import os
import shutil
from typing import Any, ClassVar

from agent_proving_ground.drivers.base import (
    AgentDriver,
    AgentLaunch,
    AgentTurnResult,
)
from agent_proving_ground.drivers.local_process import _build_prompt
from agent_proving_ground.drivers.process import ChildProcessSession


def _override_flag(args: list[str], flag: str, value: str) -> list[str]:
    """Replace the value after *flag* in *args*, or append flag+value."""
    result = list(args)
    try:
        idx = result.index(flag)
        if idx + 1 < len(result):
            result[idx + 1] = value
        else:
            result.extend([flag, value])
    except ValueError:
        result.extend([flag, value])
    return result


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
        # Real provider CLIs need the invoking user's environment (HOME,
        # PATH, provider auth config); the scenario/adapter env wins on
        # conflicts.
        env = {**os.environ, **self._launch.env}
        self._session = ChildProcessSession(
            command=command,
            cwd=self._launch.workspace,
            env=env,
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
        combined = [*args, *extra]
        model = provider_cfg.get("model")
        provider = provider_cfg.get("provider")
        if model:
            combined = _override_flag(combined, "--model", model)
        if provider:
            combined = _override_flag(combined, "--provider", provider)
        return combined

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
    # Haiku keeps full e2e runs cheap; override via driver_config for
    # scenarios that need a stronger model.
    default_args: ClassVar[list[str]] = [
        "--model",
        "claude-haiku-4-5",
    ]
