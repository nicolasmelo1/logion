# SPDX-License-Identifier: MIT
"""Tests for the Claude Code harness adapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli._harness import ClaudeCodeAdapter, get_adapter
from cli._harness.base import AUTOPOST_COMMAND, HarnessConfigError

MATCHER = "Bash(logion courses report-usage:*)"


def _adapter(tmp_path: Path) -> ClaudeCodeAdapter:
    return ClaudeCodeAdapter(
        project_dir=tmp_path / "proj",
        home_dir=tmp_path / "home",
    )


def test_matcher_is_rendered_from_autopost_command() -> None:
    """The matcher derives from AUTOPOST_COMMAND, not a hardcoded string."""
    assert AUTOPOST_COMMAND == ("logion", "courses", "report-usage")
    assert f"Bash({' '.join(AUTOPOST_COMMAND)}:*)" == MATCHER


def test_registry_resolves_claude_code() -> None:
    assert isinstance(get_adapter("claude-code"), ClaudeCodeAdapter)
    assert get_adapter("nonexistent") is None


def test_config_path_scopes(tmp_path: Path) -> None:
    a = _adapter(tmp_path)
    assert a.config_path("project") == (
        tmp_path / "proj" / ".claude" / "settings.json"
    )
    assert a.config_path("global") == (
        tmp_path / "home" / ".claude" / "settings.json"
    )
    with pytest.raises(ValueError, match="unknown scope"):
        a.config_path("bogus")


def test_grant_creates_file_with_allow(tmp_path: Path) -> None:
    a = _adapter(tmp_path)
    result = a.grant("global")
    assert result.changed is True
    assert result.already is False
    data = json.loads(result.path.read_text())
    assert data["permissions"]["allow"] == [MATCHER]


def test_grant_is_idempotent(tmp_path: Path) -> None:
    a = _adapter(tmp_path)
    a.grant("global")
    second = a.grant("global")
    assert second.changed is False
    assert second.already is True
    data = json.loads(second.path.read_text())
    # Not duplicated.
    assert data["permissions"]["allow"].count(MATCHER) == 1


def test_grant_preserves_existing_settings(tmp_path: Path) -> None:
    a = _adapter(tmp_path)
    path = a.config_path("project")
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({
            "model": "opus",
            "permissions": {"allow": ["Bash(ls:*)"], "deny": ["Bash(rm:*)"]},
        })
    )
    a.grant("project")
    data = json.loads(path.read_text())
    assert data["model"] == "opus"
    assert data["permissions"]["deny"] == ["Bash(rm:*)"]
    assert data["permissions"]["allow"] == ["Bash(ls:*)", MATCHER]


def test_is_granted(tmp_path: Path) -> None:
    a = _adapter(tmp_path)
    assert a.is_granted("global") is False
    a.grant("global")
    assert a.is_granted("global") is True


def test_revoke_removes_and_is_idempotent(tmp_path: Path) -> None:
    a = _adapter(tmp_path)
    a.grant("global")
    first = a.revoke("global")
    assert first.changed is True
    assert a.is_granted("global") is False
    second = a.revoke("global")
    assert second.changed is False
    assert second.already is True


def test_revoke_missing_file_is_noop(tmp_path: Path) -> None:
    a = _adapter(tmp_path)
    result = a.revoke("project")
    assert result.changed is False
    assert result.already is True


def test_malformed_json_refuses_to_clobber(tmp_path: Path) -> None:
    a = _adapter(tmp_path)
    path = a.config_path("global")
    path.parent.mkdir(parents=True)
    path.write_text("{not valid json")
    with pytest.raises(HarnessConfigError, match="cannot parse"):
        a.grant("global")
    # File left untouched.
    assert path.read_text() == "{not valid json"


def test_non_object_permissions_refuses(tmp_path: Path) -> None:
    a = _adapter(tmp_path)
    path = a.config_path("global")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"permissions": ["oops"]}))
    with pytest.raises(HarnessConfigError, match="not an object"):
        a.grant("global")


def test_allow_not_a_list_refuses(tmp_path: Path) -> None:
    a = _adapter(tmp_path)
    path = a.config_path("global")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"permissions": {"allow": "nope"}}))
    with pytest.raises(HarnessConfigError, match="not a list"):
        a.grant("global")


def test_is_present_detects_claude_dir(tmp_path: Path) -> None:
    a = ClaudeCodeAdapter(
        project_dir=tmp_path / "proj", home_dir=tmp_path / "home"
    )
    (tmp_path / "home" / ".claude").mkdir(parents=True)
    assert a.is_present() is True
