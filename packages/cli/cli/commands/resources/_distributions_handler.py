# SPDX-License-Identifier: MIT
"""Handlers for ``resources distributions`` and ``resources reconcile``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error, handle_validation_error
from cli._output import emit_json, to_data

from ._acquire_plan import normalize_versions
from ._catalog_reconciliation import catalog_matches
from ._distribution_entries import _distribution_entries


def handle_resources_distributions(args: argparse.Namespace) -> int:
    """List acquisition channels available for a resource version."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        version_payload = to_data(
            client.v1.resources.versions(resource_id=args.resource_id)
        )

        versions = normalize_versions(version_payload)
        if not versions:
            return handle_validation_error(
                "no resource version available",
                json_output=config.json_output,
            )
        version_id = getattr(args, "version", None) or str(
            versions[0].get("id") or versions[0].get("version_id")
        )
        plan = to_data(
            client.v1.resources.acquisition_plan(
                resource_id=args.resource_id,
                version_id=version_id,
                channel="auto",
            )
        )
        payload = {
            "resource_id": args.resource_id,
            "version_id": version_id,
            "selected_channel": plan.get("selected_channel"),
            "distributions": _distribution_entries(
                client, args.resource_id, version_id, plan
            ),
        }
        if config.json_output:
            emit_json("logion.resources.distributions", payload)
        else:
            out = sys.stdout
            out.write(f"Resource: {payload['resource_id']}\n")
            out.write(f"Version:  {payload['version_id']}\n")
            for dist in payload["distributions"]:
                marker = " (selected)" if dist["selected"] else ""
                out.write(f"  - {dist['channel']}{marker}\n")
                if not dist["available"]:
                    out.write(f"      unavailable: {dist['reason']}\n")
                    continue
                native = dist.get("native") or {}
                if native.get("tool"):
                    out.write(
                        f"      native: {native['tool']} "
                        f"{native.get('tested_version') or '?'}\n"
                    )
                if dist.get("expected"):
                    out.write(f"      expected: {dist['expected']}\n")
    except Exception as exc:
        return handle_error(
            exc, json_output=config.json_output, handle_validation=True
        )
    else:
        return 0
    finally:
        client.close()


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
    from cli import _receipts

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

    Reads local receipts and reports matched/unresolved/ambiguous state
    without reinstalling, deleting, or uploading anything.
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
