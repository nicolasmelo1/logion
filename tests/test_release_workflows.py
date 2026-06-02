# SPDX-License-Identifier: MIT
"""Tests for release workflow YAML files.

Validates OIDC permissions, environment gates, bot identity, tag routing,
and manifest PR targeting.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"


def _load_workflow(name: str) -> dict:
    path = WORKFLOWS_DIR / name
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    # YAML 1.1 parses ``on:`` as boolean True.
    # GitHub Actions expects a string key, so normalise.
    if True in data and "on" not in data:
        data["on"] = data.pop(True)
    return data


def _get_on_push_tags(wf: dict) -> list[str]:
    """Extract on.push.tags from a parsed workflow,
    handling both string-key and bool-key YAML.
    """
    on_section = wf.get("on", {})
    push_section = on_section.get("push", {})
    tags = push_section.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]
    return tags


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PUBLISH_KEYWORDS = ("pypi", "npm", "publish")
_RELEASE_WORKFLOWS = [
    "release-cli.yml",
    "release-client.yml",
    "release-companion.yml",
    "release-npm.yml",
]
_ALL_WORKFLOW_YAMLS = sorted(WORKFLOWS_DIR.glob("*.yml"))


def _is_publish_job(job_name: str, job_cfg: dict) -> bool:
    """Return True if the job publishes to PyPI or npm."""
    name_lower = job_name.lower()
    steps = job_cfg.get("steps", [])
    for step in steps:
        uses = str(step.get("uses", ""))
        if "pypi-publish" in uses or "npm-publish" in uses:
            return True
        run = str(step.get("run", ""))
        if any(kw in run for kw in ("twine upload", "npm publish")):
            return True
    return any(kw in name_lower for kw in _PUBLISH_KEYWORDS)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_release_workflows_have_oidc() -> None:
    """Every PyPI/npm publish job must have id-token: write."""
    violations: list[str] = []

    for wf_name in _RELEASE_WORKFLOWS:
        wf = _load_workflow(wf_name)
        for job_name, job_cfg in wf.get("jobs", {}).items():
            if not _is_publish_job(job_name, job_cfg):
                continue
            perms = job_cfg.get("permissions", {})
            if isinstance(perms, dict):
                oidc = perms.get("id-token")
            elif isinstance(perms, str):
                # permissions: write means all perms are write
                oidc = perms if perms == "write" else None
            else:
                oidc = None
            top_perms = wf.get("permissions", {})
            top_oidc = None
            if isinstance(top_perms, dict):
                top_oidc = top_perms.get("id-token")
            elif isinstance(top_perms, str):
                top_oidc = top_perms

            if oidc != "write" and top_oidc != "write":
                violations.append(
                    f"{wf_name} / {job_name}: id-token is not write"
                )

    assert violations == [], (
        "Publish jobs missing id-token: write:\n" + "\n".join(violations)
    )


def test_release_workflows_have_environments() -> None:
    """Every publish job must have an environment: block (gate)."""
    violations: list[str] = []

    for wf_name in _RELEASE_WORKFLOWS:
        wf = _load_workflow(wf_name)
        for job_name, job_cfg in wf.get("jobs", {}).items():
            if not _is_publish_job(job_name, job_cfg):
                continue
            if "environment" not in job_cfg:
                violations.append(
                    f"{wf_name} / {job_name}: missing environment block"
                )

    assert violations == [], (
        "Publish jobs missing environment gate:\n" + "\n".join(violations)
    )


def test_regenerate_manifest_workflow_targets_main() -> None:
    """regenerate-manifest.yml must use --base main in gh pr create."""
    wf = _load_workflow("regenerate-manifest.yml")
    steps = wf["jobs"]["regenerate"]["steps"]
    pr_step = None
    for step in steps:
        if step.get("name", "") == "Open PR on diff":
            pr_step = step
            break

    assert pr_step is not None, (
        "regenerate-manifest.yml: 'Open PR on diff' step not found"
    )
    run_script = pr_step["run"]
    assert "--base main" in run_script, (
        "regenerate-manifest.yml: gh pr create must use --base main"
    )


def test_regenerate_manifest_uses_bot_identity() -> None:
    """Commit author in regenerate-manifest.yml must be
    logion-release-bot.
    """
    wf = _load_workflow("regenerate-manifest.yml")
    steps = wf["jobs"]["regenerate"]["steps"]
    pr_step = None
    for step in steps:
        if step.get("name", "") == "Open PR on diff":
            pr_step = step
            break

    assert pr_step is not None, (
        "regenerate-manifest.yml: 'Open PR on diff' step not found"
    )
    run_script = pr_step["run"]
    assert 'user.name="logion-release-bot"' in run_script, (
        "regenerate-manifest.yml: commit author must be logion-release-bot"
    )
    assert "release-bot@users.noreply.github.com" in run_script, (
        "regenerate-manifest.yml: commit email must be release-bot@"
    )


def test_tag_workflow_routing_table_matches_yamls() -> None:
    """Tag patterns in routing table must match YAML on.push.tags."""
    # Expected routing table (from the release pipeline spec):
    #   logion-cli-v<X.Y.Z>    → release-cli.yml, release-npm.yml
    #   logion-client-v<X.Y.Z> → release-client.yml
    #   logion-companion-v<X.Y.Z> → release-companion.yml
    #   installer-v<N> → release-installer.yml

    tag_pattern_to_workflows: dict[str, set[str]] = {}

    for wf_path in _ALL_WORKFLOW_YAMLS:
        wf = _load_workflow(wf_path.name)
        tags = _get_on_push_tags(wf)
        for tag_pattern in tags:
            tag_pattern_to_workflows.setdefault(
                tag_pattern,
                set(),
            ).add(wf_path.name)

    expected_direct: dict[str, set[str]] = {
        "logion-cli-v*": {
            "release-cli.yml",
            "release-npm.yml",
        },
        "logion-client-v*": {"release-client.yml"},
        "logion-companion-v*": {"release-companion.yml"},
        "installer-v*": {"release-installer.yml"},
    }

    errors: list[str] = []
    for pat, expected_names in expected_direct.items():
        actual_names = tag_pattern_to_workflows.get(pat, set())
        if actual_names != expected_names:
            errors.append(
                f"Tag pattern '{pat}': expected "
                f"{sorted(expected_names)}, "
                f"got {sorted(actual_names)}"
            )

    # Verify release-npm.yml declares logion-cli-v* in
    # its on.push.tags
    npm_wf = _load_workflow("release-npm.yml")
    npm_tags = _get_on_push_tags(npm_wf)

    assert "logion-cli-v*" in npm_tags, (
        "release-npm.yml on.push.tags must include "
        f"'logion-cli-v*', got: {npm_tags}"
    )

    assert errors == [], "Tag routing mismatches:\n" + "\n".join(errors)
