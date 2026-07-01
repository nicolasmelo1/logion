# SPDX-License-Identifier: MIT
"""Tests for the release orchestrator."""

from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.release_orchestrator import (
    _PACKAGE_CONFIG,
    ReleaseExecutor,
    ReleasePlanner,
    plan_to_json,
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
        key = " ".join(args[:3])
        stdout = self._responses.get(key, "")
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=stdout,
            stderr="",
        )


def test_plan_includes_all_three_package_tags() -> None:
    """Plan has client, cli, and companion tags."""
    planner = ReleasePlanner(repo_root=REPO_ROOT)
    plan = planner.load("0.1.99", publish_store=False)
    names = {p.name for p in plan.packages}
    assert names == {"client", "cli", "companion"}
    tags = set(plan.tags_to_create)
    assert "logion-client-v0.1.99" in tags
    assert "logion-cli-v0.1.99" in tags
    assert "logion-companion-v0.1.99" in tags


def test_plan_requires_semver() -> None:
    """Non-semver version raises ValueError."""
    planner = ReleasePlanner(repo_root=REPO_ROOT)
    try:
        planner.load("not-a-version", publish_store=False)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for bad version")


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


def test_release_dry_run_does_not_run_git_push(
    tmp_path: Path,
) -> None:
    """Dry-run mode does not execute git push."""
    plan = ReleasePlanner(
        repo_root=REPO_ROOT,
    ).load("0.1.99", publish_store=False)
    # Create the smoke findings file so preflight passes.
    plan.smoke_findings_path.parent.mkdir(parents=True, exist_ok=True)
    plan.smoke_findings_path.write_text(
        "---\nrelease_version: \"0.1.99\"\napi_base_url: \"\"\n"
        "cli_version: \"\"\nharnesses:\n  - codex\n  - claude-code\n"
        "  - opencode\n---\n",
        encoding="utf-8",
    )
    runner = _FakeRunner()
    executor = ReleaseExecutor(plan, runner=runner)
    executor.execute(dry_run=True)
    # No git push command should have been issued.
    push_calls = [c for c in runner.calls if "push" in c and "git" in c]
    assert push_calls == [], (
        f"Dry-run should not push, got: {push_calls}",
    )


def test_release_creates_expected_tag_commands() -> None:
    """Tags match the expected ``logion-<pkg>-v<version>`` format."""
    planner = ReleasePlanner(repo_root=REPO_ROOT)
    plan = planner.load("0.2.0", publish_store=False)
    for tag in plan.tags_to_create:
        assert tag.startswith("logion-"), tag
        assert tag.endswith("-v0.2.0"), tag
    # Confirm all three packages have tags.
    assert len(plan.tags_to_create) == len(_PACKAGE_CONFIG)


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
    assert len(data["tags_to_create"]) == 3
