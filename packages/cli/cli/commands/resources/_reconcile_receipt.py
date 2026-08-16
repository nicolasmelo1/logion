# SPDX-License-Identifier: MIT
"""Local inventory receipt creation for native reconciliation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cli import _receipts
from cli._output import to_data

_RECONCILE_CHANNELS = {
    "skills": "npx_skills",
    "plugins": "npx_plugins",
    "dsh": "dsh",
    "hf": "hf",
}


def _save_reconciled_receipt(
    *,
    client: Any,
    item: dict[str, Any],
    candidate: dict[str, Any],
    root: Path,
    scope: str,
    harness: str,
) -> dict[str, Any] | None:
    """Persist Logion inventory after an exact, unique native-state match."""
    channel = _RECONCILE_CHANNELS.get(str(item.get("manager") or ""))
    if channel is None or harness == "all":
        return None
    raw_target = Path(str(item.get("path") or ""))
    target = (
        raw_target if raw_target.is_absolute() else root / raw_target
    ).resolve()
    relative = target.relative_to(root).as_posix()
    plan = to_data(
        client.v1.resources.acquisition_plan(
            resource_id=str(candidate["resource_id"]),
            version_id=str(candidate["version_id"]),
            channel=channel,
        )
    )
    if not isinstance(plan, dict) or plan.get("selected_channel") != channel:
        raise RuntimeError("catalog match has no matching native distribution")
    native = plan.get("native") or {}
    if not isinstance(native, dict):
        raise TypeError("catalog native distribution is malformed")
    planned_revision = str(native.get("revision") or "")
    observed_pins = {
        str(item.get("revision") or ""),
        str(item.get("version") or ""),
    }
    observed_pins.discard("")
    if observed_pins and planned_revision not in observed_pins:
        raise RuntimeError(
            "native installation does not match the catalog pin"
        )
    observed_revision = (
        planned_revision if planned_revision in observed_pins else ""
    )
    scope_id = _receipts.scope_id_for_target(scope, root)
    native_evidence = {
        "schema_version": 1,
        "manager_name": str(item.get("manager") or ""),
        "manager_version": str(native.get("tested_version") or ""),
        "receipt_id": str(item.get("name") or relative),
        "canonical_source": str(item.get("source") or ""),
        "immutable_revision": observed_revision,
        "content_digest": str(plan.get("content_digest") or ""),
        "declared_capabilities": item.get("declared_capabilities") or {},
    }
    reconciled_at = _receipts.now_rfc3339()
    receipt: dict[str, Any] = {
        "schema_version": _receipts.RECEIPT_SCHEMA_VERSION,
        "resource_id": str(candidate["resource_id"]),
        "version_id": str(candidate["version_id"]),
        "distribution_id": str(plan.get("distribution_id") or ""),
        "resource_type": str(candidate.get("resource_type") or ""),
        "content_digest": str(plan.get("content_digest") or ""),
        "channel": channel,
        "upstream_locator": str(native.get("upstream_locator") or ""),
        "harness": harness,
        "scope_kind": scope,
        "scope_id": scope_id,
        "installation_id": _receipts.installation_id_for(scope_id, relative),
        "target_path": str(target),
        "relative_target_path": relative,
        "installed_paths": [relative],
        "projection_paths": [],
        "acquired_at": reconciled_at,
        "verified_at": reconciled_at,
        "verification": str(candidate.get("verification") or "unverified"),
        "receipt_origin": "resources_reconcile",
        "reconciled_at": reconciled_at,
        "native_evidence": native_evidence,
        "native_receipt_digest": _receipts.native_receipt_digest(
            native_evidence
        ),
    }
    _receipts.save_receipt(receipt)
    return receipt
