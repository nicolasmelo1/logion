# SPDX-License-Identifier: MIT
"""Tests for the release orchestrator."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts import release_orchestrator as release_orchestrator_module
from scripts.release_orchestrator import (
    _PACKAGE_CONFIG,
    MergedPR,
    ReleaseExecutor,
    ReleasePlanner,
    _collect_merged_prs,
    _find_last_release_tag,
    _format_changelog_entry,
    _porcelain_paths,
    plan_to_json,
    update_changelog_file,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


class _FakeRunner:
    """CommandRunner mock that records calls and returns canned output."""

    def __init__(
        self,
        responses: dict[str, str] | None = None,
    ) -> None:
        self.calls: list[list[str]] = []
        self._responses = responses or {}

    def run(
        self,
        args: list[str],
        *,
        cwd: Path | None = None,  # noqa: ARG002
        check: bool = True,  # noqa: ARG002
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(args))
        full_key = " ".join(args)
        key = full_key if full_key in self._responses else " ".join(args[:3])
        stdout = self._responses.get(key, "")
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=stdout,
            stderr="",
        )


def test_plan_includes_all_four_package_tags() -> None:
    """Plan has skillmap, client, CLI, and companion tags."""
    planner = ReleasePlanner(repo_root=REPO_ROOT)
    plan = planner.load("0.1.99", publish_store=False)
    names = {p.name for p in plan.packages}
    assert names == {"skillmap", "client", "cli", "companion"}
    tags = set(plan.tags_to_create)
    assert "logion-skillmap-v0.1.99" in tags
    assert "logion-client-v0.1.99" in tags
    assert "logion-cli-v0.1.99" in tags
    assert "logion-companion-v0.1.99" in tags


def test_version_bump_targets_pass_config_before_subcommand() -> None:
    """semantic-release global config option precedes its subcommand."""
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    for package in ("cli", "client", "agent-companion"):
        expected = (
            f"uv run semantic-release -c packages/{package}/pyproject.toml "
            "version"
        )
        assert expected in makefile


def test_plan_normalizes_leading_v_for_tags() -> None:
    """Friendly v-prefixed input must not create vv-prefixed tags."""
    planner = ReleasePlanner(repo_root=REPO_ROOT)
    plan = planner.load("v0.1.99", publish_store=False)
    tags = set(plan.tags_to_create)
    assert "logion-skillmap-v0.1.99" in tags
    assert "logion-client-v0.1.99" in tags
    assert "logion-cli-v0.1.99" in tags
    assert "logion-companion-v0.1.99" in tags


def test_plan_requires_a_valid_pep_440_version() -> None:
    """Invalid version errors name the PEP 440 scheme used by the planner."""
    planner = ReleasePlanner(repo_root=REPO_ROOT)
    with pytest.raises(ValueError, match="PEP 440"):
        planner.load("not-a-version", publish_store=False)


def test_preflight_rejects_dirty_worktree() -> None:
    """Dirty worktree with unexpected files fails validation."""
    runner = _FakeRunner()
    runner._responses = {
        "git status --porcelain": " M packages/cli/cli/foo.py\n",
    }
    planner = ReleasePlanner(repo_root=REPO_ROOT, runner=runner)
    try:
        planner.validate_clean_or_release_only_worktree()
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected RuntimeError for dirty worktree")


def test_preflight_allows_named_smoke_findings() -> None:
    """Smoke findings file is an allowed dirty path."""
    runner = _FakeRunner()
    runner._responses = {
        "git status --porcelain": (" M release-smoke-findings.md\n"),
    }
    planner = ReleasePlanner(repo_root=REPO_ROOT, runner=runner)
    # Should not raise.
    planner.validate_clean_or_release_only_worktree()


def test_release_dry_run_does_not_run_git_push() -> None:
    """Dry-run mode does not execute git push."""
    plan = ReleasePlanner(
        repo_root=REPO_ROOT,
    ).load("0.1.99", publish_store=False)
    # Create the smoke findings file so preflight passes.
    plan.smoke_findings_path.parent.mkdir(parents=True, exist_ok=True)
    plan.smoke_findings_path.write_text(
        '---\nrelease_version: "0.1.99"\napi_base_url: ""\n'
        'cli_version: ""\nharnesses:\n  - codex\n  - claude-code\n'
        "  - opencode\n---\n",
        encoding="utf-8",
    )
    runner = _FakeRunner()
    executor = ReleaseExecutor(plan, runner=runner)
    try:
        executor.execute(dry_run=True)
        # No git push command should have been issued.
        push_calls = [c for c in runner.calls if "push" in c and "git" in c]
        assert push_calls == [], (
            f"Dry-run should not push, got: {push_calls}",
        )
    finally:
        plan.smoke_findings_path.unlink(missing_ok=True)


def test_release_checks_refresh_lock_after_version_bump() -> None:
    """Mutable releases update uv.lock after bumping package versions."""
    plan = ReleasePlanner(repo_root=REPO_ROOT).load(
        "0.1.99",
        publish_store=False,
    )
    runner = _FakeRunner()
    executor = ReleaseExecutor(plan, runner=runner)
    executor.run_checks()
    assert runner.calls[0] == ["uv", "lock"]


def test_release_resume_skips_commit_tag_and_push(monkeypatch) -> None:
    """A failed store publish can be rerun after commit/tags exist."""
    version = "0.1.99"

    def fake_read_pyproject_version(_path: str) -> str:
        return version

    monkeypatch.setattr(
        release_orchestrator_module,
        "_read_pyproject_version",
        fake_read_pyproject_version,
    )
    plan = ReleasePlanner(repo_root=REPO_ROOT).load(
        version,
        publish_store=True,
    )
    plan.smoke_findings_path.parent.mkdir(parents=True, exist_ok=True)
    plan.smoke_findings_path.write_text(
        '---\nrelease_version: "0.1.99"\napi_base_url: ""\n'
        'cli_version: ""\nharnesses:\n  - codex\n  - claude-code\n'
        "  - opencode\n---\n",
        encoding="utf-8",
    )
    runner = _FakeRunner(
        {f"git tag -l {tag}": tag for tag in plan.tags_to_create},
    )
    executor = ReleaseExecutor(plan, runner=runner)
    try:
        result = executor.execute()
    finally:
        plan.smoke_findings_path.unlink(missing_ok=True)

    assert result["resumed"] is True
    assert not any(call[:2] == ["git", "commit"] for call in runner.calls)
    assert not any(call[:2] == ["git", "push"] for call in runner.calls)
    assert not any(
        call[:2] == ["git", "tag"] and "-a" in call for call in runner.calls
    )
    assert any("scripts/release_store.py" in call for call in runner.calls)


def test_release_executor_leaves_github_releases_to_actions() -> None:
    """Tag-triggered GitHub Actions own release asset publication."""
    assert not hasattr(ReleaseExecutor, "create_github_releases")


def test_release_creates_expected_tag_commands() -> None:
    """Tags match the expected ``logion-<pkg>-v<version>`` format."""
    planner = ReleasePlanner(repo_root=REPO_ROOT)
    plan = planner.load("0.2.0", publish_store=False)
    for tag in plan.tags_to_create:
        assert tag.startswith("logion-"), tag
        assert tag.endswith("-v0.2.0"), tag
    # Confirm every public package has a tag.
    assert len(plan.tags_to_create) == len(_PACKAGE_CONFIG)


def test_development_plan_does_not_mutate_install_manifests() -> None:
    """A `.devN` release is installed explicitly, never through a manifest."""
    plan = ReleasePlanner(repo_root=REPO_ROOT).load(
        "0.2.0.dev1",
        publish_store=False,
    )
    assert plan.manifest_outputs == ()


def test_development_plan_rejects_store_publication() -> None:
    """Development companion bundles cannot claim a store publication."""
    planner = ReleasePlanner(repo_root=REPO_ROOT)
    with pytest.raises(ValueError, match="cannot publish"):
        planner.load("0.2.0.dev1", publish_store=True)


def test_development_release_skips_manifest_commands() -> None:
    """The executor leaves stable/latest installer manifests untouched."""
    plan = ReleasePlanner(repo_root=REPO_ROOT).load(
        "0.2.0.dev1",
        publish_store=False,
    )
    runner = _FakeRunner()
    ReleaseExecutor(plan, runner=runner).run_checks()
    assert ["make", "release-manifest"] not in runner.calls
    assert ["make", "release-manifest-check"] not in runner.calls


def test_release_regenerates_stable_and_latest_manifests() -> None:
    """Both stable and latest manifests are in the plan."""
    plan = ReleasePlanner(
        repo_root=REPO_ROOT,
    ).load("0.1.99", publish_store=False)
    names = {p.name for p in plan.manifest_outputs}
    assert "manifest-stable.json" in names
    assert "manifest-latest.json" in names


def test_release_publish_store_is_opt_in() -> None:
    """publish_store defaults to False."""
    plan = ReleasePlanner(
        repo_root=REPO_ROOT,
    ).load("0.1.99", publish_store=False)
    assert plan.publish_store is False


def test_plan_to_json_round_trips() -> None:
    """JSON plan output includes all package tags."""
    plan = ReleasePlanner(
        repo_root=REPO_ROOT,
    ).load("0.1.99", publish_store=True)
    import json

    data = json.loads(plan_to_json(plan))
    assert data["version"] == "0.1.99"
    assert data["publish_store"] is True
    assert len(data["tags_to_create"]) == 4


def test_plan_uses_smoke_findings_env(monkeypatch) -> None:
    """GitHub Actions can keep smoke evidence outside the repo root."""
    smoke_path = "/tmp/logion-release-smoke.md"
    monkeypatch.setenv("SMOKE_FINDINGS", smoke_path)
    plan = ReleasePlanner(repo_root=REPO_ROOT).load(
        "0.1.99",
        publish_store=False,
    )
    assert plan.smoke_findings_path == Path(smoke_path)


def test_porcelain_paths_handles_rename_entries() -> None:
    """NUL-delimited porcelain rename output reports the new path only."""
    stdout = (
        "R  release-smoke-findings.md\0"
        "old-release-smoke-findings.md\0"
        " M packages/cli/cli/foo.py\0"
    )
    assert _porcelain_paths(stdout) == (
        "release-smoke-findings.md",
        "packages/cli/cli/foo.py",
    )


def test_preflight_allows_renamed_smoke_findings() -> None:
    """Smoke findings rename is parsed from porcelain -z without old path."""
    runner = _FakeRunner()
    runner._responses = {
        "git status --porcelain": (
            "R  release-smoke-findings.md\0old-release-smoke-findings.md\0"
        ),
    }
    planner = ReleasePlanner(repo_root=REPO_ROOT, runner=runner)
    planner.validate_clean_or_release_only_worktree()


# ── changelog tests ──────────────────────────────────────────────


def test_find_last_release_tag_returns_most_recent() -> None:
    """_find_last_release_tag returns the newest logion-cli-v* tag."""
    runner = _FakeRunner({
        "git tag --sort=-creatordate --list logion-cli-v*": (
            "logion-cli-v0.1.11\nlogion-cli-v0.1.10\n"
        ),
    })
    tag = _find_last_release_tag(runner, REPO_ROOT)
    assert tag == "logion-cli-v0.1.11"


def test_find_last_release_tag_returns_none_when_empty() -> None:
    """No tags returns None."""
    runner = _FakeRunner({})
    tag = _find_last_release_tag(runner, REPO_ROOT)
    assert tag is None


def test_collect_merged_prs_parses_squash_commits() -> None:
    """_collect_merged_prs extracts PR number, author, type, scope."""
    runner = _FakeRunner({
        "git log logion-cli-v0.1.11..HEAD": (
            "Nicolas Leal|fix(update): clean installer output (#132)\n"
            "M'ael|fix(cli): align Codex skill path (#131)\n"
            "Nicolas Melo|chore(release): strip bundle root\n"
            "Nicolas Melo|feat(cli): add prune command (#130)\n"
        ),
    })
    prs = _collect_merged_prs(runner, REPO_ROOT, "logion-cli-v0.1.11")
    # The chore commit without a PR number is skipped.
    assert len(prs) == 3
    assert prs[0].number == 132
    assert prs[0].author == "Nicolas Leal"
    assert prs[0].commit_type == "fix"
    assert prs[0].scope == "update"
    assert prs[0].subject == "clean installer output"
    assert prs[1].number == 131
    assert prs[1].author == "M'ael"
    assert prs[1].commit_type == "fix"
    assert prs[1].scope == "cli"
    assert prs[2].number == 130
    assert prs[2].commit_type == "feat"


def test_collect_merged_prs_empty_when_no_tag() -> None:
    """No previous tag scans all of HEAD."""
    runner = _FakeRunner({
        "git log HEAD": "Nicolas|fix(core): something (#1)\n",
    })
    prs = _collect_merged_prs(runner, REPO_ROOT, None)
    assert len(prs) == 1
    assert prs[0].number == 1


def test_format_changelog_entry_groups_by_type() -> None:
    """Entry has section headings and credits contributors."""
    prs = [
        MergedPR(
            number=131,
            author="M'ael",
            commit_type="fix",
            scope="cli",
            subject="align Codex skill path",
        ),
        MergedPR(
            number=130,
            author="Nicolas",
            commit_type="feat",
            scope="cli",
            subject="add prune command",
        ),
        MergedPR(
            number=132,
            author="Nicolas",
            commit_type="fix",
            scope="update",
            subject="clean installer output",
        ),
    ]
    entry = _format_changelog_entry("0.2.0", prs)
    assert "## 0.2.0" in entry
    assert "### Features" in entry
    assert "### Bug Fixes" in entry
    # Scope is bolded.
    assert "**cli**: " in entry
    # PR numbers appear.
    assert "#131" in entry
    assert "#130" in entry
    assert "#132" in entry
    # Contributors line includes both authors.
    assert "@M'ael" in entry
    assert "@Nicolas" in entry


def test_format_changelog_entry_skips_empty_sections() -> None:
    """Sections with no PRs are not emitted."""
    prs = [
        MergedPR(
            number=1,
            author="Alice",
            commit_type="fix",
            scope=None,
            subject="bug fix",
        ),
    ]
    entry = _format_changelog_entry("0.1.0", prs)
    assert "### Bug Fixes" in entry
    assert "### Features" not in entry
    assert "### Performance" not in entry


def test_format_changelog_entry_handles_no_scope() -> None:
    """PRs without a scope don't get a bold prefix."""
    prs = [
        MergedPR(
            number=1,
            author="Alice",
            commit_type="fix",
            scope=None,
            subject="bug fix",
        ),
    ]
    entry = _format_changelog_entry("0.1.0", prs)
    assert "- bug fix (#1) — @Alice" in entry
    assert "**None**" not in entry


def test_update_changelog_file_prepends_after_header(tmp_path: Path) -> None:
    """New entry is inserted after the file header, before old sections."""
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "# Changelog\n\nHeader text.\n\n## 0.1.0\n\n- old entry\n",
        encoding="utf-8",
    )
    prs = [
        MergedPR(
            number=131,
            author="M'ael",
            commit_type="fix",
            scope="cli",
            subject="align Codex path",
        ),
    ]
    update_changelog_file(changelog, "0.2.0", prs)
    content = changelog.read_text(encoding="utf-8")
    # Header is preserved.
    assert content.startswith("# Changelog")
    # New entry comes before old.
    assert content.index("## 0.2.0") < content.index("## 0.1.0")
    assert "align Codex path" in content


def test_update_changelog_file_creates_when_missing(
    tmp_path: Path,
) -> None:
    """Missing changelog file is created with just the entry."""
    changelog = tmp_path / "CHANGELOG.md"
    prs = [
        MergedPR(
            number=1,
            author="Alice",
            commit_type="feat",
            scope=None,
            subject="initial",
        ),
    ]
    update_changelog_file(changelog, "0.1.0", prs)
    content = changelog.read_text(encoding="utf-8")
    assert "## 0.1.0" in content
    assert "initial (#1)" in content
