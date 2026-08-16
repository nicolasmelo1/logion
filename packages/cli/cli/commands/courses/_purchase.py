# SPDX-License-Identifier: MIT
"""Course purchase handler — credit-spend gated by ``--yes``."""

from __future__ import annotations

import argparse
import sys

from cli._config import resolve_config_from_args
from cli._confirm import require_yes
from cli._context import make_client
from cli._errors import handle_error, print_err, validate_uuid_id
from cli._output import emit, emit_json, to_object


def handle_purchase(args: argparse.Namespace) -> int:
    """Execute the courses purchase command."""
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id
    refusal = require_yes(args.yes, "spend credits and purchase this course")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.courses.purchase(
            course_id=args.course_id,
            expected_price_cents=args.expected_price_cents,
            idempotency_key=args.idempotency_key,
        )
        data = to_object(result)
        if config.json_output:
            emit_json("logion.courses.purchase", data)
        else:
            _emit_purchase_human(data)
    except Exception as exc:
        if _is_insufficient_credit_error(exc):
            print_err(
                "Insufficient credits. Check `logion credits balance` and "
                "create a user-approved top-up with `logion credits top-up`."
            )
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def _is_insufficient_credit_error(exc: Exception) -> bool:
    """Return whether an API error reports an insufficient credit balance."""
    detail = getattr(exc, "detail", "")
    text = str(detail).lower()
    return "insufficient" in text and "credit" in text


def _emit_purchase_human(data: dict[str, object]) -> None:
    """Render course purchase result with explicit credit spend lines."""
    lines: list[str] = []
    amount = data.get("amount_cents")
    if amount is not None:
        lines.append(f"cost_cents: {amount}")
    before = data.get("balance_before_cents")
    after = data.get("balance_after_cents")
    if before is not None and after is not None:
        lines.append(f"balance_cents: {before} -> {after}")
    flow = data.get("purchase_flow")
    if flow is not None:
        lines.append(f"purchase_flow: {flow}")
    entitlement = data.get("entitlement_granted")
    if entitlement is not None:
        lines.append(f"entitlement_granted: {entitlement}")
    if lines:
        sys.stdout.write("\n".join(lines) + "\n")
    else:
        emit(data, json_output=False)
