# SPDX-License-Identifier: MIT
"""Handler and helpers for ``resources reconcile``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from cli import _receipts
from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error
from cli._output import emit_json

from ._catalog_reconciliation import catalog_matches
from ._reconcile_receipt import _save_reconciled_receipt


def _scope_root_of(receipt: dict[str, Any]) -> Path | None:
    """Recover the scope root a receipt's relative target hangs off."""
    target = receipt.get("target_path")
    relative = receipt.get("relative_target_path")
    if not isinstance(target, str) or not isinstance(relative, str):
        return None
    root = Path(target)
    for _ in Path(relative).parts:
        root = root.parent
    return root


def _reconcile_receipts(
    harness_filter: str, scope_filter: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split local receipts into still-valid and drifted installations.

    A receipt is evidence of what was installed, not proof that it is
    still there. Each one is re-checked against the filesystem so a
    deleted or edited installation is reported as drifted instead of
    being reported as matched forever.
    """

    from ._reconciliation import receipt_status

    matched: list[dict[str, Any]] = []
    drifted: list[dict[str, Any]] = []
    for receipt in _receipts.load_receipts():
        harness = receipt.get("harness")
        if harness_filter != "all" and harness != harness_filter:
            continue
        if scope_filter != "all" and receipt.get("scope_kind") != scope_filter:
            continue
        status, evidence = receipt_status(receipt, _scope_root_of(receipt))
        entry = {
            "installation_id": receipt.get("installation_id"),
            "resource_id": receipt.get("resource_id"),
            "version_id": receipt.get("version_id"),
            "channel": receipt.get("channel"),
            "scope_kind": receipt.get("scope_kind"),
            "relative_target_path": receipt.get("relative_target_path"),
            "verification": status,
            "evidence": evidence,
        }
        (drifted if status == "drifted" else matched).append(entry)
    return matched, drifted


def handle_resources_reconcile(args: argparse.Namespace) -> int:
    """Match locally installed artifacts to catalog resources.

    Reads native manager state without mutating it. A unique catalog match
    records a local Logion inventory receipt; no artifact is installed,
    deleted, edited, or uploaded.
    """
    from cli._harness.scopes import canonical_scope, default_scope_for_cwd

    from ._reconciliation import discover_native_state

    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        harness_filter = str(getattr(args, "harness", "all") or "all")
        scope_filter = str(getattr(args, "scope", "all") or "all")
        if scope_filter != "all":
            scope_filter = canonical_scope(scope_filter)
        source = str(getattr(args, "source", "all") or "all")
        root = Path(getattr(args, "cwd", None) or Path.cwd()).resolve()
        matched, drifted = _reconcile_receipts(harness_filter, scope_filter)
        # Native manager state is discovered under one root, so it carries
        # that root's scope. Filtering it by --harness would compare a
        # harness (codex, claude) with a manager (skills, plugins, hf);
        # --from already selects the manager.
        native_scope = default_scope_for_cwd(root)
        native = (
            discover_native_state(root, source)
            if scope_filter in {"all", native_scope}
            else []
        )
        unresolved = []
        ambiguous = []
        for item in native:
            item["scope_kind"] = native_scope
            if item.get("resource_version_id"):
                matched.append(item)
                continue
            candidates = catalog_matches(client, item)
            if len(candidates) == 1:
                item.update(candidates[0])
                receipt = _save_reconciled_receipt(
                    client=client,
                    item=item,
                    candidate=candidates[0],
                    root=root,
                    scope=native_scope,
                    harness=harness_filter,
                )
                if receipt is not None:
                    item.update({
                        "installation_id": receipt["installation_id"],
                        "channel": receipt["channel"],
                        "relative_target_path": receipt[
                            "relative_target_path"
                        ],
                        "receipt_origin": receipt["receipt_origin"],
                    })
                matched.append(item)
            elif len(candidates) > 1:
                item["candidates"] = candidates
                ambiguous.append(item)
            else:
                unresolved.append(item)
        report: dict[str, Any] = {
            "matched": matched,
            "ambiguous": ambiguous,
            "unresolved": unresolved,
            "drifted": drifted,
            "source": source,
            "scope": scope_filter,
            "harness": harness_filter,
            "dry_run": bool(getattr(args, "dry_run", False)),
        }
        if config.json_output:
            emit_json("logion.resources.reconcile", report)
        else:
            out = sys.stdout
            out.write(f"Matched installations: {len(report['matched'])}\n")
            out.write(f"Drifted:              {len(report['drifted'])}\n")
            out.write(f"Unresolved:           {len(report['unresolved'])}\n")
            out.write(f"Ambiguous:            {len(report['ambiguous'])}\n")
            for item in report["drifted"]:
                out.write(
                    f"  drifted: {item['relative_target_path']} "
                    f"({item['evidence']})\n"
                )
    except Exception as exc:
        return handle_error(
            exc, json_output=config.json_output, handle_validation=True
        )
    else:
        return 0
    finally:
        client.close()
