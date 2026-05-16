"""Mutation handlers for courses commands."""

from __future__ import annotations

import argparse

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error, print_err, validate_uuid_id
from cli._output import emit
from cli._utils import only_not_none

MUTABLE_UPDATE_FIELDS = [
    "title",
    "description",
    "price_cents",
    "currency",
    "language",
    "short_summary",
    "visibility",
]


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
        emit(result, json_output=config.json_output)
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
        emit(result, json_output=config.json_output)
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
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()
