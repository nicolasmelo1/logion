# SPDX-License-Identifier: MIT
"""Tests for harness adapter ``scope_targets`` ."""

from __future__ import annotations

from pathlib import Path

from cli._harness.claude_code import ClaudeCodeAdapter
from cli._harness.codex import CodexAdapter
from cli._harness.hermes import HermesAdapter
from cli._harness.opencode import OpenCodeAdapter
from cli._harness.pi import PiAdapter
from cli._harness.scopes import (
    ADMIN,
    CUSTOM,
    REPO_CURRENT,
    REPO_ROOT,
    SYSTEM,
    USER,
)


def _make_repo(tmp_path: Path) -> tuple[Path, Path]:
    """Create a repo root with a nested CWD; return (cwd, repo_root)."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    nested = repo / "nested" / "deep"
    nested.mkdir(parents=True)
    return nested, repo


class TestCodexScopeTargets:
    def _adapter(self, tmp_path: Path) -> tuple[CodexAdapter, Path, Path]:
        cwd, repo = _make_repo(tmp_path)
        a = CodexAdapter(cwd=cwd, repo_root=repo, home_dir=tmp_path / "home")
        return a, cwd, repo

    def test_repo_current(self, tmp_path: Path) -> None:
        a, cwd, _ = self._adapter(tmp_path)
        targets = a.scope_targets(REPO_CURRENT)
        assert len(targets) == 1
        assert targets[0].target_path == cwd / ".agents" / "skills"
        assert targets[0].scope_kind == REPO_CURRENT

    def test_repo_root(self, tmp_path: Path) -> None:
        a, _, repo = self._adapter(tmp_path)
        targets = a.scope_targets(REPO_ROOT)
        assert len(targets) == 1
        assert targets[0].target_path == repo / ".agents" / "skills"
        assert targets[0].scope_kind == REPO_ROOT

    def test_user_is_agents_not_codex(self, tmp_path: Path) -> None:
        a, _, _ = self._adapter(tmp_path)
        targets = a.scope_targets(USER)
        assert len(targets) == 1
        # MUST be .agents/skills, NOT .codex/skills (legacy)
        assert (
            targets[0].target_path == tmp_path / "home" / ".agents" / "skills"
        )
        assert ".codex" not in str(targets[0].target_path)

    def test_admin(self, tmp_path: Path) -> None:
        a, _, _ = self._adapter(tmp_path)
        targets = a.scope_targets(ADMIN)
        assert len(targets) == 1
        assert targets[0].target_path == Path("/etc/codex/skills")

    def test_system_is_inventory_only(self, tmp_path: Path) -> None:
        a, _, _ = self._adapter(tmp_path)
        targets = a.scope_targets(SYSTEM)
        assert len(targets) == 1
        # inventory only — no writable install path
        assert targets[0].native_manager == "codex"

    def test_unsupported_scope_returns_empty(self, tmp_path: Path) -> None:
        a, _, _ = self._adapter(tmp_path)
        assert a.scope_targets(CUSTOM) == []

    def test_repo_root_outside_git_returns_empty(self, tmp_path: Path) -> None:
        a = CodexAdapter(
            cwd=tmp_path, repo_root=None, home_dir=tmp_path / "home"
        )
        assert a.scope_targets(REPO_ROOT) == []

    def test_legacy_skill_dir_separate(self, tmp_path: Path) -> None:
        a, _, _ = self._adapter(tmp_path)
        assert a.legacy_skill_dir() == tmp_path / "home" / ".codex" / "skills"


class TestClaudeCodeScopeTargets:
    def _adapter(self, tmp_path: Path) -> tuple[ClaudeCodeAdapter, Path, Path]:
        cwd, repo = _make_repo(tmp_path)
        a = ClaudeCodeAdapter(
            cwd=cwd, repo_root=repo, home_dir=tmp_path / "home"
        )
        return a, cwd, repo

    def test_repo_current(self, tmp_path: Path) -> None:
        a, cwd, _ = self._adapter(tmp_path)
        targets = a.scope_targets(REPO_CURRENT)
        assert len(targets) == 1
        assert targets[0].target_path == cwd / ".claude" / "skills"

    def test_repo_root(self, tmp_path: Path) -> None:
        a, _, repo = self._adapter(tmp_path)
        targets = a.scope_targets(REPO_ROOT)
        assert targets[0].target_path == repo / ".claude" / "skills"

    def test_user(self, tmp_path: Path) -> None:
        a, _, _ = self._adapter(tmp_path)
        targets = a.scope_targets(USER)
        assert (
            targets[0].target_path == tmp_path / "home" / ".claude" / "skills"
        )

    def test_admin_unsupported(self, tmp_path: Path) -> None:
        a, _, _ = self._adapter(tmp_path)
        assert a.scope_targets(ADMIN) == []


class TestHermesScopeTargets:
    def _adapter(self, tmp_path: Path) -> tuple[HermesAdapter, Path, Path]:
        cwd, repo = _make_repo(tmp_path)
        a = HermesAdapter(cwd=cwd, repo_root=repo, home_dir=tmp_path / "home")
        return a, cwd, repo

    def test_user_is_hermes_home(self, tmp_path: Path) -> None:
        a, _, _ = self._adapter(tmp_path)
        targets = a.scope_targets(USER)
        assert len(targets) == 1
        assert (
            targets[0].target_path == tmp_path / "home" / ".hermes" / "skills"
        )
        assert targets[0].native_manager == "hermes"

    def test_repo_root_uses_agents_shared(self, tmp_path: Path) -> None:
        a, _, repo = self._adapter(tmp_path)
        targets = a.scope_targets(REPO_ROOT)
        assert targets[0].target_path == repo / ".agents" / "skills"


class TestOpenCodeScopeTargets:
    def _adapter(self, tmp_path: Path) -> tuple[OpenCodeAdapter, Path, Path]:
        cwd, repo = _make_repo(tmp_path)
        a = OpenCodeAdapter(
            cwd=cwd, repo_root=repo, home_dir=tmp_path / "home"
        )
        return a, cwd, repo

    def test_repo_current(self, tmp_path: Path) -> None:
        a, cwd, _ = self._adapter(tmp_path)
        targets = a.scope_targets(REPO_CURRENT)
        assert (
            targets[0].target_path == cwd / ".config" / "opencode" / "skills"
        )

    def test_user(self, tmp_path: Path) -> None:
        a, _, _ = self._adapter(tmp_path)
        targets = a.scope_targets(USER)
        assert targets[0].target_path == (
            tmp_path / "home" / ".config" / "opencode" / "skills"
        )


class TestPiScopeTargets:
    def _adapter(self, tmp_path: Path) -> tuple[PiAdapter, Path, Path]:
        cwd, repo = _make_repo(tmp_path)
        a = PiAdapter(cwd=cwd, repo_root=repo, home_dir=tmp_path / "home")
        return a, cwd, repo

    def test_user_returns_both_locations(self, tmp_path: Path) -> None:
        a, _, _ = self._adapter(tmp_path)
        targets = a.scope_targets(USER)
        assert len(targets) == 2
        paths = {t.target_path for t in targets}
        assert tmp_path / "home" / ".pi" / "agent" / "skills" in paths
        assert tmp_path / "home" / ".agents" / "skills" in paths

    def test_repo_root_returns_both(self, tmp_path: Path) -> None:
        a, _, repo = self._adapter(tmp_path)
        targets = a.scope_targets(REPO_ROOT)
        assert len(targets) == 2
        paths = {t.target_path for t in targets}
        assert repo / ".agents" / "skills" in paths
        assert repo / ".pi" / "skills" in paths

    def test_repo_current_returns_both(self, tmp_path: Path) -> None:
        a, cwd, _ = self._adapter(tmp_path)
        targets = a.scope_targets(REPO_CURRENT)
        assert len(targets) == 2
        paths = {t.target_path for t in targets}
        assert cwd / ".agents" / "skills" in paths
        assert cwd / ".pi" / "skills" in paths

    def test_name_and_display(self) -> None:
        assert PiAdapter.name == "pi"
        assert PiAdapter.display_name == "Pi"

    def test_admin_unsupported(self, tmp_path: Path) -> None:
        a, _, _ = self._adapter(tmp_path)
        assert a.scope_targets(ADMIN) == []

    def test_is_present_detects_pi_dir(self, tmp_path: Path) -> None:
        a = PiAdapter(home_dir=tmp_path / "home")
        (tmp_path / "home" / ".pi").mkdir(parents=True)
        assert a.is_present() is True

    def test_is_present_detects_agents_dir(self, tmp_path: Path) -> None:
        a = PiAdapter(home_dir=tmp_path / "home")
        (tmp_path / "home" / ".agents").mkdir(parents=True)
        assert a.is_present() is True


class TestNestedReposRemainDistinct:
    def test_same_skill_two_repos_no_collision(self, tmp_path: Path) -> None:
        repo_a = tmp_path / "a"
        repo_b = tmp_path / "b"
        (repo_a / ".git").mkdir(parents=True)
        (repo_b / ".git").mkdir(parents=True)
        a = CodexAdapter(
            cwd=repo_a, repo_root=repo_a, home_dir=tmp_path / "home"
        )
        b = CodexAdapter(
            cwd=repo_b, repo_root=repo_b, home_dir=tmp_path / "home"
        )
        ta = a.scope_targets(REPO_ROOT)[0].target_path
        tb = b.scope_targets(REPO_ROOT)[0].target_path
        assert ta != tb
        assert ta == repo_a / ".agents" / "skills"
        assert tb == repo_b / ".agents" / "skills"
