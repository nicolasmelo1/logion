# SPDX-License-Identifier: MIT
"""Handlers for integration management commands."""

from __future__ import annotations

import argparse
import sys

from cli._errors import handle_error, print_err
from cli._harness import (
    adapter_names,
    all_adapters,
    detect_present,
    get_adapter,
)
from cli._harness.base import (
    HarnessAdapter,
    HarnessConfigError,
    ObservationPlan,
)
from cli._json import JsonObject
from cli._output import emit_json
from cli.integrations_state import (
    OFF,
    do_not_track,
    effective_mode,
    forget_managed_hook,
    get_mode,
    managed_hooks,
    may_spool,
    record_managed_hook,
    set_mode,
)


def _adapter_to_dict(adapter: HarnessAdapter) -> JsonObject:
    """Return a JSON-safe summary of one harness adapter."""
    return {
        "name": adapter.name,
        "display_name": adapter.display_name,
        "present": adapter.is_present(),
        "enabled": may_spool(adapter.name),
        "mode": get_mode(adapter.name),
        "effective_mode": effective_mode(adapter.name),
        "observation_supported": (
            adapter.observation_config_path("user") is not None
        ),
        "managed_hooks": list(managed_hooks(adapter.name)),
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
            {
                "name": a.name,
                "display_name": a.display_name,
                "observation_supported": (
                    a.observation_config_path("user") is not None
                ),
            }
            for a in all_adapters()
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


def _report_plan(plan: ObservationPlan) -> None:
    """Print the config edit in human-readable form."""
    if not plan.supported:
        sys.stdout.write(
            f"{plan.harness}: no trustworthy tool-use hook at scope"
            f" {plan.scope} ({plan.reason}).\n"
            "Logion will still reconcile inventory; use"
            " `logion feedback submit` to report use explicitly.\n"
        )
        return
    if plan.already:
        sys.stdout.write(f"{plan.harness}: {plan.path} already up to date.\n")
        return
    sys.stdout.write(f"{plan.harness}: {plan.path}\n")
    sys.stdout.write(plan.diff or "")


def handle_integrations_enable(args: argparse.Namespace) -> int:
    """Enable observation integration for a harness."""
    json_output = getattr(args, "json_output", False)
    try:
        adapter = get_adapter(args.harness)
        if adapter is None:
            print_err(f"Unknown harness: {args.harness}")
            return 2
        present = adapter.is_present()
        scope = getattr(args, "scope", "user")
        if args.mode == OFF:
            return handle_integrations_disable(args)
        plan = (
            adapter.plan_observation(scope)
            if args.dry_run
            else adapter.enable_observation(scope)
        )
        if not args.dry_run:
            set_mode(args.harness, args.mode)
            if plan.supported and plan.path is not None:
                record_managed_hook(
                    args.harness,
                    config_path=str(plan.path),
                    scope=plan.scope,
                    command=adapter.observation_command(),
                )
        if json_output:
            emit_json(
                "logion.integrations.enable",
                {
                    "harness": args.harness,
                    "mode": args.mode,
                    "effective_mode": effective_mode(args.harness),
                    "dry_run": args.dry_run,
                    "present": present,
                    "enabled": not args.dry_run,
                    "plan": plan.to_dict(),
                    "do_not_track": do_not_track(),
                },
            )
        else:
            action = "would enable" if args.dry_run else "enabled"
            sys.stdout.write(
                f"{action} integration for {args.harness}"
                f" (mode: {args.mode})\n"
            )
            _report_plan(plan)
            if not present:
                sys.stdout.write(
                    f"Warning: {args.harness} does not appear"
                    " to be installed.\n"
                )
            if do_not_track():
                sys.stdout.write(
                    "Warning: DO_NOT_TRACK is set in this environment;"
                    " observation stays off until it is cleared.\n"
                )
    except HarnessConfigError as exc:
        print_err(str(exc))
        return 1
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
        scope = getattr(args, "scope", "user")
        plan = adapter.disable_observation(scope)
        if plan.supported and plan.path is not None:
            forget_managed_hook(args.harness, config_path=str(plan.path))
        # Stored explicitly rather than deleted: "the user turned this
        # off" must survive a future change to the default.
        set_mode(args.harness, OFF)
        if json_output:
            emit_json(
                "logion.integrations.disable",
                {
                    "harness": args.harness,
                    "disabled": True,
                    "mode": OFF,
                    "plan": plan.to_dict(),
                },
            )
        else:
            sys.stdout.write(f"Disabled integration for {args.harness}.\n")
            _report_plan(plan)
    except HarnessConfigError as exc:
        print_err(str(exc))
        return 1
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
                        f"{s['name']}: {state}"
                        f" (mode: {s['effective_mode']})"
                        f" ({s['display_name']})\n"
                    )
            if do_not_track():
                sys.stdout.write(
                    "\nDO_NOT_TRACK is set: every harness is off"
                    " regardless of stored mode.\n"
                )
    except Exception as exc:
        return handle_error(exc)
    return 0
