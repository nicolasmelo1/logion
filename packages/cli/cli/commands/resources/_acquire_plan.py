# SPDX-License-Identifier: MIT
"""Pure acquisition-plan helpers for harness-scoped resources."""

from __future__ import annotations

import re
from typing import Any

from cli._harness.scopes import ADMIN, USER, ScopeTarget

from ._acquire_distribution import (
    _distribution_plan,
    _target_plan,
    _verification,
)


def normalize_resource(payload: Any) -> dict[str, Any]:
    """Accept both the API detail envelope and the legacy flat response."""
    if not isinstance(payload, dict):
        raise TypeError("resource detail response is not an object")
    nested = payload.get("resource")
    if isinstance(nested, dict):
        resource = dict(nested)
        resource["sources"] = payload.get("sources") or []
        resource["projections"] = payload.get("projections") or []
        return resource
    return payload


def normalize_versions(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    raise TypeError(
        "resource versions response does not contain an items list"
    )


def build_plan(
    *,
    resource_id: str,
    scope: str,
    harness: str,
    resource: dict[str, Any],
    versions: list[dict[str, Any]],
    targets: list[ScopeTarget],
    default_scope: str,
    scope_was_explicit: bool,
    visible_targets: list[ScopeTarget] | None = None,
    distribution: dict[str, Any] | None = None,
    distribution_error: str | None = None,
) -> dict[str, Any]:
    """Build the local acquisition plan.

    ``distribution`` is the validated server-owned acquisition plan. It is
    fetched for dry-run and execution alike so the preview shows exactly
    what the executable path would do: channel, native argv, expected
    bytes, permissions, integrity pin, and verification expectation. When
    it is absent the plan stays honest — not executable, with the reason.
    """
    name = _resource_name(resource, resource_id)
    latest = versions[0] if versions else None
    selected_targets = targets[:1]
    target_plans = [
        _target_plan(target, name, distribution) for target in selected_targets
    ]
    visible = visible_targets or targets
    same_name = [
        {
            "scope_kind": target.scope_kind,
            "path": str(target.target_path / name),
        }
        for target in visible
        if (target.target_path / name).is_dir()
    ]
    confirmations: list[str] = []
    if not scope_was_explicit and scope == USER:
        confirmations.append("outside-repository user-scope selection")
    if scope in {USER, ADMIN}:
        confirmations.append(f"crosses into {scope} scope")
    if any(item["state"] in {"replace", "conflict"} for item in target_plans):
        confirmations.append("existing content may be replaced")
    if any(
        item["state"] in {"create-target", "create"} for item in target_plans
    ):
        confirmations.append("creates a new native target")
    blocked_reasons: list[str] = []
    if not target_plans:
        blocked_reasons.append("no installable target resolved")
    if not versions:
        blocked_reasons.append("no resource version available")
    if any(not item["operation"]["ready"] for item in target_plans):
        blocked_reasons.append(
            "selected version has no installable distribution"
        )
    if any(item["state"] == "conflict" for item in target_plans):
        blocked_reasons.append(
            "target path conflicts with non-resource content"
        )
    # A plan is not executable when the required permissions are unknown
    # (i.e. the distribution has not been resolved yet).  Executing without
    # knowing the permissions/confirmations could silently install content
    # that requires elevated access or interactive confirmation.
    if distribution is None:
        blocked_reasons.append(
            distribution_error
            or "permissions not resolved for this distribution"
        )
    return {
        "resource_id": resource_id,
        "resource_name": name,
        "scope": scope,
        "harness": harness,
        "dry_run": True,
        "default_scope_for_cwd": default_scope,
        "scope_was_explicit": scope_was_explicit,
        "resource": resource,
        "versions": versions,
        "selected_version": latest,
        "targets": target_plans,
        "alternative_targets": [
            {
                "scope_kind": target.scope_kind,
                "target_path": str(target.target_path),
                "native_manager": target.native_manager,
            }
            for target in targets[1:]
        ],
        "same_name_resources": same_name,
        "distribution": _distribution_plan(distribution, distribution_error),
        "verification": _verification(latest, distribution),
        "observation_integration": {
            "integration_version": "logion.observation.v1",
            "state": "not-configured",
            "consent": "off",
            "spool_enabled": False,
        },
        "permissions_required": (
            distribution.get("permissions") or {}
            if distribution is not None
            else "unknown-until-distribution-is-resolved"
        ),
        "executable": not blocked_reasons,
        "blocked_reasons": blocked_reasons,
        "confirmation_required": bool(confirmations),
        "confirmation_reasons": confirmations,
    }


def _resource_name(resource: dict[str, Any], resource_id: str) -> str:
    raw = resource.get("title") or resource.get("canonical_uri") or resource_id
    normalized = re.sub(r"[^a-z0-9._-]+", "-", str(raw).lower()).strip("-.")
    if not normalized:
        raise ValueError(
            "resource does not provide a safe native directory name"
        )
    return normalized[:128]
