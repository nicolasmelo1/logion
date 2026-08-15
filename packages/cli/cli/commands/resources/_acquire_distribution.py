# SPDX-License-Identifier: MIT
"""Distribution projection for the local acquisition plan.

Turns the server-owned acquisition plan into the operation, distribution,
and verification blocks the dry-run renders and the executable path acts
on. Both read the same projection, so the preview cannot drift from what
execution does.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cli._harness.scopes import ScopeTarget
from cli._output import to_data

#: Channels Logion installs itself; every other channel delegates to the
#: upstream package manager named in ``native.tool``.
_LOGION_OWNED_CHANNELS = frozenset({"logion_bundle"})


def _target_plan(
    target: ScopeTarget,
    name: str,
    distribution: dict[str, Any] | None,
) -> dict[str, Any]:
    destination = target.target_path / name
    if not target.target_path.exists():
        state = "create-target"
    elif not destination.exists():
        state = "create"
    elif not destination.is_dir():
        state = "conflict"
    else:
        state = "replace"
    return {
        "scope_kind": target.scope_kind,
        "scope_root": str(target.scope_root),
        "target_path": str(target.target_path),
        "installation_path": str(destination),
        "native_manager": target.native_manager,
        "exists": target.exists,
        "state": state,
        "operation": _operation(distribution, destination),
    }


def _operation(
    distribution: dict[str, Any] | None, destination: Path
) -> dict[str, Any]:
    """Describe the exact operation the executable path would perform."""
    if distribution is None:
        return {
            "kind": "unresolved",
            "source": None,
            "destination": str(destination),
            "ready": False,
        }
    channel = str(distribution.get("selected_channel") or "")
    native = distribution.get("native") or {}
    if channel in _LOGION_OWNED_CHANNELS:
        return {
            "kind": "download",
            "channel": channel,
            "source": "logion-hosted bundle manifest",
            "destination": str(destination),
            "ready": True,
        }
    return {
        "kind": "delegate-native-manager",
        "channel": channel,
        "tool": native.get("tool"),
        "tested_version": native.get("tested_version"),
        # argv is a display/execution array, never a shell string.
        "argv": list(native.get("argv") or []),
        "source": native.get("upstream_locator"),
        "revision": native.get("revision"),
        "destination": str(destination),
        "ready": bool(native.get("argv")),
    }


def _distribution_plan(
    distribution: dict[str, Any] | None, error: str | None
) -> dict[str, Any]:
    """Project the server plan into the local dry-run serialization.

    Only server-owned fields are copied. Local paths, scope ids, and
    installation ids never travel back to the acquisition-plan endpoint,
    and dry-run carries no ``installation_id`` or
    ``native_receipt_digest``.
    """
    if distribution is None:
        return {"resolved": False, "reason": error or "not resolved"}
    native = distribution.get("native") or {}
    expected = distribution.get("expected") or {}
    return {
        "resolved": True,
        "distribution_id": distribution.get("distribution_id"),
        "channel": distribution.get("selected_channel"),
        "alternatives": list(distribution.get("alternatives") or []),
        "content_digest": distribution.get("content_digest"),
        "integrity": distribution.get("integrity") or {},
        "license": distribution.get("license") or {},
        "entitlement": distribution.get("entitlement") or {},
        "expected_bytes": expected.get("bytes"),
        "expected_files": expected.get("files"),
        "permissions": distribution.get("permissions") or {},
        "warnings": list(distribution.get("warnings") or []),
        "native": {
            "tool": native.get("tool"),
            "tested_version": native.get("tested_version"),
            "argv": list(native.get("argv") or []),
            "upstream_locator": native.get("upstream_locator"),
            "revision": native.get("revision"),
        },
    }


def _verification(
    version: dict[str, Any] | None, distribution: dict[str, Any] | None
) -> dict[str, Any]:
    if not version:
        return {"ready": False, "reason": "no resource version available"}
    digest = version.get("content_digest")
    algorithm = version.get("digest_algorithm")
    revision = version.get("source_revision")
    ready = all(
        isinstance(value, str) and value for value in (digest, algorithm)
    )
    return {
        "ready": ready,
        "digest_algorithm": algorithm,
        "content_digest": digest,
        "source_revision": revision,
        "expected_level": _expected_verification(distribution),
    }


def _expected_verification(distribution: dict[str, Any] | None) -> str:
    """The verification level the executable path would be able to reach."""
    if distribution is None:
        return "unknown"
    channel = str(distribution.get("selected_channel") or "")
    if channel in _LOGION_OWNED_CHANNELS:
        return "exact" if distribution.get("content_digest") else "unverified"
    revision = (distribution.get("native") or {}).get("revision")
    return "source_revision" if revision else "unverified"


def fetch_distribution(
    client: Any,
    *,
    resource_id: str,
    versions: list[dict[str, Any]],
    channel: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Fetch and validate the server-owned acquisition plan.

    Returns ``(None, reason)`` instead of raising so a dry-run can still
    render an honest, non-executable plan when no distribution resolves.
    """
    if not versions:
        return None, "no resource version available"
    version_id = str(versions[0].get("id") or versions[0].get("version_id"))
    try:
        server_plan = to_data(
            client.v1.resources.acquisition_plan(
                resource_id=resource_id,
                version_id=version_id,
                channel=channel,
            )
        )
    except Exception as exc:
        return None, f"acquisition plan unavailable: {exc}"
    if not isinstance(server_plan, dict):
        return None, "acquisition plan response is not an object"
    missing = [
        key
        for key in ("version_id", "distribution_id", "selected_channel")
        if not server_plan.get(key)
    ]
    if missing:
        return None, f"acquisition plan is missing {', '.join(missing)}"
    return server_plan, None
