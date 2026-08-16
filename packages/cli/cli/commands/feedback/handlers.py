# SPDX-License-Identifier: MIT
"""Handlers for feedback commands."""

from __future__ import annotations

import argparse
import sys

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error
from cli._json import elements, opt_str
from cli._output import emit_json, to_data, to_items, to_object


def handle_feedback_submit(args: argparse.Namespace) -> int:
    """Execute the feedback submit command."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.resource_feedback.submit(
            args.resource_id,
            args.version_id,
            rating=args.rating,
            acquisition_channel=args.acquisition_channel,
            task_class=args.task_class,
            usefulness=getattr(args, "usefulness", None),
            reliability=getattr(args, "reliability", None),
            tool_safety=getattr(args, "tool_safety", None),
            token_efficiency=getattr(args, "token_efficiency", None),
            completed_task=getattr(args, "completed_task", None),
            body=getattr(args, "body", None),
            source_receipt_id=getattr(args, "source_receipt_id", None),
        )
        if config.json_output:
            emit_json("logion.feedback.submit", to_data(result))
        else:
            data = to_object(result)
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
                items = elements(items, "items")
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
