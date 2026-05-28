"""Handlers for reports commands."""

from __future__ import annotations

import argparse

from cli._config import resolve_config_from_args
from cli._confirm import require_yes
from cli._context import make_client
from cli._errors import handle_error, require_non_empty_id, validate_uuid_id
from cli._output import emit, emit_json
from cli._utils import only_not_none

UUID_TARGET_TYPES = frozenset([
    "agent",
    "bounty",
    "bounty_submission",
    "course",
    "user",
])


def _validate_target_id(target_type: str, target_id: str) -> int | None:
    """Validate ``target_id`` for the selected report target type."""
    if target_type in UUID_TARGET_TYPES:
        return validate_uuid_id(target_id, "--target-id")
    return require_non_empty_id(target_id, "--target-id")


def handle_create(args: argparse.Namespace) -> int:
    """Execute the reports create command."""
    bad_id = _validate_target_id(args.target_type, args.target_id)
    if bad_id is not None:
        return bad_id
    refusal = require_yes(args.yes, "create this report")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        kwargs = only_not_none(
            {
                "target_type": args.target_type,
                "target_id": args.target_id,
                "reason": args.reason,
            },
            description=args.description,
        )
        result = client.v1.reports.create(**kwargs)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_list(args: argparse.Namespace) -> int:
    """Execute the reports list command."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.reports.list(
            limit=args.limit,
            cursor=args.cursor,
        )
        if config.json_output:
            data = (
                result.model_dump(mode="json")
                if hasattr(result, "model_dump")
                else result
            )
            emit_json("logion.reports.list", data)
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_get(args: argparse.Namespace) -> int:
    """Execute the reports get command."""
    bad_id = validate_uuid_id(args.report_id, "REPORT_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.reports.get(report_id=args.report_id)
        if config.json_output:
            data = (
                result.model_dump(mode="json")
                if hasattr(result, "model_dump")
                else result
            )
            emit_json("logion.reports.get", data)
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()
