from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal

from agent_proving_ground.drivers.base import AgentTurnResult
from agent_proving_ground.redaction import redact_text


class ChildProcessSession:
    """Run one agent turn as an isolated child process.

    The process receives the phase prompt on stdin. Its combined stdout/stderr
    is streamed to the transcript and redacted before storage.
    """

    def __init__(
        self,
        *,
        command: list[str],
        cwd: Path,
        env: dict[str, str],
        transcript_path: Path,
        timeout_seconds: int,
    ) -> None:
        self.command = command
        self.cwd = cwd
        self.env = env
        self.transcript_path = transcript_path
        self.timeout_seconds = timeout_seconds

    async def run_once(self, prompt: str) -> AgentTurnResult:
        self.cwd.mkdir(parents=True, exist_ok=True)
        self.transcript_path.write_text(
            f"# Agent turn\n\nPrompt:\n{redact_text(prompt)}\n\nOutput:\n",
            encoding="utf-8",
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=self.cwd,
                env=self.env,
            )
        except FileNotFoundError as exc:
            return AgentTurnResult(
                status="inconclusive",
                transcript_path=self.transcript_path,
                summary=f"driver executable not found: {exc.filename}",
                raw_exit_code=None,
            )
        except PermissionError as exc:
            return AgentTurnResult(
                status="inconclusive",
                transcript_path=self.transcript_path,
                summary=f"driver executable not runnable: {exc.filename}",
                raw_exit_code=None,
            )

        stdout_chunks: list[bytes] = []
        try:
            stdout, _ = await asyncio.wait_for(
                self._communicate(proc, prompt, stdout_chunks),
                timeout=self.timeout_seconds,
            )
        except TimeoutError:
            proc.kill()
            await proc.wait()
            self._append_output(b"\n[supervisor timeout]\n")
            return AgentTurnResult(
                status="timed_out",
                transcript_path=self.transcript_path,
                summary="agent turn exceeded timeout",
                raw_exit_code=None,
            )

        raw_output = stdout if stdout else b""
        self._append_output(raw_output)
        transcript = self.transcript_path.read_text(encoding="utf-8")
        return self._classify(proc.returncode, transcript)

    async def _communicate(
        self,
        proc: asyncio.subprocess.Process,
        prompt: str,
        stdout_chunks: list[bytes],
    ) -> tuple[bytes, bytes]:
        assert proc.stdin is not None
        assert proc.stdout is not None
        proc.stdin.write(prompt.encode("utf-8"))
        await proc.stdin.drain()
        proc.stdin.close()
        await proc.stdin.wait_closed()

        while True:
            chunk = await proc.stdout.read(8192)
            if not chunk:
                break
            stdout_chunks.append(chunk)

        await proc.wait()
        return b"".join(stdout_chunks), b""

    def _append_output(self, raw_output: bytes) -> None:
        text = raw_output.decode("utf-8", errors="replace")
        redacted = redact_text(text)
        existing = self.transcript_path.read_text(encoding="utf-8")
        self.transcript_path.write_text(existing + redacted, encoding="utf-8")

    def _classify(
        self, exit_code: int | None, transcript: str
    ) -> AgentTurnResult:
        upper = transcript.upper()
        if "RESULT: COMPLETED" in upper:
            status: Literal[
                "completed", "failed", "inconclusive", "timed_out"
            ] = "completed"
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
            transcript_path=self.transcript_path,
            summary=summary,
            raw_exit_code=exit_code,
        )
