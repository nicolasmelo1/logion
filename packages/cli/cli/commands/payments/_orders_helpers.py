# SPDX-License-Identifier: MIT
"""Shared helpers for payments order commands."""

from __future__ import annotations

import argparse
import sys
from uuid import UUID

from cli._config import CliConfig
from cli._errors import emit_error_json
from cli._json import JsonObject
from cli._output import emit_json, to_object

TERMINAL_STATUSES = frozenset({"fulfilled", "failed", "refunded", "cancelled"})


def invalid_identifier(
    args: argparse.Namespace,
    label: str,
    value: str,
    exit_code: int = 2,
) -> int:
    """Emit an unsafe identifier error envelope when JSON was requested."""
    message = f"{label} must be a valid UUID (got: {value!r})."
    if getattr(args, "json_output", False):
        emit_error_json("unsafe_identifier", message, exit_code)
    else:
        sys.stderr.write(f"Error: {message}\n")
    return exit_code


def validate_uuid_arg(
    args: argparse.Namespace, value: str, label: str
) -> int | None:
    """Validate a UUID-ish positional argument."""
    if not value or not value.strip():
        return invalid_identifier(args, label, value)
    try:
        UUID(value)
    except ValueError:
        return invalid_identifier(args, label, value)
    return None


def order_to_payload(result: object) -> JsonObject:
    """Normalize SDK order responses to the public CLI shape."""
    raw = to_object(result)
    settled_at = (
        raw.get("settled_at")
        or raw.get("paid_at")
        or raw.get("transferred_at")
    )
    payload: JsonObject = {
        "order_id": raw.get("order_id") or raw.get("id"),
        "status": raw.get("status"),
        "course_id": raw.get("course_id"),
        "amount_cents": raw.get("amount_cents"),
        "currency": raw.get("currency"),
        "settled_at": settled_at,
        "purchase_flow": raw.get("purchase_flow"),
        "balance_before_cents": raw.get("balance_before_cents"),
        "balance_after_cents": raw.get("balance_after_cents"),
    }
    # Fold through any extra fields the SDK exposes
    for key, value in raw.items():
        payload.setdefault(key, value)
    return payload


def emit_wait_result(
    config: CliConfig,
    payload: JsonObject,
    elapsed: float,
    *,
    final: bool,
) -> None:
    """Emit the current wait-state payload."""
    wait_payload = {
        **payload,
        "elapsed_seconds": round(elapsed, 2),
        "terminal": payload.get("status") in TERMINAL_STATUSES,
        "final": final,
    }
    if config.json_output:
        emit_json("logion.payments.orders.wait", wait_payload)
        sys.stdout.write("\n")
        return

    summary = (
        f"Order {payload.get('order_id')}: "
        f"status={payload.get('status')} (elapsed {int(elapsed)}s)"
    )
    sys.stdout.write(summary)
    sys.stdout.write("\n")


def timeout_payload(order_id: str) -> JsonObject:
    """Return the fallback payload for an unfinished wait call."""
    return {
        "order_id": order_id,
        "status": "unknown",
        "course_id": None,
        "amount_cents": None,
        "currency": None,
        "settled_at": None,
        "purchase_flow": None,
        "balance_before_cents": None,
        "balance_after_cents": None,
    }
