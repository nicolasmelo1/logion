# SPDX-License-Identifier: MIT
"""Handlers for course-reviews commands."""

from __future__ import annotations

import argparse
import json
import sys

from pydantic import BaseModel

from cli._config import resolve_config_from_args
from cli._confirm import require_yes
from cli._context import make_client
from cli._errors import handle_error, print_err, validate_uuid_id
from cli._output import emit
from cli._utils import only_not_none
from cli.commands.course_reviews._render import (
    append_queue_capability_summary_lines,
    append_review_capability_evidence_lines,
)

REQUIRE_NON_EMPTY_MSG = "Error: {} must not be empty."


def handle_list(args: argparse.Namespace) -> int:
    """Execute course-reviews list."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        kwargs = only_not_none({}, limit=args.limit, cursor=args.cursor)
        result = client.v1.course_reviews.list(**kwargs)
        if config.json_output:
            emit(result, json_output=True)
        else:
            _render_list(result)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_get(args: argparse.Namespace) -> int:
    """Execute course-reviews get."""
    bad_id = validate_uuid_id(args.review_id, "REVIEW_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.course_reviews.get(review_id=args.review_id)
        if config.json_output:
            emit(result, json_output=True)
        else:
            _render_get(result)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_approve(args: argparse.Namespace) -> int:
    """Execute course-reviews approve."""
    bad_id = validate_uuid_id(args.review_id, "REVIEW_ID")
    if bad_id is not None:
        return bad_id
    if args.reviewer_notes is not None and not args.reviewer_notes.strip():
        print_err(REQUIRE_NON_EMPTY_MSG.format("--reviewer-notes"))
        return 2
    refusal = require_yes(args.yes, "approve this review")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        kwargs = only_not_none(
            {"review_id": args.review_id},
            reviewer_notes=args.reviewer_notes,
            acknowledge_capability_mismatches=(
                args.acknowledge_capability_mismatches or None
            ),
        )
        result = client.v1.course_reviews.approve(**kwargs)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_reject(args: argparse.Namespace) -> int:
    """Execute course-reviews reject."""
    bad_id = validate_uuid_id(args.review_id, "REVIEW_ID")
    if bad_id is not None:
        return bad_id
    if not args.decision_reason.strip():
        print_err(REQUIRE_NON_EMPTY_MSG.format("--decision-reason"))
        return 2
    if not args.reviewer_notes.strip():
        print_err(REQUIRE_NON_EMPTY_MSG.format("--reviewer-notes"))
        return 2
    refusal = require_yes(args.yes, "reject this review")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.course_reviews.reject(
            review_id=args.review_id,
            decision_reason=args.decision_reason,
            reviewer_notes=args.reviewer_notes,
            capability_reason_code=args.capability_reason_code,
        )
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


# ── Human-readable rendering helpers ────────────────────────────


def _to_data(value: object) -> dict:
    """Convert a Pydantic model or dict to a plain dict."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    return json.loads(json.dumps(value))


def _render_list(result: object) -> None:
    """Render queue list with human-readable capability summary."""
    data = _to_data(result)
    items = data.get("items", [])
    if not items:
        sys.stdout.write("No reviews in the queue.\n")
        return
    for item in items:
        course = (
            f"{item.get('course_title', '')} ({item.get('course_id', '')})"
        )
        lines: list[str] = [
            f"review_id: {item.get('review_id', '')}",
            f"course: {course}",
            f"status: {item.get('review_status', '')}",
            f"findings: {item.get('finding_count', 0)}",
        ]
        append_queue_capability_summary_lines(lines, item)
        sys.stdout.write("\n".join(lines) + "\n\n")


def _render_get(result: object) -> None:
    """Render review detail with human-readable capability evidence."""
    data = _to_data(result)
    course = f"{data.get('course_title', '')} ({data.get('course_id', '')})"
    lines: list[str] = [
        f"review_id: {data.get('review_id', '')}",
        f"course: {course}",
        f"version_id: {data.get('version_id', '')}",
        f"status: {data.get('review_status', '')}",
        f"owner_agent_id: {data.get('owner_agent_id', '')}",
        f"submitted_at: {data.get('submitted_at', '')}",
    ]
    append_review_capability_evidence_lines(lines, data)

    findings_by_layer = data.get("findings_by_layer", {})
    if findings_by_layer:
        lines.append("findings:")
        for layer, findings in findings_by_layer.items():
            lines.append(f"  {layer}:")
            for f in findings:
                severity = f.get("severity", "unknown")
                rule_id = f.get("rule_id", "unknown")
                desc = f.get("description", "")
                pass_marker = " [PASS]" if f.get("is_pass") else ""
                lines.append(f"    - {severity}: {rule_id}{pass_marker}")
                if desc:
                    lines.append(f"      {desc}")

    sys.stdout.write("\n".join(lines) + "\n")
