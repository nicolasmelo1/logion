from __future__ import annotations

import os
import shutil
from collections.abc import Sequence
from typing import ClassVar

from agent_proving_ground._json import (
    JsonObject,
    JsonValue,
    child,
    elements,
    opt_str,
)
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
    safe_host_env: ClassVar[frozenset[str]] = frozenset({
        "COLORTERM",
        "FORCE_COLOR",
        "HOME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "LOGNAME",
        "NO_COLOR",
        "PATH",
        "SHELL",
        "TERM",
        "TMPDIR",
        "USER",
    })

    def __init__(
        self,
        driver_config: JsonObject | None = None,
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
        env = self._effective_env()
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
        provider_cfg = child(self._driver_config, self.provider_name)
        explicit = opt_str(provider_cfg, "command")
        if explicit:
            path = shutil.which(explicit)
            return path if path else None
        return shutil.which(self.default_command)

    def _effective_args(self) -> list[str]:
        provider_cfg = child(self._driver_config, self.provider_name)
        args = self._coerce_arg_list(
            provider_cfg.get("args", self.default_args)
        )
        extra = self._coerce_arg_list(elements(provider_cfg, "extra_args"))
        combined = [*args, *extra]
        model = opt_str(provider_cfg, "model")
        provider = opt_str(provider_cfg, "provider")
        if model:
            combined = _override_flag(combined, "--model", model)
        if provider:
            combined = _override_flag(combined, "--provider", provider)
        return combined

    def _effective_env(self) -> dict[str, str]:
        """Expose only safe host config plus the isolated role environment."""
        if self._launch is None:
            return {}
        provider_cfg = child(self._driver_config, self.provider_name)
        explicit_names = self._coerce_arg_list(
            elements(provider_cfg, "env_allowlist")
        )
        allowed_names = self.safe_host_env | frozenset(explicit_names)
        host_env = {
            name: os.environ[name]
            for name in allowed_names
            if name in os.environ
        }
        return {**host_env, **self._launch.env}

    @staticmethod
    def _coerce_arg_list(value: JsonValue) -> list[str]:
        """Read a driver-config arg list, tolerating a bare string.

        A scenario may write ``args: --json`` instead of a list; that
        stays one argument rather than being split into characters.
        """
        if isinstance(value, str):
            return [value]
        if isinstance(value, Sequence):
            return [str(item) for item in value]
        return []


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
    # `codex` without `exec` launches the interactive TUI and fails under the
    # proving-ground pipe with "stdin is not a terminal". Keep execution
    # non-interactive and prevent an unanswerable approval prompt.
    default_args: ClassVar[list[str]] = [
        "exec",
        "--sandbox",
        "workspace-write",
        "--skip-git-repo-check",
        "--config",
        'approval_policy="never"',
        "--config",
        "sandbox_workspace_write.network_access=true",
        "--model",
        "gpt-5-codex",
    ]

    def _effective_args(self) -> list[str]:
        args = super()._effective_args()
        if self._launch is None:
            return args
        logion_home = self._launch.env.get("LOGION_HOME")
        if not logion_home:
            return args
        return [*args, "--add-dir", logion_home]


class ClaudeCodeDriver(ProviderDriver):
    name = "claude-code"
    provider_name = "claude-code"
    default_command = "claude"
    # Haiku keeps full e2e runs cheap; override via driver_config for
    # scenarios that need a stronger model.
    #
    # Bash is allowed unscoped rather than as `Bash(logion:*)`. The
    # scenarios drive the CLI out of the checkout with a per-command
    # environment — `HOME=... LOGION_HOME=... uv run --project <repo>
    # logion ...` — and a prefix rule cannot match a command that starts
    # with an assignment. With the narrower rule the agent could only ask
    # for an approval that `--print` can never deliver, so every phase
    # failed with a transcript full of questions. The tool set stays
    # closed; this is the same posture as the codex driver's
    # `approval_policy="never"`, in a child process with an isolated env.
    default_args: ClassVar[list[str]] = [
        "--print",
        "--allowedTools",
        "Bash,Read,Write,Edit,Glob,Grep",
        "--model",
        "claude-haiku-4-5",
    ]
