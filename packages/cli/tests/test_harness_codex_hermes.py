# SPDX-License-Identifier: MIT
"""Tests for Codex and Hermes harness adapters.

Both have no per-command permission list, so grant/revoke are no-ops.
The tests verify skill_dir, config_path, is_present, and the no-op
grant/revoke behaviour.
"""

from __future__ import annotations

from pathlib import Path

from cli._harness.codex import CodexAdapter
from cli._harness.hermes import HermesAdapter


class TestCodexAdapter:
    def _adapter(self, tmp_path: Path) -> CodexAdapter:
        return CodexAdapter(
            project_dir=tmp_path / "proj",
            home_dir=tmp_path / "home",
        )

    def test_skill_dir(self, tmp_path: Path) -> None:
        a = self._adapter(tmp_path)
        assert a.skill_dir() == tmp_path / "home" / ".codex" / "skills"

    def test_config_path_is_toml(self, tmp_path: Path) -> None:
        a = self._adapter(tmp_path)
        assert a.config_path("global") == (
            tmp_path / "home" / ".codex" / "config.toml"
        )

    def test_is_present_detects_codex_dir(self, tmp_path: Path) -> None:
        a = self._adapter(tmp_path)
        (tmp_path / "home" / ".codex").mkdir(parents=True)
        assert a.is_present() is True

    def test_grant_is_noop(self, tmp_path: Path) -> None:
        a = self._adapter(tmp_path)
        result = a.grant("global")
        assert result.changed is False
        assert result.already is True
        # No file was created.
        assert not result.path.exists()

    def test_revoke_is_noop(self, tmp_path: Path) -> None:
        a = self._adapter(tmp_path)
        result = a.revoke("global")
        assert result.changed is False
        assert result.already is True

    def test_is_granted_returns_false(self, tmp_path: Path) -> None:
        a = self._adapter(tmp_path)
        assert a.is_granted("global") is False


class TestHermesAdapter:
    def _adapter(self, tmp_path: Path) -> HermesAdapter:
        return HermesAdapter(
            project_dir=tmp_path / "proj",
            home_dir=tmp_path / "home",
        )

    def test_skill_dir(self, tmp_path: Path) -> None:
        a = self._adapter(tmp_path)
        assert a.skill_dir() == tmp_path / "home" / ".hermes" / "skills"

    def test_config_path_is_yaml(self, tmp_path: Path) -> None:
        a = self._adapter(tmp_path)
        assert a.config_path("global") == (
            tmp_path / "home" / ".hermes" / "config.yaml"
        )

    def test_is_present_detects_hermes_dir(self, tmp_path: Path) -> None:
        a = self._adapter(tmp_path)
        (tmp_path / "home" / ".hermes").mkdir(parents=True)
        assert a.is_present() is True

    def test_grant_is_noop(self, tmp_path: Path) -> None:
        a = self._adapter(tmp_path)
        result = a.grant("global")
        assert result.changed is False
        assert result.already is True
        # No file was created.
        assert not result.path.exists()

    def test_revoke_is_noop(self, tmp_path: Path) -> None:
        a = self._adapter(tmp_path)
        result = a.revoke("global")
        assert result.changed is False
        assert result.already is True

    def test_is_granted_returns_false(self, tmp_path: Path) -> None:
        a = self._adapter(tmp_path)
        assert a.is_granted("global") is False
