"""Mutation and upload handlers for courses commands."""

from __future__ import annotations

import argparse
import collections
import mimetypes
from pathlib import Path

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


def _parse_upload_file_spec(spec: str) -> tuple[str, Path]:
    """Return ``(upload_path, file_path)`` from a ``--file`` argument."""
    if "=" not in spec:
        file_path = Path(spec)
        return (file_path.name, file_path)

    upload_path, file_path_str = spec.split("=", 1)
    if not upload_path.strip():
        raise ValueError("upload path before '=' must not be empty")
    return (upload_path, Path(file_path_str))


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


def handle_uploads_create(args: argparse.Namespace) -> int:
    """Execute the courses uploads create command."""
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id
    if not args.files:
        print_err("Error: at least one --file is required")
        return 2

    resolved: list[tuple[str, Path]] = []
    for file_spec in args.files:
        try:
            upload_path, path = _parse_upload_file_spec(file_spec)
        except ValueError as exc:
            print_err(f"Error: {exc}")
            return 2
        if not path.is_file():
            print_err(f"file not found: {path}")
            return 2
        resolved.append((upload_path, path))

    duplicates = [
        name
        for name, count in collections.Counter(
            upload_path for upload_path, _ in resolved
        ).items()
        if count > 1
    ]
    if duplicates:
        print_err(
            f"duplicate file names not allowed: {sorted(set(duplicates))}"
        )
        return 2

    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        files = [
            {
                "path": upload_path,
                "size_bytes": path.stat().st_size,
                "content_type": mimetypes.guess_type(str(path))[0]
                or "application/octet-stream",
            }
            for upload_path, path in resolved
        ]
        result = client.v1.courses.create_upload_session(
            course_id=args.course_id,
            files=files,
        )
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_uploads_complete(args: argparse.Namespace) -> int:
    """Execute the courses uploads complete command."""
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id
    bad_id = validate_uuid_id(args.version_id, "VERSION_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.courses.complete_upload_session(
            course_id=args.course_id,
            version_id=args.version_id,
        )
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()
