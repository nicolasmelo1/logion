from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from logion_agent_proving_ground.drivers._provider import (
    ClaudeCodeDriver,
    CodexDriver,
    OpencodeDriver,
)
from logion_agent_proving_ground.drivers.base import AgentLaunch
from logion_agent_proving_ground.drivers.local_process import (
    LocalProcessDriver,
)
from logion_agent_proving_ground.drivers.process import ChildProcessSession


@pytest.fixture
def bin_dir():
    return Path(__file__).parent.parent / "fixtures" / "bin"


@pytest.fixture
def fake_completed(bin_dir):
    return str(bin_dir / "fake_completed")


@pytest.fixture
def fake_inconclusive(bin_dir):
    return str(bin_dir / "fake_inconclusive")


@pytest.fixture
def fake_failed(bin_dir):
    return str(bin_dir / "fake_failed")


@pytest.fixture
def fake_secret(bin_dir):
    return str(bin_dir / "fake_secret")


@pytest.fixture
def fake_slow(bin_dir):
    return str(bin_dir / "fake_slow")


def _launch(tmp_path):
    return AgentLaunch(
        run_id="r1",
        agent_id="learner",
        role="Learner",
        workspace=tmp_path,
        env={},
        system_prompt=None,
        timeout_seconds=5,
    )


async def test_child_process_completed(tmp_path, fake_completed) -> None:
    session = ChildProcessSession(
        command=[fake_completed],
        cwd=tmp_path,
        env={},
        transcript_path=tmp_path / "transcript.md",
        timeout_seconds=5,
    )
    result = await session.run_once("do the thing")
    assert result.status == "completed"
    assert result.raw_exit_code == 0
    transcript = (tmp_path / "transcript.md").read_text(encoding="utf-8")
    assert "do the thing" in transcript
    assert "RESULT: completed" in transcript


async def test_child_process_inconclusive_without_marker(
    tmp_path, fake_inconclusive
) -> None:
    session = ChildProcessSession(
        command=[fake_inconclusive],
        cwd=tmp_path,
        env={},
        transcript_path=tmp_path / "transcript.md",
        timeout_seconds=5,
    )
    result = await session.run_once("do the thing")
    assert result.status == "inconclusive"
    assert result.raw_exit_code == 0


async def test_child_process_failed(tmp_path, fake_failed) -> None:
    session = ChildProcessSession(
        command=[fake_failed],
        cwd=tmp_path,
        env={},
        transcript_path=tmp_path / "transcript.md",
        timeout_seconds=5,
    )
    result = await session.run_once("do the thing")
    assert result.status == "failed"
    assert result.raw_exit_code == 1


async def test_child_process_timeout(tmp_path, fake_slow) -> None:
    session = ChildProcessSession(
        command=[fake_slow],
        cwd=tmp_path,
        env={},
        transcript_path=tmp_path / "transcript.md",
        timeout_seconds=1,
    )
    result = await session.run_once("do the thing")
    assert result.status == "timed_out"


async def test_child_process_redacts_secret_in_transcript(
    tmp_path, fake_secret
) -> None:
    session = ChildProcessSession(
        command=[fake_secret],
        cwd=tmp_path,
        env={},
        transcript_path=tmp_path / "transcript.md",
        timeout_seconds=5,
    )
    result = await session.run_once("do the thing")
    assert result.status == "completed"
    transcript = (tmp_path / "transcript.md").read_text(encoding="utf-8")
    assert "secret-token" not in transcript
    assert "<redacted>" in transcript


async def test_child_process_missing_executable(tmp_path) -> None:
    session = ChildProcessSession(
        command=["/nonexistent/binary/for_proving_ground"],
        cwd=tmp_path,
        env={},
        transcript_path=tmp_path / "transcript.md",
        timeout_seconds=5,
    )
    result = await session.run_once("do the thing")
    assert result.status == "inconclusive"
    assert result.summary is not None
    assert result.summary.startswith("driver executable not found")


async def test_local_process_driver_uses_agent_command(
    tmp_path, fake_completed
) -> None:
    driver = LocalProcessDriver(command=[fake_completed])
    await driver.start(_launch(tmp_path))
    result = await driver.send_goal(
        phase_id="p1", goal="do the thing", timeout_seconds=5
    )
    assert result.status == "completed"
    transcript = result.transcript_path.read_text(encoding="utf-8")
    assert "User request:" in transcript
    assert "Operational constraints:" in transcript


async def test_local_process_driver_without_command_is_inconclusive(
    tmp_path,
) -> None:
    driver = LocalProcessDriver(command=None)
    await driver.start(_launch(tmp_path))
    result = await driver.send_goal(
        phase_id="p1", goal="do the thing", timeout_seconds=5
    )
    assert result.status == "inconclusive"


async def test_provider_driver_inconclusive_when_missing_executable(
    tmp_path,
) -> None:
    with patch(
        "logion_agent_proving_ground.drivers._provider.shutil.which",
        return_value=None,
    ):
        driver = CodexDriver(driver_config={})
        await driver.start(_launch(tmp_path))
        result = await driver.send_goal(
            phase_id="p1", goal="do the thing", timeout_seconds=5
        )
    assert result.status == "inconclusive"
    assert result.summary is not None
    assert "codex executable not available" in result.summary


async def test_provider_driver_uses_configured_command(
    tmp_path, fake_completed
) -> None:
    driver = OpencodeDriver(
        driver_config={"opencode": {"command": fake_completed}}
    )
    await driver.start(_launch(tmp_path))
    result = await driver.send_goal(
        phase_id="p1", goal="do the thing", timeout_seconds=5
    )
    assert result.status == "completed"


async def test_claude_driver_defaults(tmp_path) -> None:
    driver = ClaudeCodeDriver(driver_config={})
    await driver.start(_launch(tmp_path))
    assert driver.provider_name == "claude-code"
    assert driver.default_command == "claude"
    assert driver.default_args
