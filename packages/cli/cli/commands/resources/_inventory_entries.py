# SPDX-License-Identifier: MIT
"""Inventory entry building, backed by local acquisition receipts.

Inventory is meant to be the one canonical local record of what is
installed, whichever channel put it there. A directory scan alone only
finds skill directories, so entries are also resolved from the local
acquisition receipts — that is what keeps agent plugins and model
snapshots visible next to skills.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cli._harness.scopes import ScopeTarget

from ._reconciliation import reconciliation_status


def _scan_dir(
    target: ScopeTarget,
    precedence: int,
    receipts_by_path: dict[Path, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """List installed resources under *target* with reconciliation status.

    A directory is an installed resource when it carries a ``SKILL.md`` or
    when a local acquisition receipt claims it. The receipt path keeps
    non-skill resource types — agent plugins and models acquired through
    ``npx plugins`` or ``hf`` — visible in the same inventory.
    """
    if not target.target_path.is_dir():
        return []
    by_path = receipts_by_path or {}
    found: list[dict[str, Any]] = []
    try:
        children = sorted(target.target_path.iterdir())
    except OSError:
        return []
    for child in children:
        if not child.is_dir():
            continue
        receipt = by_path.get(_resolve(child))
        if receipt is None and not (child / "SKILL.md").is_file():
            continue
        found.append(_entry(child, target, precedence, receipt))
    return found


def _resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path


def _entry(
    path: Path,
    target: ScopeTarget,
    precedence: int,
    receipt: dict[str, Any] | None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "name": path.name,
        "path": str(path),
        "scope_kind": target.scope_kind,
        "scope_root": str(target.scope_root),
        "precedence": precedence,
        "resource_type": (
            receipt.get("resource_type") if receipt else "agent_skill"
        ),
        "reconciliation": reconciliation_status(
            path, receipt, target.scope_root
        ),
    }
    if receipt is not None:
        entry["receipt"] = {
            "installation_id": receipt.get("installation_id"),
            "resource_id": receipt.get("resource_id"),
            "version_id": receipt.get("version_id"),
            "channel": receipt.get("channel"),
            "verification": receipt.get("verification"),
            "acquired_at": receipt.get("acquired_at"),
        }
    return entry


def _receipts_by_path() -> dict[Path, dict[str, Any]]:
    """Index local acquisition receipts by their resolved install path."""
    from cli import _receipts

    indexed: dict[Path, dict[str, Any]] = {}
    for receipt in _receipts.load_receipts():
        raw = receipt.get("target_path")
        if isinstance(raw, str) and raw:
            indexed[_resolve(Path(raw))] = receipt
    return indexed


def _unscanned_receipt_entries(
    targets: list[ScopeTarget],
    scanned: list[dict[str, Any]],
    receipts_by_path: dict[Path, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Report receipt-backed installs the directory scan cannot see.

    An ``hf`` snapshot or a plugin installed by its native manager does not
    live under a harness skills directory, so the scan misses it. The
    receipt still pins it to a scope, and inventory must stay the single
    canonical local record regardless of channel.
    """
    seen = {_resolve(Path(str(item["path"]))) for item in scanned}
    scope_roots = {_resolve(target.scope_root): target for target in targets}
    extra: list[dict[str, Any]] = []
    for path, receipt in sorted(receipts_by_path.items()):
        if path in seen:
            continue
        target = scope_roots.get(
            _resolve(Path(str(receipt.get("target_path", ""))).parent)
        )
        for root, candidate in scope_roots.items():
            if target is not None:
                break
            try:
                path.relative_to(root)
            except ValueError:
                continue
            target = candidate
        if target is None or receipt.get("scope_kind") != target.scope_kind:
            continue
        extra.append(_entry(path, target, len(targets), receipt))
    return extra
