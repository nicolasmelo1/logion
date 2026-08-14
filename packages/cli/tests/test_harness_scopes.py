# SPDX-License-Identifier: MIT
"""Tests for the scope vocabulary module ."""

from __future__ import annotations

from pathlib import Path

import pytest

from cli._harness.scopes import (
    ADMIN,
    ALIASES,
    CUSTOM,
    GLOBAL,
    PROJECT,
    REPO_CURRENT,
    REPO_PARENT,
    REPO_ROOT,
    SYSTEM,
    USER,
    VALID_SCOPES,
    ScopeTarget,
    canonical_scope,
    default_scope_for_cwd,
    is_valid_scope,
)


class TestScopeVocabulary:
    def test_semantic_constants(self) -> None:
        assert REPO_CURRENT == "repo-current"
        assert REPO_PARENT == "repo-parent"
        assert REPO_ROOT == "repo-root"
        assert USER == "user"
        assert ADMIN == "admin"
        assert SYSTEM == "system"
        assert CUSTOM == "custom"

    def test_alias_constants(self) -> None:
        assert PROJECT == "project"
        assert GLOBAL == "global"

    def test_valid_scopes_contains_all_seven(self) -> None:
        assert (
            frozenset({
                REPO_CURRENT,
                REPO_PARENT,
                REPO_ROOT,
                USER,
                ADMIN,
                SYSTEM,
                CUSTOM,
            })
            == VALID_SCOPES
        )

    def test_aliases_map_to_semantic_values(self) -> None:
        assert ALIASES == {"project": "repo-root", "global": "user"}

    @pytest.mark.parametrize(
        ("alias", "canonical"),
        [
            ("project", "repo-root"),
            ("global", "user"),
            ("repo-root", "repo-root"),
            ("user", "user"),
            ("custom", "custom"),
        ],
    )
    def test_canonical_scope_resolves_aliases(
        self, alias: str, canonical: str
    ) -> None:
        assert canonical_scope(alias) == canonical

    @pytest.mark.parametrize(
        ("scope", "expected"),
        [
            ("repo-current", True),
            ("repo-parent", True),
            ("repo-root", True),
            ("user", True),
            ("admin", True),
            ("system", True),
            ("custom", True),
            ("project", True),  # alias
            ("global", True),  # alias
            ("bogus", False),
            ("", False),
        ],
    )
    def test_is_valid_scope(self, scope: str, expected: bool) -> None:
        assert is_valid_scope(scope) is expected


class TestDefaultScopeForCwd:
    def test_inside_git_repo_returns_repo_root(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        sub = tmp_path / "nested" / "deep"
        sub.mkdir(parents=True)
        assert default_scope_for_cwd(sub) == "repo-root"

    def test_outside_git_repo_returns_user(self, tmp_path: Path) -> None:
        # tmp_path has no .git
        assert default_scope_for_cwd(tmp_path) == "user"

    def test_outside_git_default_is_explicit_user_scope(
        self, tmp_path: Path
    ) -> None:
        assert default_scope_for_cwd(tmp_path) == USER


class TestScopeTarget:
    def test_construction_and_fields(self, tmp_path: Path) -> None:
        t = ScopeTarget(
            scope_kind="repo-root",
            scope_root=tmp_path,
            target_path=tmp_path / ".agents" / "skills",
            native_manager=None,
            exists=False,
        )
        assert t.scope_kind == "repo-root"
        assert t.scope_root == tmp_path
        assert t.target_path == tmp_path / ".agents" / "skills"
        assert t.native_manager is None
        assert t.exists is False

    def test_is_frozen(self, tmp_path: Path) -> None:
        t = ScopeTarget(
            scope_kind="user",
            scope_root=tmp_path,
            target_path=tmp_path / "skills",
            native_manager=None,
            exists=False,
        )
        with pytest.raises(AttributeError):
            t.scope_kind = "admin"  # type: ignore[misc]
