# SPDX-License-Identifier: MIT
"""Handlers for feedback commands."""

from __future__ import annotations

import argparse
import sys

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error
from cli._json import JsonObject, children, opt_str
from cli._output import emit_json, to_data, to_items, to_object
from cli._pseudonymous_subject import build_feedback_proof
from cli._receipts import load_receipts
from cli.usage.tombstones import feedback_tombstone, record_feedback


def _resolve_acquisition_channel(
    args: argparse.Namespace,
) -> str:
    """The channel this exact version was acquired through.

    Reading it from the local receipt is what makes the link to the
    acquisition a fact rather than a claim the caller typed. An explicit
    flag still wins, because a resource may have been installed before
    Logion was watching.
    """
    explicit = getattr(args, "acquisition_channel", None)
    if explicit:
        return str(explicit)
    matches: list[JsonObject] = [
        receipt
        for receipt in load_receipts()
        if receipt.get("resource_id") == args.resource_id
        and receipt.get("version_id") == args.version_id
    ]
    channels = {opt_str(receipt, "channel", "") for receipt in matches}
    channels.discard("")
    if len(channels) == 1:
        return channels.pop()
    if not channels:
        raise ValueError(
            "no local acquisition receipt for this resource version —"
            " pass --acquisition-channel to report it explicitly"
        )
    raise ValueError(
        "this version was acquired through more than one channel"
        f" ({', '.join(sorted(channels))}) — pass --acquisition-channel"
    )


def _reject_repeat_submission(args: argparse.Namespace) -> None:
    """Refuse a second submission for one version and task class.

    The API upserts, so a repeat would not duplicate the row — but the
    request still leaves the machine, and a hook that fires twice should
    not become two outbound reports.
    """
    existing = feedback_tombstone(
        args.resource_id, args.version_id, args.task_class
    )
    if existing is not None and not getattr(args, "force", False):
        raise ValueError(
            f"feedback {existing} was already submitted for this"
            " version and task class — re-run with --force to revise it"
        )


def handle_feedback_submit(args: argparse.Namespace) -> int:
    """Execute the feedback submit command."""
    config = resolve_config_from_args(args)
    try:
        acquisition_channel = _resolve_acquisition_channel(args)
        _reject_repeat_submission(args)
    except Exception as exc:
        return handle_error(
            exc,
            json_output=config.json_output,
            handle_validation=True,
        )
    client = make_client(config)
    try:
        pseudonymous_public_key: str | None = None
        pseudonymous_signature: str | None = None
        if not config.api_key:
            proof = build_feedback_proof({
                "resource_id": args.resource_id,
                "version_id": args.version_id,
                "rating": args.rating,
                "acquisition_channel": acquisition_channel,
                "task_class": args.task_class,
                "usefulness": getattr(args, "usefulness", None),
                "reliability": getattr(args, "reliability", None),
                "tool_safety": getattr(args, "tool_safety", None),
                "token_efficiency": getattr(args, "token_efficiency", None),
                "completed_task": getattr(args, "completed_task", None),
                "body": getattr(args, "body", None),
                "source_receipt_id": getattr(args, "source_receipt_id", None),
            })
            pseudonymous_public_key = opt_str(proof, "pseudonymous_public_key")
            pseudonymous_signature = opt_str(proof, "pseudonymous_signature")
        result = client.v1.resource_feedback.submit(
            args.resource_id,
            args.version_id,
            rating=args.rating,
            acquisition_channel=acquisition_channel,
            task_class=args.task_class,
            usefulness=getattr(args, "usefulness", None),
            reliability=getattr(args, "reliability", None),
            tool_safety=getattr(args, "tool_safety", None),
            token_efficiency=getattr(args, "token_efficiency", None),
            completed_task=getattr(args, "completed_task", None),
            body=getattr(args, "body", None),
            source_receipt_id=getattr(args, "source_receipt_id", None),
            pseudonymous_public_key=pseudonymous_public_key,
            pseudonymous_signature=pseudonymous_signature,
        )
        data = to_object(result)
        feedback_id = opt_str(data, "id") or opt_str(data, "feedback_id")
        if feedback_id:
            record_feedback(
                args.resource_id,
                args.version_id,
                args.task_class,
                feedback_id,
            )
        if config.json_output:
            emit_json("logion.feedback.submit", to_data(result))
        else:
            lines = [
                f"feedback_id: {data.get('feedback_id', data.get('id', ''))}",
                f"resource_id: {data.get('resource_id', args.resource_id)}",
                f"version_id: {data.get('version_id', args.version_id)}",
            ]
            if data.get("rating") is not None:
                lines.append(f"rating: {data.get('rating')}")
            sys.stdout.write("\n".join(lines) + "\n")
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_feedback_list(args: argparse.Namespace) -> int:
    """Execute the feedback list command."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.resource_feedback.list_mine()
        if config.json_output:
            emit_json("logion.feedback.list", to_data(result))
        else:
            items = to_items(result)
            if isinstance(items, dict):
                items = children(items, "items")
            if not items:
                sys.stdout.write("No feedback submitted.\n")
            else:
                for item in items:
                    fb_id = item.get("feedback_id", opt_str(item, "id", ""))
                    lines = [
                        f"feedback_id: {fb_id}",
                        f"resource_id: {item.get('resource_id', '')}",
                        f"version_id: {item.get('version_id', '')}",
                        f"rating: {item.get('rating', '')}",
                    ]
                    sys.stdout.write("\n".join(lines) + "\n---\n")
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_feedback_summary(args: argparse.Namespace) -> int:
    """Execute the feedback summary command."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.resource_feedback.get_summary(args.resource_id)
        if config.json_output:
            emit_json("logion.feedback.summary", to_data(result))
        else:
            data = to_object(result)
            lines = [
                f"resource_id: {data.get('resource_id', args.resource_id)}",
                f"total_feedback: {data.get('count', 0)}",
                f"average_rating: {data.get('rating_avg', '')}",
            ]
            sys.stdout.write("\n".join(lines) + "\n")
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()
