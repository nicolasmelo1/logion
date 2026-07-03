# SPDX-License-Identifier: MIT
"""Shared helpers for credits top-up commands."""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any
from uuid import UUID

from cli._config import CliConfig
from cli._errors import emit_error_json
from cli._output import emit_json

TERMINAL_STATUSES = frozenset({
    "paid",
    "failed",
    "expired",
    "cancelled",
    "disputed",
    "reversed",
})


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
    """Validate a UUID positional argument."""
    if not value or not value.strip():
        return invalid_identifier(args, label, value)
    try:
        UUID(value)
    except ValueError:
        return invalid_identifier(args, label, value)
    return None


def top_up_to_payload(result: Any) -> dict[str, Any]:
    """Normalize a CreateCreditTopUpResponse to the CLI shape."""
    raw = (
        result.model_dump(mode="json")
        if hasattr(result, "model_dump")
        else dict(result)
    )
    payload: dict[str, Any] = {
        "top_up_id": raw.get("top_up_id"),
        "status": raw.get("status"),
        "amount_cents": raw.get("amount_cents"),
        "credit_cents_granted": raw.get("credit_cents_granted"),
        "checkout_url": raw.get("checkout_url"),
        "stripe_checkout_session_id": raw.get("stripe_checkout_session_id"),
    }
    for key, value in raw.items():
        payload.setdefault(key, value)
    return payload


def emit_top_up_human(payload: dict[str, Any]) -> None:
    """Render a top-up payload as human-readable key: value lines."""
    lines = [
        f"top_up_id: {payload.get('top_up_id')}",
        f"status: {payload.get('status')}",
        f"amount_cents: {payload.get('amount_cents')}",
        f"credit_cents_granted: {payload.get('credit_cents_granted')}",
    ]
    charge_ccy = payload.get("charge_currency")
    charge_amt = payload.get("charge_amount_cents")
    if charge_ccy and charge_amt and charge_ccy != "usd":
        lines.append(f"charge_currency: {charge_ccy}")
        lines.append(f"charge_amount_cents: {charge_amt}")
    if payload.get("checkout_url"):
        lines.append(f"checkout_url: {payload.get('checkout_url')}")
    if payload.get("stripe_checkout_session_id"):
        val = payload.get("stripe_checkout_session_id")
        lines.append(f"stripe_checkout_session_id: {val}")
    sys.stdout.write("\n".join(lines))
    sys.stdout.write("\n")


def emit_wait_result(
    config: CliConfig,
    payload: dict[str, Any],
    elapsed: float,
    *,
    final: bool,
) -> None:
    """Emit the current wait-state payload for a top-up."""
    wait_payload: dict[str, Any] = {
        **payload,
        "elapsed_seconds": round(elapsed, 2),
        "terminal": payload.get("status") in TERMINAL_STATUSES,
        "final": final,
    }
    if config.json_output:
        emit_json("logion.credits.top-ups.wait", wait_payload)
        sys.stdout.write("\n")
        return
    summary = (
        f"Top-up {payload.get('top_up_id')}: "
        f"status={payload.get('status')} (elapsed {int(elapsed)}s)"
    )
    sys.stdout.write(summary)
    sys.stdout.write("\n")


def timeout_payload(top_up_id: str) -> dict[str, Any]:
    """Return the fallback payload for an unfinished wait call."""
    return {
        "top_up_id": top_up_id,
        "status": "unknown",
        "amount_cents": None,
        "credit_cents_granted": None,
        "checkout_url": None,
        "stripe_checkout_session_id": None,
    }


def resolve_wait(
    config: CliConfig,
    last_payload: dict[str, Any] | None,
    start: float,
    top_up_id: str,
    timeout: int,
) -> int:
    """Determine the final wait result and emit it."""
    elapsed = time.monotonic() - start
    payload = last_payload or timeout_payload(top_up_id)

    if payload.get("status") == "paid":
        emit_wait_result(config, payload, elapsed, final=True)
        return 0

    if payload.get("status") in TERMINAL_STATUSES:
        emit_wait_result(config, payload, elapsed, final=True)
        return 1

    msg = f"Top-up {top_up_id} did not reach terminal state within {timeout}s"
    if config.json_output:
        emit_error_json("top_up_timeout", msg, 2)
    else:
        sys.stderr.write(f"ERROR: {msg}\n")
    return 2
