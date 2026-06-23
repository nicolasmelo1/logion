# SPDX-License-Identifier: MIT
"""Tests for the OpenCode harness adapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli._harness.base import HarnessConfigError
from cli._harness.opencode import OpenCodeAdapter, _autopost_pattern

PATTERN = "logion courses report-usage*"


def _adapter(tmp_path: Path) -> OpenCodeAdapter:
    return OpenCodeAdapter(
        project_dir=tmp_path / "proj",
        home_dir=tmp_path / "home",
    )


def test_pattern_is_rendered_from_autopost_command() -> None:
    assert _autopost_pattern() == PATTERN


def test_config_path_scopes(tmp_path: Path) -> None:
    a = _adapter(tmp_path)
    assert a.config_path("project") == (tmp_path / "proj" / "opencode.json")
    assert a.config_path("global") == (
        tmp_path / "home" / ".config" / "opencode" / "opencode.json"
    )
    with pytest.raises(ValueError, match="unknown scope"):
        a.config_path("bogus")


def test_grant_creates_file_with_bash_permission(
    tmp_path: Path,
) -> None:
    a = _adapter(tmp_path)
    result = a.grant("global")
    assert result.changed is True
    assert result.already is False
    data = json.loads(result.path.read_text())
    assert data["permission"]["bash"][PATTERN] == "allow"


def test_grant_is_idempotent(tmp_path: Path) -> None:
    a = _adapter(tmp_path)
    a.grant("global")
    second = a.grant("global")
    assert second.changed is False
    assert second.already is True
    data = json.loads(second.path.read_text())
    assert data["permission"]["bash"][PATTERN] == "allow"


def test_grant_preserves_existing_config(tmp_path: Path) -> None:
    a = _adapter(tmp_path)
    path = a.config_path("project")
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({
            "$schema": "https://opencode.ai/config.json",
            "permission": {
                "bash": {"git *": "allow"},
                "edit": "deny",
            },
        })
    )
    a.grant("project")
    data = json.loads(path.read_text())
    assert data["$schema"] == "https://opencode.ai/config.json"
    assert data["permission"]["edit"] == "deny"
    assert data["permission"]["bash"]["git *"] == "allow"
    assert data["permission"]["bash"][PATTERN] == "allow"


def test_grant_upgrades_string_bash_to_object(tmp_path: Path) -> None:
    """``"bash": "ask"`` should be upgraded to a granular object."""
    a = _adapter(tmp_path)
    path = a.config_path("global")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"permission": {"bash": "ask"}}))
    a.grant("global")
    data = json.loads(path.read_text())
    assert data["permission"]["bash"]["*"] == "ask"
    assert data["permission"]["bash"][PATTERN] == "allow"


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
    assert path.read_text() == "{not valid json"


def test_jsonc_comments_are_stripped(tmp_path: Path) -> None:
    """OpenCode uses JSONC; comments must not break parsing."""
    a = _adapter(tmp_path)
    path = a.config_path("global")
    path.parent.mkdir(parents=True)
    path.write_text('{\n  // a comment\n  "permission": {}\n}\n')
    result = a.grant("global")
    assert result.changed is True
    data = json.loads(result.path.read_text())
    assert data["permission"]["bash"][PATTERN] == "allow"


def test_is_present_detects_opencode_dir(tmp_path: Path) -> None:
    a = OpenCodeAdapter(
        project_dir=tmp_path / "proj", home_dir=tmp_path / "home"
    )
    (tmp_path / "home" / ".config" / "opencode").mkdir(parents=True)
    assert a.is_present() is True
