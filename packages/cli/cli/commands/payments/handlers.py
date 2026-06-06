# SPDX-License-Identifier: MIT
"""Handlers for payments commands."""

from __future__ import annotations

import argparse

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error
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
