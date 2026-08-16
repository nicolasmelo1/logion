# SPDX-License-Identifier: MIT
"""Handlers for indexed listings commands."""

from __future__ import annotations

import argparse

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error
from cli._output import emit_json, to_object


def _print_human(payload: dict[str, object]) -> None:
    """Render an indexed listing in compact human-readable form."""
    from sys import stdout

    stdout.write(f"ID: {payload.get('id')}\n")
    stdout.write(f"Title: {payload.get('title')}\n")
    stdout.write(f"Author: {payload.get('original_author')}\n")
    stdout.write(f"Source: {payload.get('source_url')}\n")
    stdout.write(f"Hub: {payload.get('source_hub')}\n")
    stdout.write(f"Tier: {payload.get('tier')}\n")
    stdout.write(f"License: {payload.get('license_spdx')}\n")
    stdout.write(f"Observation status: {payload.get('observation_status')}\n")
    summary = payload.get("summary")
    if isinstance(summary, str) and summary.strip():
        stdout.write(f"\n{summary}\n")


def handle_indexed_get(args: argparse.Namespace) -> int:
    """Execute ``logion indexed get LISTING_ID``."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.indexed_listings.get(listing_id=args.listing_id)
        payload = to_object(result)
        if config.json_output:
            emit_json("logion.indexed.get", payload)
        else:
            _print_human(payload)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()
