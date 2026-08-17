# SPDX-License-Identifier: MIT
"""Handlers for the ``bounties submissions`` sub-group."""

from __future__ import annotations

import argparse
from collections.abc import Callable

from cli._config import resolve_config_from_args
from cli._confirm import require_yes
from cli._context import client_for
from cli._errors import handle_error, validate_uuid_id
from cli._json import opt_str
from cli._output import emit, emit_json, to_object
from cli._utils import only_not_none

from ._inputs import load_evidence
from ._render import fork_instructions, render_github_pr_block

Handler = Callable[[argparse.Namespace], int]

# accept / reject / withdraw differ only in the SDK method and the
# wording of the confirmation prompt.
CONFIRMED_COMMANDS: tuple[tuple[str, str, str], ...] = (
    ("accept", "accept_submission", "accept this submission"),
    ("reject", "reject_submission", "reject this submission"),
    ("withdraw", "delete_submission", "withdraw this submission"),
)


def _validate_ids(args: argparse.Namespace) -> int | None:
    """Return an exit code when either identifier is not a UUID."""
    for value, label in (
        (args.bounty_id, "BOUNTY_ID"),
        (args.submission_id, "SUBMISSION_ID"),
    ):
        bad_id = validate_uuid_id(value, label)
        if bad_id is not None:
            return bad_id
    return None


def make_confirmed_handler(cmd: str, sdk_method: str, action: str) -> Handler:
    """Return a handler for a submission command that asks first."""

    def handler(args: argparse.Namespace) -> int:
        invalid = _validate_ids(args)
        if invalid is not None:
            return invalid
        refusal = require_yes(args.yes, action)
        if refusal is not None:
            return refusal
        config = resolve_config_from_args(args)
        try:
            with client_for(config) as client:
                method = getattr(client.v1.bounties, sdk_method)
                emit(
                    method(
                        bounty_id=args.bounty_id,
                        submission_id=args.submission_id,
                    ),
                    json_output=config.json_output,
                )
        except Exception as exc:
            return handle_error(exc)
        return 0

    handler.__name__ = f"handle_submissions_{cmd}"
    handler.__doc__ = f"Execute the bounties submissions {cmd} command."
    return handler


def handle_create(args: argparse.Namespace) -> int:
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
    try:
        with client_for(config) as client:
            result = client.v1.bounties.create_submission(
                **only_not_none(
                    {
                        "bounty_id": args.bounty_id,
                        "title": args.title,
                    },
                    description=args.description,
                    evidence=evidence,
                    proposed_course_version_id=(
                        args.proposed_course_version_id
                    ),
                    github_pr=args.github_pr,
                )
            )
            data = to_object(result)
            if config.json_output:
                emit_json("logion.bounties.submissions.create", data)
            else:
                print(f"Submission created: {opt_str(data, 'id', '')}")
                gh_block = data.get("github_pr")
                if isinstance(gh_block, dict):
                    render_github_pr_block(gh_block)
    except Exception as exc:
        return handle_error(exc)
    return 0


def handle_list(args: argparse.Namespace) -> int:
    """Execute the bounties submissions list command."""
    bad_id = validate_uuid_id(args.bounty_id, "BOUNTY_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    try:
        with client_for(config) as client:
            result = client.v1.bounties.list_submissions(
                bounty_id=args.bounty_id
            )
            if config.json_output:
                emit_json("logion.bounties.submissions.list", result)
            else:
                emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    return 0


def handle_get(args: argparse.Namespace) -> int:
    """Execute the bounties submissions get command."""
    invalid = _validate_ids(args)
    if invalid is not None:
        return invalid
    config = resolve_config_from_args(args)
    try:
        with client_for(config) as client:
            result = client.v1.bounties.get_submission(
                bounty_id=args.bounty_id,
                submission_id=args.submission_id,
            )
            if config.json_output:
                emit_json("logion.bounties.submissions.get", to_object(result))
            else:
                emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    return 0


def handle_open_pr(args: argparse.Namespace) -> int:
    """Execute the bounties submissions open-pr command."""
    invalid = _validate_ids(args)
    if invalid is not None:
        return invalid
    refusal = require_yes(args.yes, "open a draft PR for this submission")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    try:
        with client_for(config) as client:
            result = client.v1.bounties.open_pr(
                bounty_id=args.bounty_id,
                submission_id=args.submission_id,
            )
            data = to_object(result)
            if config.json_output:
                emit_json("logion.bounties.submissions.open-pr", data)
            elif data.get("fork_required"):
                print(fork_instructions(opt_str(data, "head_branch", "")))
                pr_body = opt_str(data, "pr_body", "")
                if pr_body:
                    print(f"\nPaste-ready PR body:\n{pr_body}")
            else:
                emit(result, json_output=False)
    except Exception as exc:
        return handle_error(exc)
    return 0
