# SPDX-License-Identifier: MIT
"""Handlers for referrals commands."""

from __future__ import annotations

import argparse

from cli._confirm import require_yes
from cli._context import make_client
from cli._errors import handle_error, validate_uuid_id
from cli._output import emit_json, to_data

from ._helpers import (
    emit_attributions_human,
    emit_code_human,
    emit_link_human,
    emit_stats_human,
)


def _run(
    args: argparse.Namespace,
    fn,
    kind: str,
    *,
    json_output: bool,
    render=None,
):
    """Call *fn* on the referrals resource and emit the result."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = fn(client.v1.referrals)
        if json_output:
            emit_json(f"logion.referrals.{kind}", to_data(result))
        elif render:
            render(result)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_referrals_code(args: argparse.Namespace) -> int:
    """Execute the referrals code command."""
    return _run(
        args,
        lambda r: r.get_code(),
        "code",
        json_output=getattr(args, "json_output", False),
        render=emit_code_human,
    )


def handle_referrals_link(args: argparse.Namespace) -> int:
    """Execute the referrals link command."""
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id
    refusal = require_yes(
        args.yes,
        "share this referral link",
    )
    if refusal is not None:
        return refusal
    return _run(
        args,
        lambda r: r.get_link(course_id=args.course_id),
        "link",
        json_output=getattr(args, "json_output", False),
        render=emit_link_human,
    )


def handle_referrals_stats(args: argparse.Namespace) -> int:
    """Execute the referrals stats command."""
    return _run(
        args,
        lambda r: r.get_stats(),
        "stats",
        json_output=getattr(args, "json_output", False),
        render=emit_stats_human,
    )


def handle_referrals_attributions(args: argparse.Namespace) -> int:
    """Execute the referrals attributions command."""
    return _run(
        args,
        lambda r: r.list_attributions(),
        "attributions",
        json_output=getattr(args, "json_output", False),
        render=emit_attributions_human,
    )


# Late import to avoid circulars at module scope
from cli._config import resolve_config_from_args  # noqa: E402
