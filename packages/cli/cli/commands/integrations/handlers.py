# SPDX-License-Identifier: MIT
"""Handlers for integration management commands."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from cli._errors import handle_error, print_err
from cli._harness import (
    adapter_names,
    all_adapters,
    detect_present,
    get_adapter,
)
from cli._output import emit_json
from cli.integrations_state import get_mode, set_mode


def _adapter_to_dict(adapter: Any) -> dict[str, Any]:
    """Return a JSON-safe summary of one harness adapter."""
    return {
        "name": adapter.name,
        "display_name": adapter.display_name,
        "present": adapter.is_present(),
        "enabled": get_mode(adapter.name) is not None,
        "mode": get_mode(adapter.name),
    }


def handle_integrations_detect(args: argparse.Namespace) -> int:
    """Detect supported harnesses installed on this machine."""
    json_output = getattr(args, "json_output", False)
    try:
        present = detect_present()
        all_names = adapter_names()
        detected = [
            {"name": a.name, "display_name": a.display_name} for a in present
        ]
        supported = [
            {"name": name, "display_name": None} for name in all_names
        ]
        if json_output:
            emit_json(
                "logion.integrations.detect",
                {
                    "detected": detected,
                    "supported": supported,
                },
            )
        else:
            if detected:
                for item in detected:
                    sys.stdout.write(
                        f"{item['name']}: {item['display_name']}\n"
                    )
            else:
                sys.stdout.write("No supported harnesses detected.\n")
            sys.stdout.write(f"\nSupported: {', '.join(all_names)}\n")
    except Exception as exc:
        return handle_error(exc)
    return 0


def handle_integrations_enable(args: argparse.Namespace) -> int:
    """Enable observation integration for a harness."""
    json_output = getattr(args, "json_output", False)
    try:
        adapter = get_adapter(args.harness)
        if adapter is None:
            print_err(f"Unknown harness: {args.harness}")
            return 2
        present = adapter.is_present()
        if not args.dry_run:
            set_mode(args.harness, args.mode)
        if json_output:
            emit_json(
                "logion.integrations.enable",
                {
                    "harness": args.harness,
                    "mode": args.mode,
                    "dry_run": args.dry_run,
                    "present": present,
                    "enabled": not args.dry_run,
                },
            )
        else:
            action = "would enable" if args.dry_run else "enabled"
            sys.stdout.write(
                f"{action} integration for {args.harness}"
                f" (mode: {args.mode})\n"
            )
            if not present:
                sys.stdout.write(
                    f"Warning: {args.harness} does not appear"
                    " to be installed.\n"
                )
    except Exception as exc:
        return handle_error(exc)
    return 0


def handle_integrations_disable(args: argparse.Namespace) -> int:
    """Disable observation integration for a harness."""
    json_output = getattr(args, "json_output", False)
    try:
        adapter = get_adapter(args.harness)
        if adapter is None:
            print_err(f"Unknown harness: {args.harness}")
            return 2
        set_mode(args.harness, None)
        if json_output:
            emit_json(
                "logion.integrations.disable",
                {
                    "harness": args.harness,
                    "disabled": True,
                },
            )
        else:
            sys.stdout.write(f"Disabled integration for {args.harness}.\n")
    except Exception as exc:
        return handle_error(exc)
    return 0


def handle_integrations_status(args: argparse.Namespace) -> int:
    """Show integration status for all harnesses."""
    json_output = getattr(args, "json_output", False)
    try:
        adapters = all_adapters()
        statuses = [_adapter_to_dict(a) for a in adapters]
        if json_output:
            emit_json("logion.integrations.status", statuses)
        else:
            if not statuses:
                sys.stdout.write("No harnesses registered.\n")
            else:
                for s in statuses:
                    state = "enabled" if s["enabled"] else "disabled"
                    sys.stdout.write(
                        f"{s['name']}: {state} ({s['display_name']})\n"
                    )
    except Exception as exc:
        return handle_error(exc)
    return 0
