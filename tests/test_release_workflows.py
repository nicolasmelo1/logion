"""Release workflow structure tests for safe, tag-only publishing.

These tests parse the release workflow YAML files as structured data and
assert properties required for safe, tag-only release publishing.
No network calls are made.
"""

from __future__ import annotations

import pathlib
from collections.abc import Mapping

import yaml

WORKFLOWS_DIR = (
    pathlib.Path(__file__).resolve().parent.parent / ".github" / "workflows"
)


def _load(name: str) -> Mapping:
    text = (WORKFLOWS_DIR / name).read_text(encoding="utf-8")
    return yaml.safe_load(text)


CLI = _load("release-cli.yml")
CLIENT = _load("release-client.yml")
SKILLMAP = _load("release-skillmap.yml")
COMPANION = _load("release-companion.yml")
NPM = _load("release-npm.yml")

PYPI_WORKFLOWS = [CLI, CLIENT, SKILLMAP]
ALL_WORKFLOWS = [CLI, CLIENT, SKILLMAP, COMPANION, NPM]


def _trigger_tags(wf: Mapping) -> list[str]:
    """Return the list of tag patterns from on.push.tags."""
    # PyYAML parses the YAML key "on" as Python bool True
    trigger = wf.get("on") or wf.get(True)
    return trigger["push"]["tags"]


# ---------------------------------------------------------------------------
# 1. Tag filters
# ---------------------------------------------------------------------------


def test_release_cli_tag_filter():
    """release-cli.yml triggers on logion-cli-v* tags only."""
    assert "logion-cli-v*" in _trigger_tags(CLI)


def test_release_client_tag_filter():
    """release-client.yml triggers on logion-client-v* tags only."""
    assert "logion-client-v*" in _trigger_tags(CLIENT)


def test_release_skillmap_tag_filter():
    """release-skillmap.yml triggers on logion-skillmap-v* tags only."""
    assert "logion-skillmap-v*" in _trigger_tags(SKILLMAP)


def test_release_cli_waits_for_matching_skillmap_version():
    """CLI publication waits until its skillmap dependency is available."""
    steps = CLI["jobs"]["publish-pypi"]["steps"]
    wait_steps = [
        step
        for step in steps
        if step.get("name") == "Wait for matching skillmap version on PyPI"
    ]
    assert len(wait_steps) == 1
    assert "logion-skillmap/json" in wait_steps[0]["run"]
    assert "needs.verify.outputs.version" in wait_steps[0]["env"]["VERSION"]


def test_release_companion_tag_filter():
    """release-companion.yml triggers on logion-companion-v* tags only."""
    assert "logion-companion-v*" in _trigger_tags(COMPANION)


# ---------------------------------------------------------------------------
# 4. Publish jobs use environment
# ---------------------------------------------------------------------------


def test_release_publish_jobs_have_environment():
    """PyPI publish jobs use environment: pypi; npm uses environment: npm."""
    for wf in PYPI_WORKFLOWS:
        pub = wf["jobs"]["publish-pypi"]
        env = pub.get("environment", {})
        if isinstance(env, dict):
            name = env.get("name", "")
        else:
            name = env if isinstance(env, str) else ""
        assert name == "pypi" or "pypi" in str(env), (
            f"Expected environment pypi in {wf['name']}, got {env}"
        )

    npm_pub = NPM["jobs"]["publish"]
    env = npm_pub.get("environment", {})
    if isinstance(env, dict):
        name = env.get("name", "")
    else:
        name = env if isinstance(env, str) else ""
    assert name == "npm" or "npm" in str(env), (
        f"Expected environment npm in release-npm.yml, got {env}"
    )


# ---------------------------------------------------------------------------
# 5. OIDC permissions
# ---------------------------------------------------------------------------


def test_release_oidc_permissions():
    """PyPI publish jobs and npm workflow include id-token: write."""
    for wf in PYPI_WORKFLOWS:
        pub = wf["jobs"]["publish-pypi"]
        perms = pub.get("permissions", {})
        assert perms.get("id-token") == "write", (
            f"publish-pypi in {wf['name']} must have id-token: write"
        )

    top_perms = NPM.get("permissions", {})
    assert top_perms.get("id-token") == "write", (
        "release-npm.yml must have id-token: write at top level"
    )


# ---------------------------------------------------------------------------
# 6. Concurrency
# ---------------------------------------------------------------------------


def test_release_workflows_have_concurrency():
    """Tag release workflows use concurrency with cancel-in-progress: false."""
    for wf in ALL_WORKFLOWS:
        conc = wf.get("concurrency", {})
        assert conc.get("cancel-in-progress") is False, (
            f"{wf['name']} concurrency.cancel-in-progress must be false, "
            f"got {conc.get('cancel-in-progress')}"
        )


# ---------------------------------------------------------------------------
# 7. npm provenance
# ---------------------------------------------------------------------------


def test_release_npm_uses_provenance():
    """release-npm.yml contains npm publish --provenance."""
    pub = NPM["jobs"]["publish"]
    steps = pub.get("steps", [])
    for step in steps:
        run = step.get("run", "")
        if "npm publish" in run:
            assert "--provenance" in run, (
                "npm publish step must include --provenance"
            )
            return
    raise AssertionError("No npm publish step found in release-npm.yml")


# ---------------------------------------------------------------------------
# 8. No broad branch push triggers
# ---------------------------------------------------------------------------


def test_release_workflows_do_not_publish_on_branch_push():
    """Publish workflows trigger on tags only, not on broad branch pushes."""
    for wf in ALL_WORKFLOWS:
        trigger = wf.get("on") or wf.get(True)
        push_cfg = trigger.get("push", {})
        branches = push_cfg.get("branches", None)
        assert branches is None, (
            f"{wf['name']} must not trigger on branch pushes, "
            f"but found branches: {branches}"
        )
