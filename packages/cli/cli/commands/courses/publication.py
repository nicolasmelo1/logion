# SPDX-License-Identifier: MIT
"""Publication handlers for courses commands."""

from __future__ import annotations

import argparse

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error, validate_uuid_id
from cli._output import emit, emit_json, to_data
from cli._utils import only_not_none


def handle_publication_request(args: argparse.Namespace) -> int:
    """Execute publication request."""
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.courses.request_publication_review(
            course_id=args.course_id,
        )
        if config.json_output:
            emit_json("logion.courses.publication.request", to_data(result))
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_publication_latest(args: argparse.Namespace) -> int:
    """Execute publication latest."""
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
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
        if config.json_output:
            emit_json("logion.courses.publication.latest", to_data(result))
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()
