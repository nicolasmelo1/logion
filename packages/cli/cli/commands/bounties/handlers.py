# SPDX-License-Identifier: MIT
"""Bounty-level handlers: create, update, list, get, and lifecycle."""

from __future__ import annotations

import argparse
from collections.abc import Callable

from cli._config import resolve_config_from_args
from cli._confirm import require_yes
from cli._context import client_for
from cli._errors import handle_error, print_err, validate_uuid_id
from cli._output import emit, emit_json, to_object
from cli._utils import only_not_none

from ._inputs import parse_datetime
from ._render import github_pr_line

Handler = Callable[[argparse.Namespace], int]

# `logion bounties payout` is gone -- accept accrues a creator-payable
# balance directly, and contributors cash out via
# `logion payments cash-out`. No separate payout step.
LIFECYCLE_COMMANDS: tuple[tuple[str, str, str], ...] = (
    ("open", "update_status", "open this bounty"),
    ("fund", "update_funding", "fund this bounty (credits will be debited)"),
    ("cancel", "delete", "cancel this bounty"),
)


def make_lifecycle_handler(cmd: str, sdk_method: str, action: str) -> Handler:
    """Return a handler for a bounty lifecycle command.

    The three lifecycle commands differ only in which SDK method they
    call and how the confirmation prompt reads, so they share one body.
    """

    def handler(args: argparse.Namespace) -> int:
        bad_id = validate_uuid_id(args.bounty_id, "BOUNTY_ID")
        if bad_id is not None:
            return bad_id
        refusal = require_yes(args.yes, action)
        if refusal is not None:
            return refusal
        config = resolve_config_from_args(args)
        try:
            with client_for(config) as client:
                method = getattr(client.v1.bounties, sdk_method)
                emit(
                    method(bounty_id=args.bounty_id),
                    json_output=config.json_output,
                )
        except Exception as exc:
            return handle_error(exc)
        return 0

    handler.__name__ = f"handle_{cmd}"
    handler.__doc__ = f"Execute the bounties {cmd} command."
    return handler


def handle_create(args: argparse.Namespace) -> int:
    """Execute the bounties create command."""
    bad_id = validate_uuid_id(args.course_id, "--course-id")
    if bad_id is not None:
        return bad_id
    # Validate --submission-deadline before spending a round trip on it.
    if args.submission_deadline is not None:
        try:
            parse_datetime(args.submission_deadline)
        except (ValueError, TypeError) as exc:
            print_err(f"Error: --submission-deadline: {exc}")
            return 2
    config = resolve_config_from_args(args)
    try:
        with client_for(config) as client:
            kwargs = only_not_none(
                {
                    "course_id": args.course_id,
                    "title": args.title,
                    "description": args.description,
                    "reward_amount_cents": args.reward_cents,
                },
                currency=args.currency,
                submission_deadline=parse_datetime(args.submission_deadline),
            )
            kwargs["accepts_github_prs"] = args.accepts_github_prs
            result = client.v1.bounties.create(**kwargs)
            if not config.json_output:
                print(github_pr_line(to_object(result)))
            emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    return 0


def handle_update(args: argparse.Namespace) -> int:
    """Execute the bounties update command."""
    bad_id = validate_uuid_id(args.bounty_id, "BOUNTY_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    try:
        with client_for(config) as client:
            result = client.v1.bounties.update(
                bounty_id=args.bounty_id,
                accepts_github_prs=args.accepts_github_prs,
            )
            if not config.json_output:
                print(github_pr_line(to_object(result)))
            emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    return 0


def handle_list(args: argparse.Namespace) -> int:
    """Execute the bounties list command."""
    config = resolve_config_from_args(args)
    try:
        with client_for(config) as client:
            result = client.v1.bounties.list(
                **only_not_none({}, scope=args.scope)
            )
            if config.json_output:
                emit_json("logion.bounties.list", result)
            else:
                emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    return 0


def handle_get(args: argparse.Namespace) -> int:
    """Execute the bounties get command."""
    bad_id = validate_uuid_id(args.bounty_id, "BOUNTY_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    try:
        with client_for(config) as client:
            result = client.v1.bounties.get(bounty_id=args.bounty_id)
            data = to_object(result)
            if config.json_output:
                emit_json("logion.bounties.get", data)
            else:
                print(github_pr_line(data))
                emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    return 0
