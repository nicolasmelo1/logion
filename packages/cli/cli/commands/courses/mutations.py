# SPDX-License-Identifier: MIT
"""Mutation handlers for courses commands."""

from __future__ import annotations

import argparse
import sys

from cli._config import resolve_config_from_args
from cli._confirm import require_yes
from cli._context import make_client
from cli._errors import handle_error, print_err, validate_uuid_id
from cli._output import emit, emit_json, to_data
from cli._utils import only_not_none
from cli.commands.courses._capability_render import (
    _append_summary_fields,
    append_approved_capability_summary_lines,
)

MUTABLE_UPDATE_FIELDS = [
    "title",
    "description",
    "price_cents",
    "currency",
    "language",
    "short_summary",
    "visibility",
]


def _append_course_capability_lines(
    lines: list[str],
    data: dict[str, object],
) -> None:
    """Append latest-version capability summary lines for course detail."""
    status = data.get("latest_version_capabilities_status")
    if status:
        lines.append(f"latest_version_capabilities_status: {status}")
    schema_version = data.get("latest_version_capabilities_schema_version")
    if schema_version is not None:
        lines.append(
            f"latest_version_capabilities_schema_version: {schema_version}"
        )
    summary = data.get("latest_version_capabilities_summary")
    if summary and isinstance(summary, dict):
        _append_summary_fields(lines, summary)


def _check_clear_price_conflict(args: argparse.Namespace) -> int | None:
    if args.clear_price and (args.currency or args.clear_currency):
        print_err(
            "Error: --clear-price cannot be used with "
            "--currency or --clear-currency."
        )
        return 2
    return None


def _apply_update_overrides(
    args: argparse.Namespace,
    kwargs: dict[str, object],
) -> None:
    if args.clear_tags:
        kwargs["tags"] = []
    elif args.tags:
        kwargs["tags"] = args.tags
    if args.clear_description:
        kwargs["description"] = None
    if args.clear_short_summary:
        kwargs["short_summary"] = None
    if args.clear_language:
        kwargs["language"] = None
    if args.clear_currency:
        kwargs["currency"] = None
    if args.clear_price:
        kwargs["price_cents"] = None
        kwargs["currency"] = None


def _has_mutable_field(args: argparse.Namespace) -> bool:
    if any(
        getattr(args, field, None) is not None
        for field in MUTABLE_UPDATE_FIELDS
    ):
        return True
    if args.tags:
        return True
    return bool(
        args.clear_tags
        or args.clear_description
        or args.clear_short_summary
        or args.clear_language
        or args.clear_currency
        or args.clear_price
    )


def handle_create(args: argparse.Namespace) -> int:
    """Execute the courses create command."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        kwargs = only_not_none(
            {"title": args.title, "slug": args.slug},
            description=args.description,
            price_cents=args.price_cents,
            currency=args.currency,
            language=args.language,
            short_summary=args.short_summary,
            visibility=args.visibility,
        )
        if args.tags:
            kwargs["tags"] = args.tags
        result = client.v1.courses.create(**kwargs)
        if config.json_output:
            emit_json("logion.courses.create", to_data(result))
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_get(args: argparse.Namespace) -> int:
    """Execute the courses get command."""
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.courses.get(course_id=args.course_id)
        if config.json_output:
            emit(result, json_output=True)
        else:
            data = to_data(result)
            lines: list[str] = [
                f"id: {data['id']}",
                f"owner_agent_id: {data['owner_agent_id']}",
                f"title: {data['title']}",
                f"slug: {data['slug']}",
                f"status: {data['status']}",
                f"visibility: {data['visibility']}",
            ]
            if data.get("description"):
                lines.append(f"description: {data['description']}")
            if data.get("short_summary"):
                lines.append(f"short_summary: {data['short_summary']}")
            lines.append(f"price_cents: {data['price_cents']}")
            lines.append(f"currency: {data['currency']}")
            if data.get("language"):
                lines.append(f"language: {data['language']}")
            if data.get("tags"):
                lines.append(f"tags: {', '.join(data['tags'])}")
            lines.append(f"current_version: {data.get('current_version')}")
            latest_version_id = data.get("latest_version_id")
            if latest_version_id:
                lines.append(f"latest_version_id: {latest_version_id}")
            _append_course_capability_lines(lines, data)
            append_approved_capability_summary_lines(lines, data)
            if data.get("published_at"):
                lines.append(f"published_at: {data['published_at']}")
            lines.append(f"created_at: {data['created_at']}")
            lines.append(f"updated_at: {data['updated_at']}")
            sys.stdout.write("\n".join(lines))
            sys.stdout.write("\n")
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_purchase(args: argparse.Namespace) -> int:
    """Execute the courses purchase command."""
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id
    refusal = require_yes(
        args.yes,
        "purchase this course (spends credits)",
    )
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.courses.purchase(
            course_id=args.course_id,
            expected_price_cents=args.expected_price_cents,
        )
        if config.json_output:
            emit_json("logion.courses.purchase", to_data(result))
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_update(args: argparse.Namespace) -> int:
    """Execute the courses update command."""
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id
    price_conflict = _check_clear_price_conflict(args)
    if price_conflict is not None:
        return price_conflict
    if not _has_mutable_field(args):
        print_err(
            "Error: courses update requires at least one field to change."
        )
        return 2
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        kwargs = only_not_none(
            {"course_id": args.course_id},
            title=args.title,
            description=args.description,
            price_cents=args.price_cents,
            currency=args.currency,
            language=args.language,
            short_summary=args.short_summary,
            visibility=args.visibility,
        )
        _apply_update_overrides(args, kwargs)
        result = client.v1.courses.update(**kwargs)
        if config.json_output:
            emit_json("logion.courses.update", to_data(result))
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()
