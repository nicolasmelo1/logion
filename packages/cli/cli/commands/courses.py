"""Courses commands — create, get, update, upload, and review courses."""

from __future__ import annotations

import argparse
from typing import Any

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error
from cli._options import COMMON_PARSER
from cli._output import emit

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
    create.add_argument("--tag", action="append", dest="tags", default=[])
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
    update.add_argument("--description")
    update.add_argument("--price-cents", type=int)
    update.add_argument("--currency")
    update.add_argument("--language")
    update.add_argument("--short-summary")
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
        help="File path to include in the upload session",
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
    _bool_flag(ru, "--completed-task", dest="completed_task")
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


def _bool_flag(
    parser: argparse.ArgumentParser,
    flag: str,
    *,
    dest: str,
) -> None:
    """Add a three-state boolean flag.

    ``--flag`` sets True, ``--no-flag`` sets False, omit → None.
    """
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        flag,
        dest=dest,
        action="store_true",
        default=None,
    )
    group.add_argument(
        f"--no-{flag.lstrip('-')}",
        dest=dest,
        action="store_false",
    )


# ── Handlers ──────────────────────────────────────────────────────


def handle_create(args: argparse.Namespace) -> int:
    """Execute the courses create command."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.courses.create(
            title=args.title,
            slug=args.slug,
            description=args.description,
            price_cents=args.price_cents,
            tags=args.tags or None,
            language=args.language,
            currency=args.currency,
            short_summary=args.short_summary,
            visibility=args.visibility,
        )
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_get(args: argparse.Namespace) -> int:
    """Execute the courses get command."""
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
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        kwargs: dict[str, Any] = {"course_id": args.course_id}
        if args.title is not None:
            kwargs["title"] = args.title
        if args.description is not None:
            kwargs["description"] = args.description
        if args.price_cents is not None:
            kwargs["price_cents"] = args.price_cents
        if args.currency is not None:
            kwargs["currency"] = args.currency
        if args.language is not None:
            kwargs["language"] = args.language
        if args.short_summary is not None:
            kwargs["short_summary"] = args.short_summary
        if args.visibility is not None:
            kwargs["visibility"] = args.visibility
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
    import mimetypes
    from pathlib import Path

    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        files = []
        for path_str in args.files:
            p = Path(path_str)
            files.append({
                "path": path_str,
                "size_bytes": p.stat().st_size,
                "content_type": mimetypes.guess_type(path_str)[0]
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
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.courses.get_latest_publication_review(
            course_id=args.course_id,
            include_pass=args.include_pass,
        )
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_reviews_list(args: argparse.Namespace) -> int:
    """Execute the courses reviews list command."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.courses.list_reviews(
            course_id=args.course_id,
            version=getattr(args, "version", None),
            limit=args.limit,
            cursor=getattr(args, "cursor", None),
        )
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_reviews_mine(args: argparse.Namespace) -> int:
    """Execute the courses reviews mine command."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.courses.get_my_review(
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


def handle_reviews_upsert(args: argparse.Namespace) -> int:
    """Execute the courses reviews upsert command."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        kwargs: dict[str, Any] = {
            "course_id": args.course_id,
            "version_id": args.version_id,
            "rating": args.rating,
        }
        if args.body is not None:
            kwargs["body"] = args.body
        if args.completed_task is not None:
            kwargs["completed_task"] = args.completed_task
        if args.reliability is not None:
            kwargs["reliability"] = args.reliability
        if args.usefulness is not None:
            kwargs["usefulness"] = args.usefulness
        if args.tool_safety is not None:
            kwargs["tool_safety"] = args.tool_safety
        if args.token_efficiency is not None:
            kwargs["token_efficiency"] = args.token_efficiency
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
