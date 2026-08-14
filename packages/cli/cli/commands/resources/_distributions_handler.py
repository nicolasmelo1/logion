# SPDX-License-Identifier: MIT
"""Handlers for ``resources distributions`` and ``resources reconcile``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error, handle_validation_error
from cli._output import emit_json, to_data

from ._acquire_plan import normalize_versions


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


def _catalog_matches(
    client: object, item: dict[str, object]
) -> list[dict[str, object]]:
    """Resolve native source/revision against catalog identity."""
    source = str(item.get("source") or "")
    revision = str(item.get("revision") or "")
    if not source:
        return []
    try:
        payload = to_data(
            client.v1.resources.search(resource_type="agent_skill", limit=100)
        )
    except Exception:
        return []
    entries = (
        payload if isinstance(payload, list) else payload.get("items", [])
    )
    matches: list[dict[str, object]] = []
    for resource in entries:
        if not isinstance(resource, dict):
            continue
        canonical = str(resource.get("canonical_uri") or "")
        if (
            canonical != source
            and source not in canonical
            and canonical not in source
        ):
            continue
        resource_id = resource.get("id")
        if not resource_id:
            continue
        try:
            versions = to_data(
                client.v1.resources.versions(resource_id=str(resource_id))
            )
        except Exception:
            continue
        versions = (
            versions
            if isinstance(versions, list)
            else versions.get("items", [])
        )
        for version in versions:
            if not isinstance(version, dict):
                continue
            version_revision = str(version.get("source_revision") or "")
            if revision and version_revision and revision != version_revision:
                continue
            matches.append({
                "resource_id": str(resource_id),
                "version_id": str(
                    version.get("id") or version.get("version_id") or ""
                ),
                "verification": "source_revision" if revision else "canonical",
            })
    return matches


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
        receipts = _receipts.load_receipts()
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
            item for item in native if item.get("resource_version_id")
        )
        unresolved = []
        ambiguous = []
        for item in native:
            if item.get("resource_version_id"):
                continue
            candidates = _catalog_matches(client, item)
            if len(candidates) == 1:
                item.update(candidates[0])
                matched.append(item)
            elif len(candidates) > 1:
                item["candidates"] = candidates
                ambiguous.append(item)
            else:
                unresolved.append(item)
        report = {
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
