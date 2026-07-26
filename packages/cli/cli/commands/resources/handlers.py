# SPDX-License-Identifier: MIT
"""Handlers for resources commands."""

from __future__ import annotations

import argparse
import sys

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error
from cli._output import emit_json, to_data

from ._acquire_handler import handle_resources_acquire
from ._inventory_handler import handle_resources_inventory

__all__ = [
    "handle_resources_acquire",
    "handle_resources_get",
    "handle_resources_inventory",
    "handle_resources_search",
    "handle_resources_versions",
]


def _print_resource(payload: dict[str, object]) -> None:
    """Render a resource in compact human-readable form."""
    sys.stdout.write(
        f"ID: {payload.get('canonical')}\n"
        f"Type: {payload.get('resource_type', 'unknown')}\n"
        f"Title: {payload.get('title')}\n"
        f"Author: {payload.get('original_author')}\n"
        f"Source: {payload.get('source_url')}\n"
        f"License: {payload.get('license_spdx')}\n"
    )
    summary = payload.get("summary")
    if isinstance(summary, str) and summary.strip():
        sys.stdout.write(f"\n{summary}\n")


def handle_resources_search(args: argparse.Namespace) -> int:
    """Execute ``logion resources search QUERY``."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.resources.search(
            query=args.query,
            resource_type=getattr(args, "resource_type", None),
            tags=getattr(args, "tags", None),
            limit=getattr(args, "limit", None),
        )
        payload = to_data(result)
        if config.json_output:
            emit_json("logion.resources.search", payload)
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
                    rid = idata.get("canonical", "?")
                    rtype = idata.get("resource_type", "?")
                    title = idata.get("title", "")
                    line = f"  {rid} [{rtype}]"
                    if title:
                        line += f" — {title}"
                    sys.stdout.write(f"{line}\n")
    except Exception as exc:
        return handle_error(exc)
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
        return handle_error(exc)
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
                    vid = idata.get("version_id", "?")
                    created = idata.get("created_at", "")
                    line = f"  {vid}"
                    if created:
                        line += f" ({created})"
                    sys.stdout.write(f"{line}\n")
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()
