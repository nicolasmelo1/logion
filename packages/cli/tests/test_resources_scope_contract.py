# SPDX-License-Identifier: MIT
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cli._harness.scopes import ScopeTarget
from cli.commands.resources._acquire_plan import (
    build_plan,
    normalize_resource,
    normalize_versions,
)
from cli.commands.resources._inventory_handler import _scan_dir
from cli.commands.resources._reconciliation import (
    mark_ambiguities,
    reconciliation_status,
)
from cli.commands.resources._scope_resolution import resolve_acquire_targets
from cli.commands.resources.parser import register


def _resources_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    register(subparsers)
    return parser


def test_acquire_parser_accepts_scope_alias_and_omits_default() -> None:
    parser = _resources_parser()
    args = parser.parse_args([
        "resources",
        "acquire",
        "res-1",
        "--harness",
        "codex",
    ])
    assert args.scope is None
    aliased = parser.parse_args([
        "resources",
        "acquire",
        "res-1",
        "--harness",
        "codex",
        "--scope",
        "project",
    ])
    assert aliased.scope == "project"


def test_acquire_parser_exposes_explicit_non_dry_run_rejection() -> None:
    args = _resources_parser().parse_args([
        "resources",
        "acquire",
        "res-1",
        "--harness",
        "codex",
        "--no-dry-run",
    ])
    assert args.dry_run is False


def test_resolve_targets_does_not_swallow_constructor_type_error(
    tmp_path: Path,
) -> None:
    targets = resolve_acquire_targets("codex", "repo-current", tmp_path, None)
    assert targets[0].target_path == tmp_path / ".agents" / "skills"


def test_normalizes_generated_resource_detail_envelope() -> None:
    normalized = normalize_resource({
        "resource": {"id": "res-1", "title": "Audit Skill"},
        "sources": [{"source_uri": "https://example.test/repo"}],
        "projections": [{"platform": "codex"}],
    })
    assert normalized["id"] == "res-1"
    assert normalized["sources"][0]["source_uri"].startswith("https://")
    assert normalize_versions({"items": [{"id": "v1"}]}) == [{"id": "v1"}]


def test_acquisition_plan_is_honest_when_distribution_is_unresolved(
    tmp_path: Path,
) -> None:
    target = ScopeTarget(
        scope_kind="repo-root",
        scope_root=tmp_path,
        target_path=tmp_path / ".agents" / "skills",
        native_manager=None,
        exists=False,
    )
    plan = build_plan(
        resource_id="res-1",
        scope="repo-root",
        harness="codex",
        resource={"title": "Audit Skill", "canonical_uri": "logion://res-1"},
        versions=[
            {
                "id": "v1",
                "digest_algorithm": "sha256",
                "content_digest": "abc123",
            }
        ],
        targets=[target],
        default_scope="repo-root",
        scope_was_explicit=True,
    )
    target_plan = plan["targets"][0]
    assert target_plan["state"] == "create-target"
    assert target_plan["operation"]["ready"] is False
    assert plan["observation_integration"]["state"] == "not-configured"
    assert not target.target_path.exists()


def test_acquisition_plan_not_executable_when_permissions_unresolved(
    tmp_path: Path,
) -> None:
    """A dry-run plan must not be executable when permissions are unknown."""
    target = ScopeTarget(
        scope_kind="repo-root",
        scope_root=tmp_path,
        target_path=tmp_path / ".agents" / "skills",
        native_manager=None,
        exists=False,
    )
    plan = build_plan(
        resource_id="res-1",
        scope="repo-root",
        harness="codex",
        resource={"title": "Audit Skill", "canonical_uri": "logion://res-1"},
        versions=[
            {
                "id": "v1",
                "digest_algorithm": "sha256",
                "content_digest": "abc123",
                "distribution_url": "https://example.test/v1.zip",
            }
        ],
        targets=[target],
        default_scope="repo-root",
        scope_was_explicit=True,
    )
    assert plan["executable"] is False
    assert any(
        "permissions not resolved" in r for r in plan["blocked_reasons"]
    )
    assert (
        plan["permissions_required"]
        == "unknown-until-distribution-is-resolved"
    )


def test_inventory_does_not_trust_marker_existence(tmp_path: Path) -> None:
    skill = tmp_path / "skills" / "audit-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Audit\n", encoding="utf-8")
    (skill / ".logion-lock.json").write_text("{}", encoding="utf-8")
    reconciliation = reconciliation_status(skill)
    assert reconciliation["status"] == "unlinked"


def test_inventory_validates_exact_receipt_and_marks_name_ambiguity(
    tmp_path: Path,
) -> None:
    first = tmp_path / "repo" / "skills" / "audit-skill"
    second = tmp_path / "user" / "skills" / "audit-skill"
    for skill in (first, second):
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("# Audit\n", encoding="utf-8")
    digest = reconciliation_status(first)["content_digest"]
    (first / ".logion-lock.json").write_text(
        json.dumps({
            "resource_version_id": "v1",
            "native_receipt_digest": "receipt-1",
            "content_digest": digest,
        }),
        encoding="utf-8",
    )
    repo_target = ScopeTarget(
        scope_kind="repo-root",
        scope_root=first.parents[2],
        target_path=first.parent,
        native_manager=None,
        exists=True,
    )
    user_target = ScopeTarget(
        scope_kind="user",
        scope_root=second.parents[2],
        target_path=second.parent,
        native_manager=None,
        exists=True,
    )
    results = _scan_dir(repo_target, 0) + _scan_dir(user_target, 1)
    mark_ambiguities(results)
    assert results[0]["reconciliation"]["status"] == "exact"
    assert results[1]["reconciliation"]["status"] == "ambiguous"
    assert all(item["ambiguous_name"] for item in results)
