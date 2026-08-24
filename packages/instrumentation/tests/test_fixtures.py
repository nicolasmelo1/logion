# SPDX-License-Identifier: MIT
"""Tests for client fixtures under ``packages/instrumentation/fixtures/``.

Verifies that the Claude Code, Codex, and Hermes fixture files exist,
are valid JSON, and contain the expected event-shape markers.
"""

from __future__ import annotations

import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _load(name: str) -> dict[str, object]:
    path = FIXTURES / name
    assert path.is_file(), f"Fixture not found: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


# --- Claude Code -----------------------------------------------------------


def test_claude_code_fixture_exists() -> None:
    data = _load("claude-code/post-tool-use.json")
    assert isinstance(data, dict)


def test_claude_code_fixture_has_hook_event() -> None:
    data = _load("claude-code/post-tool-use.json")
    assert data["hook_event_name"] == "PostToolUse"


def test_claude_code_fixture_has_tool_name() -> None:
    data = _load("claude-code/post-tool-use.json")
    assert "tool_name" in data


def test_claude_code_fixture_has_session_id() -> None:
    data = _load("claude-code/post-tool-use.json")
    assert "session_id" in data


# --- Codex -----------------------------------------------------------------


def test_codex_fixture_exists() -> None:
    data = _load("codex/post-tool-use.json")
    assert isinstance(data, dict)


def test_codex_fixture_has_hook_event() -> None:
    data = _load("codex/post-tool-use.json")
    assert data["hook_event_name"] == "PostToolUse"


def test_codex_fixture_has_tool_name() -> None:
    data = _load("codex/post-tool-use.json")
    assert "tool_name" in data


# --- Hermes ----------------------------------------------------------------


def test_hermes_fixture_exists() -> None:
    data = _load("hermes/skill-loaded.json")
    assert isinstance(data, dict)


def test_hermes_fixture_is_marked_synthetic() -> None:
    data = _load("hermes/skill-loaded.json")
    assert data.get("_logion_fixture") is True


def test_hermes_fixture_has_action_loaded() -> None:
    data = _load("hermes/skill-loaded.json")
    assert data["action"] == "loaded"


def test_hermes_fixture_has_skill_name() -> None:
    data = _load("hermes/skill-loaded.json")
    assert isinstance(data["skill_name"], str)
    assert len(data["skill_name"]) > 0


def test_hermes_fixture_has_scope() -> None:
    data = _load("hermes/skill-loaded.json")
    assert "scope" in data


def test_hermes_fixture_has_session_id() -> None:
    data = _load("hermes/skill-loaded.json")
    assert "session_id" in data
