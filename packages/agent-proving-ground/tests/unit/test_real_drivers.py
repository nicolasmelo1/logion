from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from agent_proving_ground.drivers._provider import (
    ClaudeCodeDriver,
    CodexDriver,
    OpencodeDriver,
)
from agent_proving_ground.drivers.base import AgentLaunch
from agent_proving_ground.drivers.local_process import (
    LocalProcessDriver,
)
from agent_proving_ground.drivers.process import ChildProcessSession


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
        "agent_proving_ground.drivers._provider.shutil.which",
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


async def test_provider_driver_sanitizes_host_environment(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("UNRELATED_SECRET_TOKEN", "must-not-leak")
    monkeypatch.setenv("PATH", "/safe/bin")
    driver = CodexDriver(driver_config={})
    launch = _launch(tmp_path)
    launch.env["LOGION_API_KEY"] = "isolated-role-key"

    await driver.start(launch)
    env = driver._effective_env()

    assert env["PATH"] == "/safe/bin"
    assert env["LOGION_API_KEY"] == "isolated-role-key"
    assert "UNRELATED_SECRET_TOKEN" not in env


async def test_provider_driver_allows_explicit_host_env(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("CUSTOM_PROVIDER_CONFIG", "explicit-value")
    driver = CodexDriver(
        driver_config={"codex": {"env_allowlist": ["CUSTOM_PROVIDER_CONFIG"]}}
    )

    await driver.start(_launch(tmp_path))

    assert (
        driver._effective_env()["CUSTOM_PROVIDER_CONFIG"] == "explicit-value"
    )


async def test_claude_driver_defaults(tmp_path) -> None:
    driver = ClaudeCodeDriver(driver_config={})
    await driver.start(_launch(tmp_path))
    assert driver.provider_name == "claude-code"
    assert driver.default_command == "claude"
    assert driver.default_args


def test_codex_driver_defaults_to_noninteractive_exec() -> None:
    args = CodexDriver(driver_config={})._effective_args()

    assert args[0] == "exec"
    assert "--sandbox" in args
    assert "workspace-write" in args
    assert "--skip-git-repo-check" in args
    assert 'approval_policy="never"' in args
    assert "sandbox_workspace_write.network_access=true" in args


async def test_codex_driver_allows_role_logion_home(tmp_path) -> None:
    driver = CodexDriver(driver_config={})
    launch = _launch(tmp_path)
    launch.env["LOGION_HOME"] = str(tmp_path / "role-home")
    (tmp_path / ".agents").mkdir()
    (tmp_path / ".codex").mkdir()

    await driver.start(launch)

    args = driver._effective_args()
    assert ["--add-dir", str(tmp_path / ".agents")] in [
        args[i : i + 2] for i in range(len(args) - 1)
    ]
    assert ["--add-dir", str(tmp_path / ".codex")] in [
        args[i : i + 2] for i in range(len(args) - 1)
    ]
    assert args[-2:] == ["--add-dir", str(tmp_path / "role-home")]


class TestProviderDriverModelProvider:
    """Model and provider config are forwarded as --model/--provider flags."""

    def test_provider_model_and_provider_in_args(self) -> None:
        driver = CodexDriver(
            driver_config={
                "codex": {
                    "model": "gpt-5.4-mini",
                    "provider": "openai",
                }
            }
        )
        args = driver._effective_args()
        assert "--model" in args
        idx = args.index("--model")
        assert args[idx + 1] == "gpt-5.4-mini"
        assert "--provider" in args
        pidx = args.index("--provider")
        assert args[pidx + 1] == "openai"

    def test_provider_model_only(self) -> None:
        driver = OpencodeDriver(
            driver_config={"opencode": {"model": "qwen/qwen3-coder"}}
        )
        args = driver._effective_args()
        assert "--model" in args
        assert "qwen/qwen3-coder" in args
        assert "--provider" not in args

    def test_provider_no_model_no_provider(self) -> None:
        driver = ClaudeCodeDriver(driver_config={})
        args = driver._effective_args()
        # default_args already contain --model; we just don't override it
        assert "--model" in args
        idx = args.index("--model")
        assert args[idx + 1] == "claude-haiku-4-5"

    def test_provider_extra_args_combined_with_model(self) -> None:
        driver = CodexDriver(
            driver_config={
                "codex": {
                    "model": "gpt-5.4-mini",
                    "extra_args": ["--verbose"],
                }
            }
        )
        args = driver._effective_args()
        assert "--model" in args
        assert "gpt-5.4-mini" in args
        assert "--verbose" in args
