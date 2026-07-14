# SPDX-License-Identifier: MIT
"""``logion courses source-link`` — manage course-to-repo links.

Subcommands:
  set    — PUT /courses/{id}/source-link
  show   — GET /courses/{id}/source-link
  remove — DELETE /courses/{id}/source-link (gated by --yes)
"""

from __future__ import annotations

import argparse
import sys

from cli._config import resolve_config_from_args
from cli._confirm import require_yes
from cli._context import make_client
from cli._errors import (
    ALLOWED_ERROR_CODES,
    emit_error_json,
    handle_error,
    print_err,
    validate_uuid_id,
)
from cli._options import COMMON_PARSER
from cli._output import emit_json, to_data

_SET_KIND = "logion.courses.source-link.set"
_SHOW_KIND = "logion.courses.source-link.show"
_REMOVE_KIND = "logion.courses.source-link.remove"


def _handle_source_link_error(exc: Exception, *, json_output: bool) -> int:
    if not json_output:
        return handle_error(exc)

    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        return handle_error(exc)
    detail = getattr(exc, "detail", str(exc))
    if isinstance(detail, list):
        detail = "; ".join(str(item) for item in detail)
    message = str(detail)
    if message in ALLOWED_ERROR_CODES:
        code = message
    elif status_code == 401:
        code = "auth_missing"
    elif status_code == 404:
        code = "not_found"
    elif status_code >= 500:
        code = "server_error"
    else:
        code = "validation_failed"
    emit_error_json(code, message, 1)
    return 1


def handle_set(args: argparse.Namespace) -> int:
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.courses.set_source_link(
            course_id=args.course_id,
            repository=args.repository,
            ref=args.ref,
            package_map_path=args.map,
        )
        data = to_data(result)
        if config.json_output:
            emit_json(_SET_KIND, data)
        else:
            _emit_set_human(data)
    except Exception as exc:
        return _handle_source_link_error(exc, json_output=config.json_output)
    else:
        return 0
    finally:
        client.close()


def handle_show(args: argparse.Namespace) -> int:
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.courses.get_source_link(
            course_id=args.course_id,
        )
        data = to_data(result)
        if config.json_output:
            emit_json(_SHOW_KIND, data)
        else:
            _emit_show_human(data)
    except Exception as exc:
        status_code = getattr(exc, "status_code", None)
        if status_code == 404:
            message = f"No source link found for course {args.course_id}."
            if config.json_output:
                emit_error_json("not_found", message, 1)
            else:
                print_err(message)
            return 1
        return _handle_source_link_error(exc, json_output=config.json_output)
    else:
        return 0
    finally:
        client.close()


def handle_remove(args: argparse.Namespace) -> int:
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id
    refusal = require_yes(args.yes, "revoke this course's source link")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        client.v1.courses.delete_source_link(
            course_id=args.course_id,
        )
        if config.json_output:
            emit_json(
                _REMOVE_KIND, {"course_id": args.course_id, "revoked": True}
            )
        else:
            sys.stdout.write(
                f"Source link revoked for course {args.course_id}.\n"
            )
    except Exception as exc:
        return _handle_source_link_error(exc, json_output=config.json_output)
    else:
        return 0
    finally:
        client.close()


def _emit_set_human(data: dict[str, object]) -> None:
    lines: list[str] = []
    repo = data.get("repository")
    if repo is not None:
        lines.append(f"repository: {repo}")
    ref = data.get("default_ref")
    if ref is not None:
        lines.append(f"default_ref: {ref}")
    status = data.get("status")
    if status is not None:
        lines.append(f"status: {status}")
    if lines:
        sys.stdout.write("\n".join(lines) + "\n")


def _emit_show_human(data: dict[str, object]) -> None:
    lines: list[str] = []
    repo = data.get("repository")
    if repo is not None:
        lines.append(f"repository: {repo}")
    ref = data.get("default_ref")
    if ref is not None:
        lines.append(f"default_ref: {ref}")
    status = data.get("status")
    if status is not None:
        lines.append(f"status: {status}")
    provider = data.get("provider")
    if provider is not None:
        lines.append(f"provider: {provider}")
    if lines:
        sys.stdout.write("\n".join(lines) + "\n")
    else:
        sys.stdout.write("No source link found.\n")


def register_source_link(sub: argparse._SubParsersAction) -> None:
    """Register the ``courses source-link`` subgroup."""
    parser = sub.add_parser(
        "source-link",
        help="Manage the GitHub source link for a course",
    )
    sl_sub = parser.add_subparsers(
        dest="courses_source_link_command",
        required=True,
    )

    set_cmd = sl_sub.add_parser(
        "set",
        help="Set or update the GitHub source link for a course",
        parents=[COMMON_PARSER],
    )
    set_cmd.add_argument("course_id", metavar="COURSE_ID")
    set_cmd.add_argument(
        "--repository",
        required=True,
        help="GitHub repository in 'owner/repo' format.",
    )
    set_cmd.add_argument(
        "--ref",
        default="main",
        help="Default git ref (default: main).",
    )
    set_cmd.add_argument(
        "--map",
        default=None,
        help="Package map path within the repo"
        " (default: logion-package-map.yaml).",
    )
    set_cmd.set_defaults(handler=handle_set)

    show_cmd = sl_sub.add_parser(
        "show",
        help="Show the source link for a course",
        parents=[COMMON_PARSER],
    )
    show_cmd.add_argument("course_id", metavar="COURSE_ID")
    show_cmd.set_defaults(handler=handle_show)

    remove_cmd = sl_sub.add_parser(
        "remove",
        help="Revoke the source link for a course",
        parents=[COMMON_PARSER],
    )
    remove_cmd.add_argument("course_id", metavar="COURSE_ID")
    remove_cmd.add_argument(
        "--yes",
        action="store_true",
        default=False,
        help="Confirm the destructive action.",
    )
    remove_cmd.set_defaults(handler=handle_remove)
