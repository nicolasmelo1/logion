"""Courses commands — create, get, update, upload, and review courses."""

from __future__ import annotations

import argparse
import collections
import mimetypes
from pathlib import Path

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import (
    handle_error,
    print_err,
    validate_uuid_id,
)
from cli._options import COMMON_PARSER
from cli._output import emit
from cli._utils import only_not_none


def _add_tag_arguments(
    parser: argparse.ArgumentParser,
    *,
    default: list[str] | None,
) -> None:
    """Add ``--tag`` and ``--clear-tags`` arguments.

    For ``create`` the default is ``[]`` (append-only, no clear).
    For ``update`` the default is ``None`` (distinguish "no --tag"
    from ``--clear-tags``).
    """
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--tag",
        action="append",
        dest="tags",
        default=default,
        help="Tag to add (can be specified multiple times)",
    )
    if default is None:
        # update mode: can also clear all tags
        group.add_argument(
            "--clear-tags",
            action="store_true",
            help="Remove all tags from the course",
        )


_CMD_HELP = {
    "create": "Create a new course",
    "get": "Get course details",
    "update": "Update an existing course",
    "uploads": "Manage course version uploads",
    "publication": "Manage course publication review",
    "reviews": "Manage marketplace course reviews",
    "feedback": "Get review feedback for a course",
    "versions": "Manage course versions",
}


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``courses`` subcommand group."""
    parser = subparsers.add_parser(
        "courses",
        help="Manage courses",
    )
    sub = parser.add_subparsers(
        dest="courses_command",
        required=True,
    )

    # ── create ───────────────────────────────────────────────────
    create = sub.add_parser(
        "create",
        help=_CMD_HELP["create"],
        parents=[COMMON_PARSER],
    )
    create.add_argument("--title", required=True)
    create.add_argument("--slug", required=True)
    create.add_argument("--description")
    create.add_argument("--price-cents", type=int)
    create.add_argument("--currency")
    _add_tag_arguments(create, default=[])
    create.add_argument("--language")
    create.add_argument("--short-summary")
    create.add_argument(
        "--visibility",
        choices=["public", "unlisted", "private"],
    )
    create.set_defaults(handler=handle_create)

    # ── get ───────────────────────────────────────────────────────
    get = sub.add_parser(
        "get",
        help=_CMD_HELP["get"],
        parents=[COMMON_PARSER],
    )
    get.add_argument("course_id")
    get.set_defaults(handler=handle_get)

    # ── update ────────────────────────────────────────────────────
    update = sub.add_parser(
        "update",
        help=_CMD_HELP["update"],
        parents=[COMMON_PARSER],
    )
    update.add_argument("course_id")
    update.add_argument("--title")
    # description / clear-description are mutually exclusive
    _desc = update.add_mutually_exclusive_group()
    _desc.add_argument("--description")
    _desc.add_argument(
        "--clear-description",
        action="store_true",
        help="Clear the course description",
    )
    # price-cents / clear-price are mutually exclusive.
    # Note: --clear-price also nullifies currency; _check_clear_price_conflict
    # prevents --clear-price + (--currency | --clear-currency) combinations.
    _price = update.add_mutually_exclusive_group()
    _price.add_argument("--price-cents", type=int)
    _price.add_argument(
        "--clear-price",
        action="store_true",
        help=(
            "Clear the course price (price_cents and currency). "
            "Note: this also clears the currency."
        ),
    )
    # currency / clear-currency are mutually exclusive
    _cur = update.add_mutually_exclusive_group()
    _cur.add_argument("--currency")
    _cur.add_argument(
        "--clear-currency",
        action="store_true",
        help="Clear the course currency",
    )
    # language / clear-language are mutually exclusive
    _lang = update.add_mutually_exclusive_group()
    _lang.add_argument("--language")
    _lang.add_argument(
        "--clear-language",
        action="store_true",
        help="Clear the course language",
    )
    # short-summary / clear-short-summary are mutually exclusive
    _ss = update.add_mutually_exclusive_group()
    _ss.add_argument("--short-summary")
    _ss.add_argument(
        "--clear-short-summary",
        action="store_true",
        help="Clear the short summary",
    )
    # tags
    _add_tag_arguments(update, default=None)
    update.add_argument(
        "--visibility",
        choices=["public", "unlisted", "private"],
    )
    update.set_defaults(handler=handle_update)

    # ── uploads sub-group ─────────────────────────────────────────
    uploads = sub.add_parser(
        "uploads",
        help=_CMD_HELP["uploads"],
    )
    uploads_sub = uploads.add_subparsers(
        dest="courses_uploads_command",
        required=True,
    )

    # uploads create
    uc = uploads_sub.add_parser(
        "create",
        help="Create an upload session for a course version",
        parents=[COMMON_PARSER],
    )
    uc.add_argument("course_id")
    uc.add_argument(
        "--file",
        action="append",
        dest="files",
        default=[],
        help=(
            "File path to include in the upload session. "
            "Only the basename is used as the upload path; "
            "directory structure is flattened."
        ),
    )
    uc.set_defaults(handler=handle_uploads_create)

    # uploads complete
    ucomp = uploads_sub.add_parser(
        "complete",
        help="Complete an upload session",
        parents=[COMMON_PARSER],
    )
    ucomp.add_argument("course_id")
    ucomp.add_argument("version_id")
    ucomp.set_defaults(handler=handle_uploads_complete)

    # ── publication sub-group ────────────────────────────────────
    publication = sub.add_parser(
        "publication",
        help=_CMD_HELP["publication"],
    )
    pub_sub = publication.add_subparsers(
        dest="courses_publication_command",
        required=True,
    )

    # publication request
    pr = pub_sub.add_parser(
        "request",
        help="Request publication review",
        parents=[COMMON_PARSER],
    )
    pr.add_argument("course_id")
    pr.set_defaults(handler=handle_publication_request)

    # publication latest
    pl = pub_sub.add_parser(
        "latest",
        help="Get latest publication review status",
        parents=[COMMON_PARSER],
    )
    pl.add_argument("course_id")
    pl.add_argument("--include-pass", action="store_true", default=None)
    pl.set_defaults(handler=handle_publication_latest)

    # ── reviews sub-group ────────────────────────────────────────
    reviews = sub.add_parser(
        "reviews",
        help=_CMD_HELP["reviews"],
    )
    rev_sub = reviews.add_subparsers(
        dest="courses_reviews_command",
        required=True,
    )

    # reviews list
    rl = rev_sub.add_parser(
        "list",
        help="List reviews for a course",
        parents=[COMMON_PARSER],
    )
    rl.add_argument("course_id")
    rl.add_argument("--version")
    rl.add_argument("--limit", type=int)
    rl.add_argument("--cursor")
    rl.set_defaults(handler=handle_reviews_list)

    # reviews mine
    rm = rev_sub.add_parser(
        "mine",
        help="Get your review for a course version",
        parents=[COMMON_PARSER],
    )
    rm.add_argument("course_id")
    rm.add_argument("--version-id")
    rm.set_defaults(handler=handle_reviews_mine)

    # reviews upsert
    ru = rev_sub.add_parser(
        "upsert",
        help="Create or update a review for a course version",
        parents=[COMMON_PARSER],
    )
    ru.add_argument("course_id")
    ru.add_argument("version_id")
    ru.add_argument("--rating", type=int, required=True)
    ru.add_argument("--body")
    _add_tristate_flag(ru, "--completed-task", dest="completed_task")
    ru.add_argument("--reliability", type=float)
    ru.add_argument("--usefulness", type=float)
    ru.add_argument("--tool-safety", type=float)
    ru.add_argument("--token-efficiency", type=float)
    ru.set_defaults(handler=handle_reviews_upsert)

    # ── feedback ─────────────────────────────────────────────────
    feedback = sub.add_parser(
        "feedback",
        help=_CMD_HELP["feedback"],
        parents=[COMMON_PARSER],
    )
    feedback.add_argument("course_id")
    feedback.set_defaults(handler=handle_feedback)

    # ── versions get ─────────────────────────────────────────────
    versions = sub.add_parser(
        "versions",
        help=_CMD_HELP["versions"],
    )
    ver_sub = versions.add_subparsers(
        dest="courses_versions_command",
        required=True,
    )
    vg = ver_sub.add_parser(
        "get",
        help="Get a course version",
        parents=[COMMON_PARSER],
    )
    vg.add_argument("course_id")
    vg.add_argument("version_id")
    vg.set_defaults(handler=handle_versions_get)


def _add_tristate_flag(
    parser: argparse.ArgumentParser,
    flag: str,
    *,
    dest: str,
) -> None:
    """Add a three-state boolean flag.

    ``--flag`` sets True, ``--no-flag`` sets False, omit → None.
    """
    base = flag.removeprefix("--")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        flag,
        dest=dest,
        action="store_true",
        default=None,
    )
    group.add_argument(
        f"--no-{base}",
        dest=dest,
        action="store_false",
        default=None,
    )


# ── Handlers ──────────────────────────────────────────────────────


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
    bad_id = validate_uuid_id(args.course_id, "course_id")
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


def _check_clear_price_conflict(args: argparse.Namespace) -> int | None:
    """Return exit code 2 if --clear-price conflicts with other flags."""
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
    """Mutate *kwargs* with tag and --clear-<field> overrides."""
    if args.clear_tags:
        kwargs["tags"] = []
    elif args.tags:
        kwargs["tags"] = args.tags
    # --clear-<field> explicitly sets nullable fields to None
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


_MUTABLE_UPDATE_FIELDS = [
    "title",
    "description",
    "price_cents",
    "currency",
    "language",
    "short_summary",
    "visibility",
]


def _has_mutable_field(args: argparse.Namespace) -> bool:
    """Return True if at least one mutable field or --clear-* flag was set."""
    if any(getattr(args, f, None) is not None for f in _MUTABLE_UPDATE_FIELDS):
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


def handle_update(args: argparse.Namespace) -> int:
    """Execute the courses update command."""
    bad_id = validate_uuid_id(args.course_id, "course_id")
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
    bad_id = validate_uuid_id(args.course_id, "course_id")
    if bad_id is not None:
        return bad_id
    if not args.files:
        print_err("Error: at least one --file is required")
        return 2
    # Validate all paths exist and check for duplicate basenames
    resolved: list[Path] = []
    for path_str in args.files:
        p = Path(path_str)
        if not p.is_file():
            print_err(f"file not found: {path_str}")
            return 2
        resolved.append(p)
    basenames = [p.name for p in resolved]
    basename_counts = collections.Counter(basenames)
    dupes = [name for name, count in basename_counts.items() if count > 1]
    if dupes:
        print_err(f"duplicate file names not allowed: {sorted(set(dupes))}")
        return 2
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        files = []
        for p in resolved:
            files.append({
                "path": p.name,
                "size_bytes": p.stat().st_size,
                "content_type": mimetypes.guess_type(str(p))[0]
                or "application/octet-stream",
            })
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
    bad_id = validate_uuid_id(args.course_id, "course_id")
    if bad_id is not None:
        return bad_id
    bad_id = validate_uuid_id(args.version_id, "version_id")
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


def handle_publication_request(args: argparse.Namespace) -> int:
    """Execute publication request."""
    bad_id = validate_uuid_id(args.course_id, "course_id")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.courses.request_publication_review(
            course_id=args.course_id,
        )
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_publication_latest(args: argparse.Namespace) -> int:
    """Execute publication latest."""
    bad_id = validate_uuid_id(args.course_id, "course_id")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        kwargs = only_not_none(
            {"course_id": args.course_id},
            include_pass=args.include_pass,
        )
        result = client.v1.courses.get_latest_publication_review(**kwargs)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_reviews_list(args: argparse.Namespace) -> int:
    """Execute the courses reviews list command."""
    bad_id = validate_uuid_id(args.course_id, "course_id")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        kwargs = only_not_none(
            {"course_id": args.course_id},
            version=args.version,
            limit=args.limit,
            cursor=args.cursor,
        )
        result = client.v1.courses.list_reviews(**kwargs)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_reviews_mine(args: argparse.Namespace) -> int:
    """Execute the courses reviews mine command."""
    bad_id = validate_uuid_id(args.course_id, "course_id")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        kwargs = only_not_none(
            {"course_id": args.course_id},
            version_id=args.version_id,
        )
        result = client.v1.courses.get_my_review(**kwargs)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_reviews_upsert(args: argparse.Namespace) -> int:
    """Execute the courses reviews upsert command."""
    bad_id = validate_uuid_id(args.course_id, "course_id")
    if bad_id is not None:
        return bad_id
    bad_id = validate_uuid_id(args.version_id, "version_id")
    if bad_id is not None:
        return bad_id
    # Validate rating range (1-5)
    if args.rating is not None and not (1 <= args.rating <= 5):
        print_err("Error: --rating must be between 1 and 5.")
        return 2
    # Validate sub-score ranges (0.0-5.0, matching rating scale)
    for attr, label in [
        ("reliability", "--reliability"),
        ("usefulness", "--usefulness"),
        ("tool_safety", "--tool-safety"),
        ("token_efficiency", "--token-efficiency"),
    ]:
        val = getattr(args, attr)
        if val is not None and not (0.0 <= val <= 5.0):
            print_err(f"Error: {label} must be between 0.0 and 5.0.")
            return 2
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        kwargs = only_not_none(
            {
                "course_id": args.course_id,
                "version_id": args.version_id,
                "rating": args.rating,
            },
            body=args.body,
            completed_task=args.completed_task,
            reliability=args.reliability,
            usefulness=args.usefulness,
            tool_safety=args.tool_safety,
            token_efficiency=args.token_efficiency,
        )
        result = client.v1.courses.review_version(**kwargs)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_feedback(args: argparse.Namespace) -> int:
    """Execute the courses feedback command."""
    bad_id = validate_uuid_id(args.course_id, "course_id")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.courses.get_review_feedback(
            course_id=args.course_id,
        )
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_versions_get(args: argparse.Namespace) -> int:
    """Execute the courses versions get command."""
    bad_id = validate_uuid_id(args.course_id, "course_id")
    if bad_id is not None:
        return bad_id
    bad_id = validate_uuid_id(args.version_id, "version_id")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.courses.get_version(
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
