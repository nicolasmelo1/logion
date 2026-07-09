# SPDX-License-Identifier: MIT
"""Bounties commands — create, list, get, lifecycle, submissions."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from cli._config import resolve_config_from_args
from cli._confirm import require_yes
from cli._context import make_client
from cli._errors import (
    handle_error,
    print_err,
    validate_uuid_id,
)
from cli._options import COMMON_PARSER
from cli._output import emit, emit_json, to_data
from cli._utils import only_not_none
from cli.commands import workspace as _workspace


def parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO-8601 datetime string, treating trailing Z as UTC."""
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_evidence(path: Path | None) -> dict[str, object] | None:
    """Load a JSON evidence file, returning None if *path* is None.

    Returns ``None`` and prints a user-facing error when the file
    is missing or contains invalid JSON.
    """
    if path is None:
        return None
    try:
        return json.loads(path.read_text())  # type: ignore[no-any-return]
    except (OSError, json.JSONDecodeError) as exc:
        print_err(f"Error: evidence JSON must be valid: {exc}")
        return None


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``bounties`` subcommand group."""
    parser = subparsers.add_parser(
        "bounties",
        help="Manage bounties",
    )
    sub = parser.add_subparsers(
        dest="bounties_command",
        required=True,
    )

    # ── create ──────────────────────────────────────────────────
    create = sub.add_parser(
        "create",
        help="Create a new bounty",
        parents=[COMMON_PARSER],
    )
    create.add_argument("--course-id", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--description", required=True)
    create.add_argument("--reward-cents", required=True, type=int)
    create.add_argument("--currency")
    create.add_argument("--submission-deadline")
    create.set_defaults(handler=handle_create)

    # ── list ────────────────────────────────────────────────────
    ls = sub.add_parser(
        "list",
        help="List bounties",
        parents=[COMMON_PARSER],
    )
    ls.add_argument("--scope", choices=["mine", "open", "funded"])
    ls.set_defaults(handler=handle_list)

    # ── get ──────────────────────────────────────────────────────
    get = sub.add_parser(
        "get",
        help="Get bounty details",
        parents=[COMMON_PARSER],
    )
    get.add_argument("bounty_id", metavar="BOUNTY_ID")
    get.set_defaults(handler=handle_get)

    # ── lifecycle commands (open / fund / cancel) ───────────────
    # `logion bounties payout` is gone — accept accrues a
    # creator-payable balance directly, and contributors cash out via
    # `logion payments cash-out`. No separate payout step.
    for cmd, sdk_method, action in [
        ("open", "update_status", "open this bounty"),
        (
            "fund",
            "update_funding",
            "fund this bounty (credits will be debited)",
        ),
        ("cancel", "delete", "cancel this bounty"),
    ]:
        p = sub.add_parser(
            cmd,
            help=f"{cmd.capitalize()} a bounty",
            parents=[COMMON_PARSER],
        )
        p.add_argument("bounty_id", metavar="BOUNTY_ID")
        p.add_argument("--yes", action="store_true")
        handler = _make_lifecycle_handler(cmd, sdk_method, action)
        p.set_defaults(handler=handler)

    # ── submissions sub-group ────────────────────────────────────
    submissions = sub.add_parser(
        "submissions",
        help="Manage bounty submissions",
    )
    sub_sub = submissions.add_subparsers(
        dest="bounties_submissions_command",
        required=True,
    )

    # submissions create
    sc = sub_sub.add_parser(
        "create",
        help="Create a submission for a bounty",
        parents=[COMMON_PARSER],
    )
    sc.add_argument("bounty_id", metavar="BOUNTY_ID")
    sc.add_argument("--title", required=True)
    sc.add_argument("--description")
    sc.add_argument("--evidence-json", type=Path, metavar="PATH")
    sc.add_argument("--proposed-course-version-id")
    sc.set_defaults(handler=handle_submissions_create)

    # submissions list
    sl = sub_sub.add_parser(
        "list",
        help="List submissions for a bounty",
        parents=[COMMON_PARSER],
    )
    sl.add_argument("bounty_id", metavar="BOUNTY_ID")
    sl.set_defaults(handler=handle_submissions_list)

    # submissions get
    sg = sub_sub.add_parser(
        "get",
        help="Get submission details",
        parents=[COMMON_PARSER],
    )
    sg.add_argument("bounty_id", metavar="BOUNTY_ID")
    sg.add_argument("submission_id", metavar="SUBMISSION_ID")
    sg.set_defaults(handler=handle_submissions_get)

    # submissions accept
    sa = sub_sub.add_parser(
        "accept",
        help="Accept a submission",
        parents=[COMMON_PARSER],
    )
    sa.add_argument("bounty_id", metavar="BOUNTY_ID")
    sa.add_argument("submission_id", metavar="SUBMISSION_ID")
    sa.add_argument("--yes", action="store_true")
    sa.set_defaults(handler=handle_submissions_accept)

    # submissions reject
    sr = sub_sub.add_parser(
        "reject",
        help="Reject a submission",
        parents=[COMMON_PARSER],
    )
    sr.add_argument("bounty_id", metavar="BOUNTY_ID")
    sr.add_argument("submission_id", metavar="SUBMISSION_ID")
    sr.add_argument("--yes", action="store_true")
    sr.set_defaults(handler=handle_submissions_reject)

    # submissions withdraw
    sw = sub_sub.add_parser(
        "withdraw",
        help="Withdraw a submission",
        parents=[COMMON_PARSER],
    )
    sw.add_argument("bounty_id", metavar="BOUNTY_ID")
    sw.add_argument("submission_id", metavar="SUBMISSION_ID")
    sw.add_argument("--yes", action="store_true")
    sw.set_defaults(handler=handle_submissions_withdraw)

    # submissions open-pr
    sop = sub_sub.add_parser(
        "open-pr",
        help="Open a draft GitHub PR for a submitted bounty submission",
        parents=[COMMON_PARSER],
    )
    sop.add_argument("bounty_id", metavar="BOUNTY_ID")
    sop.add_argument("submission_id", metavar="SUBMISSION_ID")
    sop.set_defaults(handler=handle_submissions_open_pr)

    # submissions register-pr
    srp = sub_sub.add_parser(
        "register-pr",
        help=(
            "Register an existing GitHub PR for a submitted bounty submission"
        ),
        parents=[COMMON_PARSER],
    )
    srp.add_argument("bounty_id", metavar="BOUNTY_ID")
    srp.add_argument("submission_id", metavar="SUBMISSION_ID")
    srp.add_argument("--pr-number", required=True, type=int)
    srp.set_defaults(handler=handle_submissions_register_pr)

    # ── workspace sub-group ──────────────────────────────────────
    _workspace.register(sub)


# ── Lifecycle handler factory ────────────────────────────────────


def _make_lifecycle_handler(cmd: str, sdk_method: str, action: str):
    """Return a handler function for a bounty lifecycle command."""

    def handler(args: argparse.Namespace) -> int:
        bad_id = validate_uuid_id(args.bounty_id, "BOUNTY_ID")
        if bad_id is not None:
            return bad_id
        refusal = require_yes(args.yes, action)
        if refusal is not None:
            return refusal
        config = resolve_config_from_args(args)
        client = make_client(config)
        try:
            method = getattr(client.v1.bounties, sdk_method)
            result = method(bounty_id=args.bounty_id)
            emit(result, json_output=config.json_output)
        except Exception as exc:
            return handle_error(exc)
        else:
            return 0
        finally:
            client.close()

    handler.__name__ = f"handle_{cmd}"
    handler.__doc__ = f"Execute the bounties {cmd} command."
    return handler


# ── Handlers ──────────────────────────────────────────────────────


def handle_create(args: argparse.Namespace) -> int:
    """Execute the bounties create command."""
    bad_id = validate_uuid_id(args.course_id, "--course-id")
    if bad_id is not None:
        return bad_id
    # Validate --submission-deadline format early
    if args.submission_deadline is not None:
        try:
            parse_datetime(args.submission_deadline)
        except (ValueError, TypeError) as exc:
            print_err(f"Error: --submission-deadline: {exc}")
            return 2
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        kwargs = only_not_none(
            {
                "course_id": args.course_id,
                "title": args.title,
                "description": args.description,
                "reward_amount_cents": args.reward_cents,
            },
            currency=args.currency,
            submission_deadline=parse_datetime(args.submission_deadline),
        )
        result = client.v1.bounties.create(**kwargs)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_list(args: argparse.Namespace) -> int:
    """Execute the bounties list command."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        kwargs = only_not_none(
            {},
            scope=args.scope,
        )
        result = client.v1.bounties.list(**kwargs)
        if config.json_output:
            data = (
                result.model_dump(mode="json")
                if hasattr(result, "model_dump")
                else to_data(result)
            )
            emit_json("logion.bounties.list", data)
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_get(args: argparse.Namespace) -> int:
    """Execute the bounties get command."""
    bad_id = validate_uuid_id(args.bounty_id, "BOUNTY_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.bounties.get(bounty_id=args.bounty_id)
        if config.json_output:
            data = (
                result.model_dump(mode="json")
                if hasattr(result, "model_dump")
                else to_data(result)
            )
            emit_json("logion.bounties.get", data)
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


# ── Submission handlers ──────────────────────────────────────────


def handle_submissions_create(args: argparse.Namespace) -> int:
    """Execute the bounties submissions create command."""
    bad_id = validate_uuid_id(args.bounty_id, "BOUNTY_ID")
    if bad_id is not None:
        return bad_id
    if args.proposed_course_version_id is not None:
        bad_id = validate_uuid_id(
            args.proposed_course_version_id,
            "--proposed-course-version-id",
        )
        if bad_id is not None:
            return bad_id
    evidence = load_evidence(args.evidence_json)
    if args.evidence_json is not None and evidence is None:
        return 2
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        kwargs = only_not_none(
            {
                "bounty_id": args.bounty_id,
                "title": args.title,
            },
            description=args.description,
            evidence=evidence,
            proposed_course_version_id=args.proposed_course_version_id,
        )
        result = client.v1.bounties.create_submission(**kwargs)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_submissions_list(args: argparse.Namespace) -> int:
    """Execute the bounties submissions list command."""
    bad_id = validate_uuid_id(args.bounty_id, "BOUNTY_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.bounties.list_submissions(bounty_id=args.bounty_id)
        if config.json_output:
            data = (
                result.model_dump(mode="json")
                if hasattr(result, "model_dump")
                else to_data(result)
            )
            emit_json("logion.bounties.submissions.list", data)
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_submissions_get(args: argparse.Namespace) -> int:
    """Execute the bounties submissions get command."""
    bad_id = validate_uuid_id(args.bounty_id, "BOUNTY_ID")
    if bad_id is not None:
        return bad_id
    bad_id = validate_uuid_id(args.submission_id, "SUBMISSION_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.bounties.get_submission(
            bounty_id=args.bounty_id,
            submission_id=args.submission_id,
        )
        if config.json_output:
            data = (
                result.model_dump(mode="json")
                if hasattr(result, "model_dump")
                else to_data(result)
            )
            emit_json("logion.bounties.submissions.get", data)
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_submissions_accept(args: argparse.Namespace) -> int:
    """Execute the bounties submissions accept command."""
    bad_id = validate_uuid_id(args.bounty_id, "BOUNTY_ID")
    if bad_id is not None:
        return bad_id
    bad_id = validate_uuid_id(args.submission_id, "SUBMISSION_ID")
    if bad_id is not None:
        return bad_id
    refusal = require_yes(args.yes, "accept this submission")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.bounties.accept_submission(
            bounty_id=args.bounty_id,
            submission_id=args.submission_id,
        )
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_submissions_reject(args: argparse.Namespace) -> int:
    """Execute the bounties submissions reject command."""
    bad_id = validate_uuid_id(args.bounty_id, "BOUNTY_ID")
    if bad_id is not None:
        return bad_id
    bad_id = validate_uuid_id(args.submission_id, "SUBMISSION_ID")
    if bad_id is not None:
        return bad_id
    refusal = require_yes(args.yes, "reject this submission")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.bounties.reject_submission(
            bounty_id=args.bounty_id,
            submission_id=args.submission_id,
        )
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_submissions_withdraw(args: argparse.Namespace) -> int:
    """Execute the bounties submissions withdraw command."""
    bad_id = validate_uuid_id(args.bounty_id, "BOUNTY_ID")
    if bad_id is not None:
        return bad_id
    bad_id = validate_uuid_id(args.submission_id, "SUBMISSION_ID")
    if bad_id is not None:
        return bad_id
    refusal = require_yes(args.yes, "withdraw this submission")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.bounties.delete_submission(
            bounty_id=args.bounty_id,
            submission_id=args.submission_id,
        )
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_submissions_open_pr(args: argparse.Namespace) -> int:
    """Execute the bounties submissions open-pr command."""
    bad_id = validate_uuid_id(args.bounty_id, "BOUNTY_ID")
    if bad_id is not None:
        return bad_id
    bad_id = validate_uuid_id(args.submission_id, "SUBMISSION_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.bounties.open_pr(
            bounty_id=args.bounty_id,
            submission_id=args.submission_id,
        )
        if config.json_output:
            data = (
                result.model_dump(mode="json")
                if hasattr(result, "model_dump")
                else to_data(result)
            )
            emit_json("logion.bounties.submissions.open-pr", data)
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_submissions_register_pr(args: argparse.Namespace) -> int:
    """Execute the bounties submissions register-pr command."""
    bad_id = validate_uuid_id(args.bounty_id, "BOUNTY_ID")
    if bad_id is not None:
        return bad_id
    bad_id = validate_uuid_id(args.submission_id, "SUBMISSION_ID")
    if bad_id is not None:
        return bad_id
    if args.pr_number <= 0:
        print_err("Error: --pr-number must be a positive integer")
        return 2
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.bounties.register_pr(
            bounty_id=args.bounty_id,
            submission_id=args.submission_id,
            pr_number=args.pr_number,
        )
        if config.json_output:
            data = (
                result.model_dump(mode="json")
                if hasattr(result, "model_dump")
                else to_data(result)
            )
            emit_json("logion.bounties.submissions.register-pr", data)
        else:
            emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()
