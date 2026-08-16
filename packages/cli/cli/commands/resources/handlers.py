# SPDX-License-Identifier: MIT
"""Handlers for resources commands."""

from __future__ import annotations

import argparse
import sys

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error, handle_validation_error
from cli._output import emit_json, to_data

from ._acquire_handler import handle_resources_acquire
from ._distributions_handler import handle_resources_distributions
from ._inventory_handler import handle_resources_inventory
from ._reconcile_handler import handle_resources_reconcile

__all__ = [
    "handle_resources_acquire",
    "handle_resources_distributions",
    "handle_resources_get",
    "handle_resources_inventory",
    "handle_resources_reconcile",
    "handle_resources_search",
    "handle_resources_versions",
]


def _print_resource(payload: dict[str, object]) -> None:
    """Render a resource-detail envelope in human-readable form."""
    nested = payload.get("resource")
    resource = nested if isinstance(nested, dict) else payload
    sys.stdout.write(
        f"ID: {resource.get('id')}\n"
        f"Canonical URI: {resource.get('canonical_uri')}\n"
        f"Type: {resource.get('resource_type', 'unknown')}\n"
        f"Title: {resource.get('title')}\n"
        f"Lifecycle: {resource.get('lifecycle_status', 'unknown')}\n"
    )
    summary = resource.get("summary")
    if isinstance(summary, str) and summary.strip():
        sys.stdout.write(f"\n{summary}\n")
    sources = payload.get("sources")
    if isinstance(sources, list) and sources:
        sys.stdout.write("\nSources:\n")
        for source in sources:
            if isinstance(source, dict):
                sys.stdout.write(
                    f"  {source.get('source_kind', '?')}: "
                    f"{source.get('source_uri', '?')}\n"
                )


def handle_resources_search(args: argparse.Namespace) -> int:
    """Execute ``resources list`` and its historical ``search`` alias."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        unsupported = [
            name
            for name in ("query", "tags")
            if getattr(args, name, None) is not None
        ]
        if unsupported:
            message = (
                "resource query/tag search is not supported by the "
                "current API; "
                "use resources list with resource/lifecycle filters"
            )
            return handle_validation_error(
                message, json_output=config.json_output
            )
        result = client.v1.resources.search(
            resource_type=getattr(args, "resource_type", None),
            lifecycle_status=getattr(args, "lifecycle_status", None),
            limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
        )
        payload = to_data(result)
        if config.json_output:
            command = getattr(args, "resources_command", "list")
            emit_json(f"logion.resources.{command}", payload)
        else:
            items = (
                payload
                if isinstance(payload, list)
                else payload.get("items", [])
            )
            if not items:
                sys.stdout.write("No resources found.\n")
            else:
                for item in items:
                    idata = (
                        to_data(item) if not isinstance(item, dict) else item
                    )
                    rid = idata.get("id", "?")
                    rtype = idata.get("resource_type", "?")
                    title = idata.get("title", "")
                    line = f"  {rid} [{rtype}]"
                    if title:
                        line += f" — {title}"
                    sys.stdout.write(f"{line}\n")
                    if getattr(args, "verbose", False):
                        canonical_uri = idata.get("canonical_uri")
                        summary = idata.get("summary")
                        if canonical_uri:
                            sys.stdout.write(f"    URI: {canonical_uri}\n")
                        if summary:
                            sys.stdout.write(f"    {summary}\n")
    except Exception as exc:
        return handle_error(
            exc, json_output=config.json_output, handle_validation=True
        )
    else:
        return 0
    finally:
        client.close()


def handle_resources_get(args: argparse.Namespace) -> int:
    """Execute ``logion resources get RESOURCE_ID``."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.resources.get(resource_id=args.resource_id)
        payload = to_data(result)
        if config.json_output:
            emit_json("logion.resources.get", payload)
        else:
            _print_resource(payload)
    except Exception as exc:
        return handle_error(
            exc, json_output=config.json_output, handle_validation=True
        )
    else:
        return 0
    finally:
        client.close()


def handle_resources_versions(args: argparse.Namespace) -> int:
    """Execute ``logion resources versions RESOURCE_ID``."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.resources.versions(
            resource_id=args.resource_id,
            limit=getattr(args, "limit", None),
        )
        payload = to_data(result)
        if config.json_output:
            emit_json("logion.resources.versions", payload)
        else:
            items = (
                payload
                if isinstance(payload, list)
                else payload.get("items", [])
            )
            if not items:
                sys.stdout.write("No versions found.\n")
            else:
                for item in items:
                    idata = (
                        to_data(item) if not isinstance(item, dict) else item
                    )
                    vid = idata.get("id", "?")
                    discovered = idata.get("discovered_at", "")
                    line = f"  {vid}"
                    if discovered:
                        line += f" ({discovered})"
                    sys.stdout.write(f"{line}\n")
    except Exception as exc:
        return handle_error(
            exc, json_output=config.json_output, handle_validation=True
        )
    else:
        return 0
    finally:
        client.close()
