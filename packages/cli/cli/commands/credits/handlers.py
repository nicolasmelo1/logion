# SPDX-License-Identifier: MIT
"""Handlers for credits commands."""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

from cli._config import CliConfig, resolve_config_from_args
from cli._confirm import require_yes
from cli._context import make_client
from cli._errors import handle_error
from cli._output import emit_json, to_data
from logion import LogionClient

from ._helpers import (
    TERMINAL_STATUSES,
    emit_top_up_human,
    emit_wait_result,
    resolve_wait,
    top_up_to_payload,
    validate_uuid_arg,
)


def _run(
    args: argparse.Namespace,
    fn,
    kind: str,
    *,
    json_output: bool,
    render=None,
):
    """Call *fn* on the credits resource and emit the result."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = fn(client.v1.credits)
        if json_output:
            emit_json(f"logion.credits.{kind}", to_data(result))
        elif render:
            render(result)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def _render_balance(result: object) -> None:
    data = to_data(result)
    lines = [
        f"balance_cents: {data.get('balance_cents')}",
        f"currency_code: {data.get('currency_code', 'USD_CREDIT')}",
    ]
    sys.stdout.write("\n".join(lines) + "\n")


def handle_credits_balance(args: argparse.Namespace) -> int:
    """Execute the credits balance command."""
    config = resolve_config_from_args(args)
    return _run(
        args,
        lambda c: c.get_balance(),
        "balance",
        json_output=config.json_output,
        render=_render_balance,
    )


def handle_credits_top_up(args: argparse.Namespace) -> int:
    """Execute the credits top-up command."""
    refusal = require_yes(
        args.yes,
        "create this credit top-up checkout session",
    )
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.credits.create_top_up(
            amount_cents=args.amount_cents,
            currency=getattr(args, "currency", "usd"),
        )
        payload = top_up_to_payload(result)
        if config.json_output:
            emit_json("logion.credits.top-up", payload)
        else:
            emit_top_up_human(payload)
    except Exception as exc:
        client.close()
        return handle_error(exc)
    if args.wait:
        return _poll_top_up(args, config, client, payload)
    client.close()
    return 0


def _poll_top_up(
    args: argparse.Namespace,
    config: CliConfig,
    client: LogionClient,
    initial_payload: dict[str, Any],
) -> int:
    """Poll a top-up until terminal state or timeout."""
    timeout = min(max(args.wait_timeout, 1), 600)
    interval = max(getattr(args, "interval", 5), 1)
    top_up_id = str(initial_payload.get("top_up_id"))
    last_status: str | None = str(initial_payload.get("status", "unknown"))
    last_payload: dict[str, Any] = initial_payload
    start = time.monotonic()
    try:
        while True:
            result = client.v1.credits.get_top_up(top_up_id=top_up_id)
            pl = top_up_to_payload(result)
            status = str(pl.get("status"))
            elapsed = time.monotonic() - start
            if status != last_status:
                emit_wait_result(config, pl, elapsed, final=False)
                last_status = status
            last_payload = pl
            if status in TERMINAL_STATUSES or elapsed >= timeout:
                break
            time.sleep(interval)
    except Exception as exc:
        client.close()
        return handle_error(exc)
    client.close()
    return resolve_wait(config, last_payload, start, top_up_id, timeout)


def handle_credits_top_ups_get(args: argparse.Namespace) -> int:
    """Execute the credits top-ups get command."""
    bad_id = validate_uuid_arg(args, args.top_up_id, "TOP_UP_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.credits.get_top_up(top_up_id=args.top_up_id)
        payload = top_up_to_payload(result)
        if config.json_output:
            emit_json("logion.credits.top-ups.get", payload)
        else:
            emit_top_up_human(payload)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_credits_top_ups_wait(args: argparse.Namespace) -> int:
    """Poll until a credit top-up reaches a terminal state."""
    bad_id = validate_uuid_arg(args, args.top_up_id, "TOP_UP_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    timeout = min(max(args.wait_timeout, 1), 600)
    interval = max(args.interval, 1)
    try:
        last_status: str | None = None
        last_payload: dict[str, Any] | None = None
        start = time.monotonic()
        while True:
            result = client.v1.credits.get_top_up(top_up_id=args.top_up_id)
            pl = top_up_to_payload(result)
            status = str(pl.get("status"))
            elapsed = time.monotonic() - start
            if status != last_status:
                emit_wait_result(config, pl, elapsed, final=False)
                last_status = status
            last_payload = pl
            if status in TERMINAL_STATUSES or elapsed >= timeout:
                break
            time.sleep(interval)
    except Exception as exc:
        return handle_error(exc)
    finally:
        client.close()
    return resolve_wait(config, last_payload, start, args.top_up_id, timeout)


def _render_ledger(result: object) -> None:
    items = to_data(result)
    if not items:
        sys.stdout.write("No ledger entries.\n")
    else:
        for item in items:
            lines = [
                f"id: {item.get('id')}",
                f"kind: {item.get('kind')}",
                f"direction: {item.get('direction')}",
                f"amount_cents: {item.get('amount_cents')}",
                f"balance_after_cents: {item.get('balance_after_cents')}",
                f"posted_at: {item.get('posted_at')}",
            ]
            if item.get("related_top_up_id"):
                rtup = item.get("related_top_up_id")
                lines.append(f"related_top_up_id: {rtup}")
            sys.stdout.write("\n".join(lines) + "\n---\n")


def handle_credits_ledger(args: argparse.Namespace) -> int:
    """Execute the credits ledger command."""
    config = resolve_config_from_args(args)
    return _run(
        args,
        lambda c: c.list_ledger(),
        "ledger",
        json_output=config.json_output,
        render=_render_ledger,
    )
