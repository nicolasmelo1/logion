# SPDX-License-Identifier: MIT
"""Handlers for usage observation commands."""

from __future__ import annotations

import argparse
import json
import re
import sys

from cli._errors import handle_error, print_err
from cli._json import JsonObject, opt_str
from cli._output import emit_json, to_data
from cli._receipts import load_receipts
from cli.integrations_state import get_mode
from cli.usage.observations import (
    dismiss_observations,
    list_pending_observations,
    make_observation,
    spool_observation,
)


def _parse_since(value: str) -> int | None:
    """Parse a ``--since`` window string like ``24h`` or ``1h`` into seconds.

    Returns ``None`` for an empty value (all observations).
    """
    if not value:
        return None
    match = re.fullmatch(r"(\d+)([smhd])", value.strip())
    if match is None:
        raise ValueError("--since must use <number><s|m|h|d>")
    amount = int(match.group(1))
    unit = match.group(2)
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return amount * multipliers[unit]


def handle_usage_pending(args: argparse.Namespace) -> int:
    """List pending usage observations from the local spool."""
    json_output = getattr(args, "json_output", False)
    since_seconds = _parse_since(getattr(args, "since", "24h"))
    try:
        observations = list_pending_observations(since_seconds=since_seconds)
        if json_output:
            emit_json("logion.usage.pending", to_data(observations))
        else:
            if not observations:
                sys.stdout.write("No pending usage observations.\n")
            else:
                for obs in observations:
                    lines = [
                        f"observation_id: {obs.get('observation_id', '')}",
                        f"observed_at: {obs.get('observed_at', '')}",
                        f"harness: {obs.get('harness', '')}",
                        f"event: {obs.get('event', '')}",
                        f"resource_id: {obs.get('resource_id', '')}",
                        f"version_id: {obs.get('version_id', '')}",
                    ]
                    sys.stdout.write("\n".join(lines) + "\n---\n")
    except Exception as exc:
        return handle_error(exc)
    return 0


def _read_stdin_json() -> JsonObject:
    """Read one bounded JSON object from stdin."""
    max_bytes = 64 * 1024
    try:
        raw = sys.stdin.buffer.read(max_bytes + 1)
    except (AttributeError, OSError):
        try:
            text_payload = sys.stdin.read(max_bytes + 1)
        except TypeError:
            text_payload = sys.stdin.read()
        raw = text_payload.encode()
    if len(raw) > max_bytes:
        raise ValueError("observation payload exceeds 64 KiB")
    if not raw.strip():
        raise ValueError("observation payload is required")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("observation payload must be valid JSON") from exc
    if not isinstance(data, dict):
        raise TypeError("observation payload must be a JSON object")
    return data


def _receipt_for_observation(
    harness: str, installation_id: object
) -> JsonObject:
    if not isinstance(installation_id, str) or not installation_id:
        raise ValueError("installation_id is required")
    matches = [
        receipt
        for receipt in load_receipts()
        if receipt.get("installation_id") == installation_id
        and receipt.get("harness") == harness
    ]
    if len(matches) != 1:
        raise ValueError(
            "installation_id is not uniquely attributed in local inventory"
        )
    return matches[0]


def handle_usage_observe(args: argparse.Namespace) -> int:
    """Read an observation from stdin and write it to the local spool."""
    json_output = getattr(args, "json_output", False)
    try:
        if get_mode(args.harness) is None:
            if json_output:
                emit_json(
                    "logion.usage.observe",
                    {
                        "disposition": "ignored",
                        "reason": "integration_disabled",
                    },
                )
            return 0
        data = _read_stdin_json()
        receipt = _receipt_for_observation(
            args.harness, data.get("installation_id")
        )
        obs = make_observation(
            harness=args.harness,
            event=opt_str(data, "event", "resource_invoked"),
            resource_id=receipt["resource_id"],
            version_id=receipt["version_id"],
            resource_type=receipt["resource_type"],
            acquisition_channel=receipt["channel"],
            installation_id=receipt["installation_id"],
            scope_kind=receipt["scope_kind"],
            scope_id=receipt["scope_id"],
            session_hash=data.get("session_hash"),
        )
        spool_observation(obs)
        if json_output:
            emit_json(
                "logion.usage.observe",
                {
                    "disposition": "recorded",
                    "observation": to_data(obs.to_dict()),
                },
            )
        else:
            sys.stdout.write(f"observation_id: {obs.observation_id}\n")
            sys.stdout.write(f"event: {obs.event}\n")
            sys.stdout.write(f"resource_id: {obs.resource_id}\n")
    except Exception as exc:
        # observe must always exit 0 per contract
        if json_output:
            emit_json(
                "logion.usage.observe",
                {"disposition": "failed", "reason": str(exc)},
            )
        print_err(f"Warning: could not spool observation: {exc}")
    return 0


def handle_usage_dismiss(args: argparse.Namespace) -> int:
    """Remove observations by group id from the local spool."""
    json_output = getattr(args, "json_output", False)
    try:
        removed = dismiss_observations(args.observation_group_id)
        if json_output:
            emit_json(
                "logion.usage.dismiss",
                {
                    "observation_group_id": args.observation_group_id,
                    "removed": removed,
                },
            )
        else:
            if removed > 0:
                sys.stdout.write(f"Removed {removed} observation(s).\n")
            else:
                sys.stdout.write("No matching observations found.\n")
    except Exception as exc:
        return handle_error(exc)
    return 0
