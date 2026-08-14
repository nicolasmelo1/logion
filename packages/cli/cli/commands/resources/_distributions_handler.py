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
            "distributions": [
                {
                    "channel": plan.get("selected_channel"),
                    "integrity": plan.get("integrity"),
                    "expected": plan.get("expected"),
                    "native": plan.get("native"),
                    "enabled": True,
                }
            ]
            + [
                {"channel": alt, "enabled": True}
                for alt in (plan.get("alternatives") or [])
            ],
        }
        if config.json_output:
            emit_json("logion.resources.distributions", payload)
        else:
            out = sys.stdout
            out.write(f"Resource: {payload['resource_id']}\n")
            out.write(f"Version:  {payload['version_id']}\n")
            for dist in payload["distributions"]:
                out.write(f"  - {dist['channel']}\n")
    except Exception as exc:
        return handle_error(
            exc, json_output=config.json_output, handle_validation=True
        )
    else:
        return 0
    finally:
        client.close()


def handle_resources_reconcile(args: argparse.Namespace) -> int:
    """Match locally installed artifacts to catalog resources.

    Reads local receipts and reports matched/unresolved/ambiguous state
    without reinstalling, deleting, or uploading anything.
    """
    from cli import _receipts

    from ._reconciliation import discover_native_state

    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        harness_filter = str(getattr(args, "harness", "all") or "all")
        scope_filter = str(getattr(args, "scope", "all") or "all")
        if scope_filter != "all":
            from cli._harness.scopes import canonical_scope

            scope_filter = canonical_scope(scope_filter)
        receipts = [
            receipt
            for receipt in _receipts.load_receipts()
            if (
                harness_filter == "all"
                or receipt.get("harness") == harness_filter
            )
            and (
                scope_filter == "all"
                or receipt.get("scope_kind") == scope_filter
            )
        ]
        source = str(getattr(args, "source", "all") or "all")
        root = Path(getattr(args, "cwd", None) or Path.cwd()).resolve()
        native = discover_native_state(root, source)
        matched = [
            {
                "installation_id": r["installation_id"],
                "resource_id": r["resource_id"],
                "version_id": r["version_id"],
                "channel": r["channel"],
                "scope_kind": r["scope_kind"],
                "relative_target_path": r["relative_target_path"],
                "verification": r["verification"],
            }
            for r in receipts
        ]
        matched.extend(
            item
            for item in native
            if item.get("resource_version_id")
            and (
                harness_filter == "all"
                or item.get("manager") == harness_filter
            )
            and (scope_filter in {"all", "repo-root"})
        )
        unresolved = []
        ambiguous = []
        for item in native:
            if (
                harness_filter != "all"
                and item.get("manager") != harness_filter
            ):
                continue
            if scope_filter not in {"all", "repo-root"}:
                continue
            if item.get("resource_version_id"):
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
            "drifted": [],
            "source": source,
            "dry_run": bool(getattr(args, "dry_run", False)),
        }
        if config.json_output:
            emit_json("logion.resources.reconcile", report)
        else:
            out = sys.stdout
            out.write(f"Matched installations: {len(report['matched'])}\n")
            out.write(f"Unresolved:           {len(report['unresolved'])}\n")
            out.write(f"Ambiguous:            {len(report['ambiguous'])}\n")
    except Exception as exc:
        return handle_error(
            exc, json_output=config.json_output, handle_validation=True
        )
    else:
        return 0
    finally:
        client.close()
