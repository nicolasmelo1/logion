# SPDX-License-Identifier: MIT
"""Tests for the first-run onboarding trigger."""

from __future__ import annotations

import argparse

import pytest

from cli._first_run import decide, is_noninteractive
from cli._parser import build_parser


def _parse(argv: list[str]):
    """Parse argv and return the Namespace."""
    return build_parser().parse_args(argv)


def test_trigger_fires_when_unonboarded_and_tty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("cli._first_run.is_onboarded", lambda: False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.delenv("LOGION_NONINTERACTIVE", raising=False)
    args = _parse(["courses", "purchase", "abc"])
    d = decide(["courses", "purchase", "abc"], args)
    assert d.should_run is True
    assert d.reason == "command-needs-setup"


def test_trigger_skips_when_onboarded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("cli._first_run.is_onboarded", lambda: True)
    args = _parse(["courses", "purchase", "abc"])
    d = decide(["courses", "purchase", "abc"], args)
    assert d.should_run is False
    assert d.reason == "already-onboarded"


def test_trigger_skips_help_via_decide(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``decide`` returns ``help-version`` without requiring parse_args."""
    monkeypatch.setattr("cli._first_run.is_onboarded", lambda: False)
    args = argparse.Namespace(command="courses", no_onboarding=False)
    d = decide(["courses", "--help"], args)
    assert d.should_run is False
    assert d.reason == "help-version"


def test_trigger_skips_help_parse_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--help`` makes argparse exit; ``decide`` is never reached."""
    monkeypatch.setattr("cli._first_run.is_onboarded", lambda: False)
    with pytest.raises(SystemExit):
        _parse(["courses", "--help"])


def test_trigger_skips_version(monkeypatch: pytest.MonkeyPatch) -> None:
    # --version exits before parse_args returns, so we test the raw
    # argv check directly.
    monkeypatch.setattr("cli._first_run.is_onboarded", lambda: False)
    args = argparse.Namespace(command=None, no_onboarding=False)
    d = decide(["--version"], args)
    assert d.should_run is False
    assert d.reason == "help-version"


def test_trigger_skips_docs_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("cli._first_run.is_onboarded", lambda: False)
    args = _parse(["docs"])
    d = decide(["docs"], args)
    assert d.should_run is False
    assert d.reason == "skip-command"


def test_trigger_skips_onboarding_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("cli._first_run.is_onboarded", lambda: False)
    args = _parse(["onboarding", "--no-enable-autopost"])
    d = decide(["onboarding", "--no-enable-autopost"], args)
    assert d.should_run is False
    assert d.reason == "skip-command"


def test_trigger_skips_noninteractive_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("cli._first_run.is_onboarded", lambda: False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setenv("LOGION_NONINTERACTIVE", "1")
    args = _parse(["courses", "purchase", "abc"])
    d = decide(["courses", "purchase", "abc"], args)
    assert d.should_run is False
    assert d.reason == "noninteractive-env"


def test_trigger_skips_no_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("cli._first_run.is_onboarded", lambda: False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.delenv("LOGION_NONINTERACTIVE", raising=False)
    args = _parse(["courses", "purchase", "abc"])
    d = decide(["courses", "purchase", "abc"], args)
    assert d.should_run is False
    assert d.reason == "noninteractive-env"


def test_trigger_skips_no_onboarding_flag_before_subcommand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("cli._first_run.is_onboarded", lambda: False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    args = _parse(["--no-onboarding", "courses", "purchase", "abc"])
    d = decide(["--no-onboarding", "courses", "purchase", "abc"], args)
    assert d.should_run is False
    assert d.reason == "no-onboarding-flag"


def test_trigger_skips_no_onboarding_flag_after_subcommand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--no-onboarding`` after the subcommand is honoured via raw argv."""
    monkeypatch.setattr("cli._first_run.is_onboarded", lambda: False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    # argparse does not populate ``args.no_onboarding`` when the flag
    # appears after the subcommand, so ``decide`` must check raw argv.
    args = _parse(["courses", "purchase", "abc"])
    d = decide(["courses", "purchase", "abc", "--no-onboarding"], args)
    assert d.should_run is False
    assert d.reason == "no-onboarding-flag"


def test_trigger_skips_non_setup_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("cli._first_run.is_onboarded", lambda: False)
    args = _parse(["health"])
    d = decide(["health"], args)
    assert d.should_run is False
    assert d.reason == "unknown-command"


def test_trigger_skips_listings_browse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``listings`` is public/read-only — must not force onboarding."""
    monkeypatch.setattr("cli._first_run.is_onboarded", lambda: False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.delenv("LOGION_NONINTERACTIVE", raising=False)
    args = _parse(["listings", "search", "--query", "x"])
    d = decide(["listings", "search", "--query", "x"], args)
    assert d.should_run is False
    assert d.reason == "unknown-command"


def test_trigger_skips_json_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--json`` is treated as non-interactive: never hijack stdout."""
    monkeypatch.setattr("cli._first_run.is_onboarded", lambda: False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.delenv("LOGION_NONINTERACTIVE", raising=False)
    args = _parse(["courses", "purchase", "abc", "--json"])
    d = decide(["courses", "purchase", "abc", "--json"], args)
    assert d.should_run is False
    assert d.reason == "json-output"


def test_is_noninteractive_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setenv("LOGION_NONINTERACTIVE", "1")
    assert is_noninteractive() is True


def test_is_noninteractive_no_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOGION_NONINTERACTIVE", raising=False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    assert is_noninteractive() is True


def test_is_noninteractive_with_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOGION_NONINTERACTIVE", raising=False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    assert is_noninteractive() is False


def test_main_no_onboarding_after_subcommand_does_not_trigger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--no-onboarding`` after the subcommand must be accepted by
    argparse and prevent the first-run trigger from firing."""
    from cli.main import main

    monkeypatch.setattr("cli._first_run.is_onboarded", lambda: False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.delenv("LOGION_NONINTERACTIVE", raising=False)
    # Patch the onboarding handler so we can assert it was NOT called.
    called: list[bool] = []
    monkeypatch.setattr(
        "cli.commands.identity.onboarding.handle_onboarding",
        lambda _args: called.append(True) or 0,
    )
    # Use a setup command to isolate the flag's effect.
    main(["courses", "purchase", "abc", "--no-onboarding"])
    # The command handler may fail (no API), but onboarding must not run.
    assert called == []
