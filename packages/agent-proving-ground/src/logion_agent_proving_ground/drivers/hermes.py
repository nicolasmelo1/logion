from __future__ import annotations

import asyncio
import os
import re
import shutil
from pathlib import Path
from typing import Any, ClassVar, Literal

from logion_agent_proving_ground.drivers.base import (
    AgentDriver,
    AgentLaunch,
    AgentTurnResult,
)
from logion_agent_proving_ground.redaction import redact_text


async def _stream_output(
    proc: asyncio.subprocess.Process,
    transcript_path: Path,
    redactor: Any,
) -> None:
    assert proc.stdout is not None
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        decoded = line.decode("utf-8", errors="replace")
        with transcript_path.open("a", encoding="utf-8") as f:
            f.write(redactor(decoded))


async def _run_with_pty(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    transcript_path: Path,
    timeout_seconds: int,
    redactor: Any,
) -> tuple[int | None, str]:
    """Run hermes in a real pseudo-terminal so it believes stdin is a TTY."""
    import pty
    import select as select_mod
    import time

    master_fd, slave_fd = pty.openpty()
    try:
        proc = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            env=env,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
        )
    finally:
        os.close(slave_fd)

    collected: list[str] = []
    deadline = time.monotonic() + timeout_seconds
    loop = asyncio.get_running_loop()

    def _read_chunk() -> str:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return ""
        ready, _, _ = select_mod.select(
            [master_fd], [], [], min(remaining, 1.0)
        )
        if master_fd not in ready:
            return ""
        try:
            data = os.read(master_fd, 8192)
        except OSError:
            return ""
        if not data:
            return ""
        return data.decode("utf-8", errors="replace")

    while True:
        chunk = await loop.run_in_executor(None, _read_chunk)
        if chunk:
            redacted = redactor(chunk)
            with transcript_path.open("a", encoding="utf-8") as f:
                f.write(redacted)
            collected.append(chunk)
        if proc.returncode is not None:
            # drain remaining output
            while True:
                chunk = await loop.run_in_executor(None, _read_chunk)
                if not chunk:
                    break
                redacted = redactor(chunk)
                with transcript_path.open("a", encoding="utf-8") as f:
                    f.write(redacted)
                collected.append(chunk)
            break
        if time.monotonic() >= deadline:
            proc.kill()
            break

    return proc.returncode, "".join(collected)


def _classify_turn(
    exit_code: int | None,
    transcript: str,
    transcript_path: Path,
) -> AgentTurnResult:
    upper = transcript.upper()
    if "RESULT: COMPLETED" in upper:
        status: Literal["completed", "failed", "inconclusive", "timed_out"] = (
            "completed"
        )
        summary = "agent reported completion"
    elif "RESULT: FAILED" in upper:
        status = "failed"
        summary = "agent reported failure"
    elif "RESULT: BLOCKED" in upper:
        status = "inconclusive"
        summary = "agent reported a blocker"
    elif exit_code == 0:
        status = "inconclusive"
        summary = "agent exited 0 without a result marker"
    else:
        status = "failed"
        summary = f"agent exited with code {exit_code}"

    return AgentTurnResult(
        status=status,
        transcript_path=transcript_path,
        summary=summary,
        raw_exit_code=exit_code,
    )


def _phase_scaffolding(phase_id: str, unique_slug: str) -> list[str]:
    """Return phase-specific scaffolding lines for the prompt.

    Only creator/publisher phases need course-creation and bundle-upload
    hints.  Reviewer, learner, and bounty phases must NOT receive these
    hints — otherwise the agent creates a brand-new course instead of
    reviewing or purchasing the existing one.
    """
    creator_phases = {
        "creator_publishes_course",
        "publisher_publishes_course",
    }
    if phase_id not in creator_phases:
        return []
    return [
        "",
        "Create a NEW course with a unique slug. Base the slug on this run "
        f"identifier: '{unique_slug}'.",
        "Keep the course minimal: one short description, one SKILL.md with a "
        "single tiny exercise, and a LICENSE file. No extra lessons.",
        "When uploading bundle files with `logion courses uploads push`, use "
        "the explicit mapping syntax:",
        "  --file course/capabilities.yaml=/path/to/course/capabilities.yaml",
        "  --file SKILL.md=/path/to/SKILL.md",
        "  --file LICENSE=/path/to/LICENSE",
        "so the upload key preserves the required `course/capabilities.yaml` "
        "path.",
    ]


def _build_prompt(
    goal: str,
    unique_slug: str,
    success_hint: str | None = None,
    phase_id: str = "",
) -> str:
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
    parts.extend(_phase_scaffolding(phase_id, unique_slug))
    if success_hint:
        parts.extend(["", f"Success hint: {success_hint}"])
    return "\n".join(parts) + "\n"


class HermesDriver(AgentDriver):
    """Run one agent turn through the local Hermes CLI.

    Spawns ``hermes chat --cli -q <prompt> --quiet --accept-hooks --yolo``
    inside a real pseudo-terminal so the Hermes REPL believes stdin is a TTY.
    ``--yolo`` bypasses dangerous-command confirmations, matching the proving
    ground's non-interactive mode.  ``--max-turns`` keeps a single phase from
    running indefinitely.  The child is expected to emit
    ``RESULT: completed``, ``RESULT: failed`` or ``RESULT: blocked`` so the
    supervisor can classify the turn.
    """

    name = "hermes"
    default_command: ClassVar[str] = "hermes"
    default_args: ClassVar[list[str]] = [
        "chat",
        "--cli",
        "--quiet",
        "--accept-hooks",
        "--yolo",
        "--source",
        "tool",
        "--max-turns",
        "80",
        "--toolsets",
        "web,terminal,file",
    ]

    def __init__(
        self,
        driver_config: dict[str, Any] | None = None,
    ) -> None:
        self._driver_config = driver_config or {}
        self._launch: AgentLaunch | None = None

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
            raise RuntimeError("hermes driver not started")

        executable = self._resolve_executable()
        if executable is None:
            return AgentTurnResult(
                status="inconclusive",
                transcript_path=self._launch.workspace / "transcript.md",
                summary="hermes executable not available",
                raw_exit_code=None,
            )

        run_unique = self._launch.run_id.replace("-", "_").replace(".", "_")
        role_slug = re.sub(
            r"[^a-z0-9_-]", "", self._launch.role.lower().replace(" ", "-")
        )[:20]
        agent_slug = re.sub(r"[^a-z0-9_-]", "", self._launch.agent_id.lower())[
            :20
        ]
        unique_slug = f"{role_slug}-{agent_slug}-{run_unique}"[:64]

        prompt = _build_prompt(goal, unique_slug, success_hint, phase_id)
        command = [
            executable,
            *self._effective_args(),
            "-q",
            prompt,
        ]
        transcript_path = self._launch.workspace / f"{phase_id}.md"
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        transcript_path.write_text(
            f"# Agent turn\n\nPrompt:\n{redact_text(prompt)}\n\nOutput:\n",
            encoding="utf-8",
        )

        env = {
            **os.environ,
            **self._launch.env,
            "HERMES_QUIET": "1",
            "TERM": "xterm-256color",
            # Strip any active Hermes session context so the child runs as a
            # standalone chat, not as part of the orchestrating session.
            "HERMES_SESSION_ID": "",
            "HERMES_SESSION_KEY": "",
            "HERMES_SESSION_CHAT_ID": "",
            "HERMES_SESSION_MESSAGE_ID": "",
            "HERMES_SESSION_USER_ID": "",
            "HERMES_SESSION_USER_NAME": "",
            "HERMES_SESSION_PLATFORM": "",
            "HERMES_SESSION_SOURCE": "",
            "HERMES_SESSION_THREAD_ID": "",
            "HERMES_SESSION_CHAT_NAME": "",
            "HERMES_GATEWAY_BUSY_INPUT_MODE": "",
            "_HERMES_GATEWAY": "",
        }

        exit_code, _ = await _run_with_pty(
            command,
            cwd=self._launch.workspace,
            env=env,
            transcript_path=transcript_path,
            timeout_seconds=timeout_seconds,
            redactor=redact_text,
        )

        transcript = transcript_path.read_text(encoding="utf-8")
        return _classify_turn(exit_code, transcript, transcript_path)

    async def stop(self) -> None:
        self._launch = None

    def _resolve_executable(self) -> str | None:
        provider_cfg = self._driver_config.get("hermes", {})
        explicit = provider_cfg.get("command")
        if explicit:
            path = shutil.which(str(explicit))
            return path if path else None
        return shutil.which(self.default_command)

    def _effective_args(self) -> list[str]:
        provider_cfg = self._driver_config.get("hermes", {})
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
