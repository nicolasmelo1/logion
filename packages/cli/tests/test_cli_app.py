"""Tests for CLI app — help text, version, command registration."""

from __future__ import annotations

from pathlib import Path

import pytest

from cli.main import main

_HERE = Path(__file__).resolve().parent.parent


def test_help_includes_phase_1_commands(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--help lists health, listings, and notifications."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "health" in output
    assert "listings" in output
    assert "notifications" in output


def test_project_scripts_define_logion_and_lgn() -> None:
    """pyproject.toml defines both logion and lgn entrypoints."""
    data = (_HERE / "pyproject.toml").read_text()
    import tomllib

    parsed = tomllib.loads(data)
    scripts = parsed["project"]["scripts"]
    assert scripts["logion"] == "cli.main:main"
    assert scripts["lgn"] == "cli.main:main"


def test_version_uses_package_metadata(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--version reads from importlib.metadata."""
    monkeypatch.setattr("cli._version.version", lambda _: "1.2.3")
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    assert "1.2.3" in capsys.readouterr().out


def test_bounties_appears_in_help(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--help lists bounties as a top-level command."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "bounties" in output


def test_evals_dspy_appears_in_help(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--help lists evals as a top-level development command."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "evals" in output

    with pytest.raises(SystemExit) as dspy_exc:
        main(["evals", "dspy", "--help"])
    assert dspy_exc.value.code == 0
    dspy_output = capsys.readouterr().out
    assert "split-scenarios" in dspy_output
    assert "optimize-policy" in dspy_output


def test_admin_hidden_by_default() -> None:
    """admin subcommand exits 2 without LOGION_ENABLE_ADMIN."""
    code = main(["admin"])
    assert code == 2


def test_admin_visible_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """With LOGION_ENABLE_ADMIN set, admin --help shows sub-commands."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    with pytest.raises(SystemExit) as exc_info:
        main(["admin", "--help"])
    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "users" in output


def test_no_command_exits_with_error() -> None:
    """Running with no subcommand exits 2."""
    with pytest.raises(SystemExit) as exc_info:
        main([])
    # argparse exits 2 for missing required subcommand
    assert exc_info.value.code == 2
