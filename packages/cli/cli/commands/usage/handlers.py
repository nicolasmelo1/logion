# SPDX-License-Identifier: MIT
"""Handlers for usage observation commands."""

from __future__ import annotations

import argparse
import json
import re
import sys

from cli._errors import handle_error, print_err
from cli._json import JsonObject, opt_str, require_str
from cli._output import emit_json, to_data
from cli.integrations_state import effective_mode, may_spool
from cli.usage.attribution import (
    receipt_by_installation_id,
    resolve_installations,
    session_hash_for,
)
from cli.usage.observations import (
    dismiss_observations,
    list_pending_observations,
    make_observation,
    observation_event,
    observation_scope_kind,
    spool_observation,
    with_group_ids,
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
        observations = with_group_ids(
            list_pending_observations(since_seconds=since_seconds)
        )
        if json_output:
            emit_json("logion.usage.pending", to_data(observations))
        else:
            if not observations:
                sys.stdout.write("No pending usage observations.\n")
            else:
                for obs in observations:
                    group_id = obs.get("observation_group_id", "")
                    lines = [
                        f"observation_id: {obs.get('observation_id', '')}",
                        f"observation_group_id: {group_id}",
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
    max_bytes = 1024 * 1024
    try:
        raw = sys.stdin.buffer.read(max_bytes + 1)
    except (AttributeError, OSError):
        try:
            text_payload = sys.stdin.read(max_bytes + 1)
        except TypeError:
            text_payload = sys.stdin.read()
        raw = text_payload.encode()
    if len(raw) > max_bytes:
        raise ValueError("observation payload exceeds 1 MiB")
    if not raw.strip():
        raise ValueError("observation payload is required")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("observation payload must be valid JSON") from exc
    if not isinstance(data, dict):
        raise TypeError("observation payload must be a JSON object")
    return data


def _session_hash(payload: JsonObject) -> str | None:
    """Opaque session grouping key, hashing the raw id if that is all we got.

    A companion may pass an already-opaque ``session_hash``; a native hook
    passes the harness's own ``session_id``, which never reaches the spool.
    """
    provided = opt_str(payload, "session_hash")
    if provided:
        return provided
    session_id = opt_str(payload, "session_id")
    return session_hash_for(session_id) if session_id else None


def _receipts_for_payload(payload: JsonObject) -> list[JsonObject]:
    """Every installation this payload is evidence of use for.

    An explicit ``installation_id`` short-circuits path resolution; a raw
    harness payload is matched against local inventory in memory.
    """
    if payload.get("installation_id") is not None:
        return [receipt_by_installation_id(payload.get("installation_id"))]
    return resolve_installations(payload)


def handle_usage_observe(args: argparse.Namespace) -> int:
    """Read an observation from stdin and write it to the local spool."""
    json_output = getattr(args, "json_output", False)
    try:
        if not may_spool(args.harness):
            # Consent gate comes first: with observation off there is no
            # read, no write, and no network call beyond this check.
            if json_output:
                emit_json(
                    "logion.usage.observe",
                    {
                        "disposition": "ignored",
                        "reason": "observation_not_consented",
                        "mode": effective_mode(args.harness),
                    },
                )
            return 0
        payload = _read_stdin_json()
        receipts = _receipts_for_payload(payload)
        if not receipts:
            if json_output:
                emit_json(
                    "logion.usage.observe",
                    {
                        "disposition": "ignored",
                        "reason": "no_attributed_installation",
                    },
                )
            return 0
        session_hash = _session_hash(payload)
        event = observation_event(opt_str(payload, "event"))
        recorded: list[JsonObject] = []
        for receipt in receipts:
            obs = make_observation(
                harness=args.harness,
                event=event,
                resource_id=require_str(receipt, "resource_id"),
                version_id=require_str(receipt, "version_id"),
                resource_type=require_str(receipt, "resource_type"),
                acquisition_channel=require_str(receipt, "channel"),
                installation_id=require_str(receipt, "installation_id"),
                scope_kind=observation_scope_kind(
                    require_str(receipt, "scope_kind")
                ),
                scope_id=require_str(receipt, "scope_id"),
                session_hash=session_hash,
            )
            spool_observation(obs)
            recorded.append(obs.to_dict())
        if json_output:
            emit_json(
                "logion.usage.observe",
                {
                    "disposition": "recorded",
                    "observation": to_data(recorded[0]),
                    "observations": to_data(recorded),
                },
            )
        else:
            for entry in recorded:
                sys.stdout.write(
                    f"observation_id: {entry.get('observation_id', '')}\n"
                )
                sys.stdout.write(f"event: {entry.get('event', '')}\n")
                sys.stdout.write(
                    f"resource_id: {entry.get('resource_id', '')}\n"
                )
    except Exception as exc:
        # observe must always exit 0 per contract: a broken hook must
        # never break the harness that called it.
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
