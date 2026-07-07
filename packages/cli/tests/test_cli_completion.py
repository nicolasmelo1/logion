# SPDX-License-Identifier: MIT
"""Tests for ``logion completion``."""

from __future__ import annotations

import json

import pytest

from cli.main import main

_KIND = "logion.completion"


@pytest.mark.parametrize("shell", ["bash", "zsh", "tcsh"])
def test_completion_emits_script_for_shell(
    shell: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Each supported shell yields a non-empty completion script that
    references the CLI's own command name."""
    code = main(["completion", shell])
    assert code == 0
    out = capsys.readouterr().out
    assert out.strip()
    assert "logion" in out


def test_completion_covers_all_top_level_commands(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The generated script mentions every registered top-level command,
    proving completion is derived from the live parser (not a stale
    hand-maintained list)."""
    from cli._parser import build_parser

    parser = build_parser()
    commands = set()
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if choices:
            commands.update(choices)

    code = main(["completion", "bash"])
    assert code == 0
    out = capsys.readouterr().out
    missing = sorted(c for c in commands if c not in out)
    assert not missing, f"commands absent from completion script: {missing}"


def test_completion_json_envelope(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--json wraps the script in the standard envelope."""
    code = main(["completion", "zsh", "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == _KIND
    assert payload["data"]["shell"] == "zsh"
    assert payload["data"]["script"].strip()


def test_completion_rejects_unknown_shell() -> None:
    """An unsupported shell is rejected by argparse before dispatch."""
    with pytest.raises(SystemExit) as excinfo:
        main(["completion", "powershell"])
    assert excinfo.value.code != 0
