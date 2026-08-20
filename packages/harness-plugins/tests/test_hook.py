# SPDX-License-Identifier: MIT
"""Tests for the hook entry point."""

from __future__ import annotations

import io
import json
from unittest.mock import patch

from logion_harness_plugins.hook import main


def test_hook_exits_zero_on_empty_stdin() -> None:
    """A broken payload must never break the harness."""
    with patch("sys.stdin", io.TextIOWrapper(io.BytesIO(b""))):
        assert main() == 0


def test_hook_exits_zero_on_invalid_json() -> None:
    with patch("sys.stdin", io.TextIOWrapper(io.BytesIO(b"not json"))):
        assert main() == 0


def test_hook_exits_zero_on_missing_logion() -> None:
    """If logion is not on PATH, the hook silently exits 0."""
    payload = json.dumps({"event": "resource_invoked"})
    with (
        patch("sys.stdin", io.TextIOWrapper(io.BytesIO(payload.encode()))),
        patch("subprocess.run", side_effect=FileNotFoundError),
    ):
        assert main() == 0


def test_hook_strips_internal_keys() -> None:
    """_logion_* keys are stripped before forwarding to the CLI."""
    payload = json.dumps({
        "_logion_harness": "claude-code",
        "event": "resource_invoked",
        "tool_name": "Read",
    })
    captured: dict = {}

    def fake_run(cmd, *, input, **_kwargs):  # noqa: A002
        captured["cmd"] = cmd
        captured["input"] = json.loads(input.decode())

    with (
        patch("sys.stdin", io.TextIOWrapper(io.BytesIO(payload.encode()))),
        patch("subprocess.run", side_effect=fake_run),
    ):
        main()

    assert "claude-code" in captured["cmd"]
    assert "_logion_harness" not in captured["input"]
    assert captured["input"]["event"] == "resource_invoked"
