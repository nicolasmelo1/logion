# SPDX-License-Identifier: MIT
"""Handlers for payments commands."""

from __future__ import annotations

import argparse

from cli._config import resolve_config_from_args
from cli._confirm import require_yes
from cli._context import make_client
from cli._errors import handle_error, print_err
from cli._output import emit, emit_json, to_data

from ._orders_helpers import (
    order_to_payload,
    validate_uuid_arg,
)


def handle_seller_readiness(args: argparse.Namespace) -> int:
    """Execute the payments seller-readiness command."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.payments.get_seller_readiness()
        if config.json_output:
            emit_json("logion.payments.seller-readiness", to_data(result))
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_onboarding_link(args: argparse.Namespace) -> int:
    """Execute the payments onboarding-link command."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.payments.create_onboarding_link()
        if config.json_output:
            emit_json("logion.payments.onboarding-link", to_data(result))
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_orders_get(args: argparse.Namespace) -> int:
    """Execute the payments orders get command."""
    bad_id = validate_uuid_arg(args, args.order_id, "ORDER_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.payments.get_order(order_id=args.order_id)
    except Exception as exc:
        return handle_error(exc)
    else:
        payload = order_to_payload(result)
        if config.json_output:
            emit_json("logion.payments.orders.get", payload)
        else:
            emit(payload, json_output=False)
        return 0
    finally:
        client.close()


def handle_creator_earnings(args: argparse.Namespace) -> int:
    """Execute the payments creator-earnings command."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.payments.get_creator_earnings()
        if config.json_output:
            emit_json("logion.payments.creator-earnings", to_data(result))
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_cash_out(args: argparse.Namespace) -> int:
    """Execute the payments cash-out command."""
    if not args.dry_run:
        refusal = require_yes(args.yes, "initiate a cash-out transfer")
        if refusal is not None:
            return refusal
        if args.expected_gross_payout_cents is None:
            print_err(
                "Error: non-dry-run cash-out requires "
                "--expected-gross-payout-cents from a prior preview."
            )
            return 2
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        if not args.dry_run:
            preview = client.v1.payments.request_cash_out(
                minimum_payout_cents=args.minimum_payout_cents,
                dry_run=True,
            )
            preview_data = to_data(preview)
            actual = preview_data.get("gross_payout_cents")
            if actual != args.expected_gross_payout_cents:
                print_err(
                    "Error: cash-out preview changed: expected "
                    f"{args.expected_gross_payout_cents} cents, got "
                    f"{actual} cents. Review the new dry-run before retrying."
                )
                return 2
        result = client.v1.payments.request_cash_out(
            minimum_payout_cents=args.minimum_payout_cents,
            dry_run=args.dry_run,
        )
        if config.json_output:
            emit_json("logion.payments.cash-out", to_data(result))
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()
