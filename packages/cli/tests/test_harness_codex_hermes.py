# SPDX-License-Identifier: MIT
"""Tests for Codex and Hermes harness adapters."""

from __future__ import annotations

from pathlib import Path

from cli._harness.codex import CodexAdapter
from cli._harness.hermes import HermesAdapter


class TestCodexAdapter:
    def _adapter(self, tmp_path: Path) -> CodexAdapter:
        return CodexAdapter(
            project_dir=tmp_path / "proj", home_dir=tmp_path / "home"
        )

    def test_skill_dir(self, tmp_path: Path) -> None:
        assert (
            self._adapter(tmp_path).skill_dir()
            == tmp_path / "home" / ".agents" / "skills"
        )

    def test_legacy_skill_dir(self, tmp_path: Path) -> None:
        assert (
            self._adapter(tmp_path).legacy_skill_dir()
            == tmp_path / "home" / ".codex" / "skills"
        )

    def test_config_path_is_toml(self, tmp_path: Path) -> None:
        assert (
            self._adapter(tmp_path).config_path("global")
            == tmp_path / "home" / ".codex" / "config.toml"
        )

    def test_is_present_detects_codex_dir(self, tmp_path: Path) -> None:
        adapter = self._adapter(tmp_path)
        (tmp_path / "home" / ".codex").mkdir(parents=True)
        assert adapter.is_present() is True

    def test_grant_is_noop(self, tmp_path: Path) -> None:
        result = self._adapter(tmp_path).grant("global")
        assert result.changed is False
        assert result.already is True
        assert not result.path.exists()

    def test_revoke_is_noop(self, tmp_path: Path) -> None:
        result = self._adapter(tmp_path).revoke("global")
        assert result.changed is False
        assert result.already is True
        assert not result.path.exists()

    def test_is_granted_returns_false(self, tmp_path: Path) -> None:
        assert self._adapter(tmp_path).is_granted("global") is False


class TestHermesAdapter:
    def _adapter(self, tmp_path: Path) -> HermesAdapter:
        return HermesAdapter(
            project_dir=tmp_path / "proj", home_dir=tmp_path / "home"
        )

    def test_skill_dir(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv("HERMES_HOME", raising=False)
        assert (
            self._adapter(tmp_path).skill_dir()
            == tmp_path / "home" / ".hermes" / "skills"
        )

    def test_active_profile_home_from_environment(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        profile_home = tmp_path / "profiles" / "work"
        monkeypatch.setenv("HERMES_HOME", str(profile_home))
        adapter = self._adapter(tmp_path)
        assert adapter.skill_dir() == profile_home / "skills"
        assert adapter.config_path("user") == profile_home / "config.yaml"

    def test_config_path_is_yaml(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv("HERMES_HOME", raising=False)
        assert (
            self._adapter(tmp_path).config_path("global")
            == tmp_path / "home" / ".hermes" / "config.yaml"
        )

    def test_is_present_detects_hermes_dir(self, tmp_path: Path) -> None:
        adapter = self._adapter(tmp_path)
        (tmp_path / "home" / ".hermes").mkdir(parents=True)
        assert adapter.is_present() is True

    def test_grant_is_noop(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv("HERMES_HOME", raising=False)
        result = self._adapter(tmp_path).grant("global")
        assert result.changed is False
        assert result.already is True
        assert not result.path.exists()

    def test_revoke_is_noop(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.delenv("HERMES_HOME", raising=False)
        result = self._adapter(tmp_path).revoke("global")
        assert result.changed is False
        assert result.already is True
        assert not result.path.exists()

    def test_is_granted_returns_false(self, tmp_path: Path) -> None:
        assert self._adapter(tmp_path).is_granted("global") is False


class TestHermesObservation:
    def _adapter(self, tmp_path: Path) -> HermesAdapter:
        return HermesAdapter(home_dir=tmp_path / "home")

    @staticmethod
    def _assert_plugin(plugin: Path) -> None:
        source = (plugin / "__init__.py").read_text(encoding="utf-8")
        assert "on_skill_lifecycle" in source
        assert '"logion"' in source
        assert '"usage"' in source
        assert '"observe"' in source
        compile(source, str(plugin / "__init__.py"), "exec")

    def test_enable_installs_receipt_backed_observer_without_clobbering_config(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.delenv("HERMES_HOME", raising=False)
        adapter = self._adapter(tmp_path)
        config = tmp_path / "home" / ".hermes" / "config.yaml"
        config.parent.mkdir(parents=True)
        config.write_text(
            """model:
  default: gpt-5.4
plugins:
  enabled:
    - mine
  disabled:
    - logion-observer
""",
            encoding="utf-8",
        )
        plan = adapter.plan_observation("user")
        assert plan.supported is True
        assert "logion-observer" in plan.diff
        assert not (config.parent / "plugins" / "logion-observer").exists()
        result = adapter.enable_observation("user")
        plugin = config.parent / "plugins" / "logion-observer"
        assert result.changed is True
        text = config.read_text(encoding="utf-8")
        assert "default: gpt-5.4" in text
        assert "- mine" in text
        assert "- logion-observer" in text
        assert "disabled: []" in text
        self._assert_plugin(plugin)
        assert adapter.plan_observation("user").already is True

    def test_enable_is_idempotent_without_rewriting_plugin_or_config(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.delenv("HERMES_HOME", raising=False)
        adapter = self._adapter(tmp_path)
        config = tmp_path / "home" / ".hermes" / "config.yaml"
        adapter.enable_observation("user")
        plugin = config.parent / "plugins" / "logion-observer"
        plugin_mtime = (plugin / "__init__.py").stat().st_mtime_ns
        config_mtime = config.stat().st_mtime_ns
        repeated = adapter.enable_observation("user")
        assert repeated.already is True
        assert repeated.changed is False
        assert (plugin / "__init__.py").stat().st_mtime_ns == plugin_mtime
        assert config.stat().st_mtime_ns == config_mtime

    def test_repo_scope_is_unsupported_until_hermes_has_scope_aware_config(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.delenv("HERMES_HOME", raising=False)
        adapter = HermesAdapter(
            home_dir=tmp_path / "home",
            cwd=tmp_path / "repo",
            repo_root=tmp_path / "repo",
        )
        plan = adapter.plan_observation("repo-root")
        assert plan.supported is False
        assert plan.changed is False

    def test_disable_without_logion_state_is_a_noop(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.delenv("HERMES_HOME", raising=False)
        adapter = self._adapter(tmp_path)
        result = adapter.disable_observation("user")
        assert result.path is not None
        assert result.changed is False
        assert result.already is True
        assert not result.path.exists()

    def test_disable_removes_only_logion_plugin_and_preserves_user_config(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        monkeypatch.delenv("HERMES_HOME", raising=False)
        adapter = self._adapter(tmp_path)
        config = tmp_path / "home" / ".hermes" / "config.yaml"
        config.parent.mkdir(parents=True)
        config.write_text(
            "plugins:\n  enabled:\n    - mine\n", encoding="utf-8"
        )
        adapter.enable_observation("user")
        result = adapter.disable_observation("user")
        assert result.changed is True
        text = config.read_text(encoding="utf-8")
        assert "- mine" in text
        assert "logion-observer" not in text
        assert not (config.parent / "plugins" / "logion-observer").exists()
