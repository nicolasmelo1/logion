"""Admin commands — courses/users/agents/reports administration.

Gated by ``LOGION_ENABLE_ADMIN``.  If the env var is not truthy the
``admin`` subcommand is hidden: the parser prints *No such command* to
stderr and exits with code 2.
"""

from __future__ import annotations

import argparse

from cli._config import is_admin_enabled, resolve_config_from_args
from cli._confirm import require_yes
from cli._context import make_client
from cli._errors import handle_error, print_err, validate_uuid_id
from cli._options import COMMON_PARSER
from cli._output import emit
from cli._utils import only_not_none

# ── Registration ──────────────────────────────────────────────────


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``admin`` subcommand group.

    If ``LOGION_ENABLE_ADMIN`` is not truthy, adds a stub parser that
    exits with code 2 and prints *No such command* to stderr.
    """
    if not is_admin_enabled():
        parser = subparsers.add_parser(
            "admin",
            help="Admin operations (disabled)",
            add_help=False,
        )
        parser.set_defaults(handler=_handle_disabled)
        return

    parser = subparsers.add_parser(
        "admin",
        help="Admin operations",
    )
    sub = parser.add_subparsers(
        dest="admin_command",
        required=True,
    )

    # ── courses sub-group ──────────────────────────────────────────
    _register_courses(sub)

    # ── users sub-group ─────────────────────────────────────────────
    _register_users(sub)

    # ── agents sub-group ─────────────────────────────────────────────
    _register_agents(sub)

    # ── reports sub-group ─────────────────────────────────────────────
    _register_reports(sub)


# ── Disabled handler ──────────────────────────────────────────────


def _handle_disabled(args: argparse.Namespace) -> int:  # noqa: ARG001
    """Exit with code 2 — admin is not enabled."""
    print_err("No such command")
    return 2


# ── Courses ────────────────────────────────────────────────────────


def _register_courses(sub: argparse._SubParsersAction) -> None:
    """Register the ``admin courses`` sub-group."""
    courses = sub.add_parser(
        "courses",
        help="Administer courses",
    )
    courses_sub = courses.add_subparsers(
        dest="admin_courses_command",
        required=True,
    )

    # courses list
    cl = courses_sub.add_parser(
        "list",
        help="List courses (admin view)",
        parents=[COMMON_PARSER],
    )
    cl.add_argument("--status")
    cl.add_argument("--owner-agent-id")
    cl.add_argument("--limit", type=int)
    cl.add_argument("--cursor")
    cl.set_defaults(handler=handle_admin_courses_list)

    # courses get
    cg = courses_sub.add_parser(
        "get",
        help="Get course details (admin view)",
        parents=[COMMON_PARSER],
    )
    cg.add_argument("course_id", metavar="COURSE_ID")
    cg.set_defaults(handler=handle_admin_courses_get)

    # courses block
    cb = courses_sub.add_parser(
        "block",
        help="Block a course (set status to blocked)",
        parents=[COMMON_PARSER],
    )
    cb.add_argument("course_id", metavar="COURSE_ID")
    cb.add_argument("--yes", action="store_true")
    cb.set_defaults(handler=handle_admin_courses_block)


def handle_admin_courses_list(args: argparse.Namespace) -> int:
    """Execute the admin courses list command."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        kwargs = only_not_none(
            {},
            status=args.status,
            owner_agent_id=args.owner_agent_id,
            limit=args.limit,
            cursor=args.cursor,
        )
        result = client.v1.admin.list_courses(**kwargs)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_admin_courses_get(args: argparse.Namespace) -> int:
    """Execute the admin courses get command."""
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.admin.get_course(course_id=args.course_id)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_admin_courses_block(args: argparse.Namespace) -> int:
    """Execute the admin courses block command."""
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id
    refusal = require_yes(args.yes, "block this course")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.admin.update_course_status(course_id=args.course_id)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


# ── Users ──────────────────────────────────────────────────────────


def _register_users(sub: argparse._SubParsersAction) -> None:
    """Register the ``admin users`` sub-group."""
    users = sub.add_parser(
        "users",
        help="Administer users",
    )
    users_sub = users.add_subparsers(
        dest="admin_users_command",
        required=True,
    )

    # users get
    ug = users_sub.add_parser(
        "get",
        help="Get user details",
        parents=[COMMON_PARSER],
    )
    ug.add_argument("user_id", metavar="USER_ID")
    ug.set_defaults(handler=handle_admin_users_get)

    # users billing-exemption
    ube = users_sub.add_parser(
        "billing-exemption",
        help="Update user billing exemption",
        parents=[COMMON_PARSER],
    )
    ube.add_argument("user_id", metavar="USER_ID")
    ube.add_argument(
        "--enabled",
        required=True,
        choices=["true", "false"],
        help="Enable or disable billing exemption",
    )
    ube.add_argument("--yes", action="store_true")
    ube.set_defaults(handler=handle_admin_users_billing_exemption)

    # users suspend
    us = users_sub.add_parser(
        "suspend",
        help="Suspend a user",
        parents=[COMMON_PARSER],
    )
    us.add_argument("user_id", metavar="USER_ID")
    us.add_argument("--yes", action="store_true")
    us.set_defaults(handler=handle_admin_users_suspend)

    # users unsuspend
    uus = users_sub.add_parser(
        "unsuspend",
        help="Unsuspend a user",
        parents=[COMMON_PARSER],
    )
    uus.add_argument("user_id", metavar="USER_ID")
    uus.add_argument("--yes", action="store_true")
    uus.set_defaults(handler=handle_admin_users_unsuspend)


def handle_admin_users_get(args: argparse.Namespace) -> int:
    """Execute the admin users get command."""
    bad_id = validate_uuid_id(args.user_id, "USER_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.admin.get_user(user_id=args.user_id)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_admin_users_billing_exemption(args: argparse.Namespace) -> int:
    """Execute the admin users billing-exemption command."""
    bad_id = validate_uuid_id(args.user_id, "USER_ID")
    if bad_id is not None:
        return bad_id
    refusal = require_yes(args.yes, "update billing exemption")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        enabled = args.enabled == "true"
        result = client.v1.admin.update_user_billing_exemption(
            user_id=args.user_id,
            enabled=enabled,
        )
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_admin_users_suspend(args: argparse.Namespace) -> int:
    """Execute the admin users suspend command."""
    bad_id = validate_uuid_id(args.user_id, "USER_ID")
    if bad_id is not None:
        return bad_id
    refusal = require_yes(args.yes, "suspend this user")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.admin.suspend_user(user_id=args.user_id)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_admin_users_unsuspend(args: argparse.Namespace) -> int:
    """Execute the admin users unsuspend command."""
    bad_id = validate_uuid_id(args.user_id, "USER_ID")
    if bad_id is not None:
        return bad_id
    refusal = require_yes(args.yes, "unsuspend this user")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.admin.unsuspend_user(user_id=args.user_id)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


# ── Agents ─────────────────────────────────────────────────────────


def _register_agents(sub: argparse._SubParsersAction) -> None:
    """Register the ``admin agents`` sub-group."""
    agents = sub.add_parser(
        "agents",
        help="Administer agents",
    )
    agents_sub = agents.add_subparsers(
        dest="admin_agents_command",
        required=True,
    )

    # agents get
    ag = agents_sub.add_parser(
        "get",
        help="Get agent details",
        parents=[COMMON_PARSER],
    )
    ag.add_argument("agent_id", metavar="AGENT_ID")
    ag.set_defaults(handler=handle_admin_agents_get)

    # agents suspend
    asp = agents_sub.add_parser(
        "suspend",
        help="Suspend an agent",
        parents=[COMMON_PARSER],
    )
    asp.add_argument("agent_id", metavar="AGENT_ID")
    asp.add_argument("--yes", action="store_true")
    asp.set_defaults(handler=handle_admin_agents_suspend)

    # agents unsuspend
    aus = agents_sub.add_parser(
        "unsuspend",
        help="Unsuspend an agent",
        parents=[COMMON_PARSER],
    )
    aus.add_argument("agent_id", metavar="AGENT_ID")
    aus.add_argument("--yes", action="store_true")
    aus.set_defaults(handler=handle_admin_agents_unsuspend)


def handle_admin_agents_get(args: argparse.Namespace) -> int:
    """Execute the admin agents get command."""
    bad_id = validate_uuid_id(args.agent_id, "AGENT_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.admin.get_agent(agent_id=args.agent_id)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_admin_agents_suspend(args: argparse.Namespace) -> int:
    """Execute the admin agents suspend command."""
    bad_id = validate_uuid_id(args.agent_id, "AGENT_ID")
    if bad_id is not None:
        return bad_id
    refusal = require_yes(args.yes, "suspend this agent")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.admin.suspend_agent(agent_id=args.agent_id)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_admin_agents_unsuspend(args: argparse.Namespace) -> int:
    """Execute the admin agents unsuspend command."""
    bad_id = validate_uuid_id(args.agent_id, "AGENT_ID")
    if bad_id is not None:
        return bad_id
    refusal = require_yes(args.yes, "unsuspend this agent")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.admin.unsuspend_agent(agent_id=args.agent_id)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


# ── Reports ────────────────────────────────────────────────────────


def _register_reports(sub: argparse._SubParsersAction) -> None:
    """Register the ``admin reports`` sub-group."""
    reports = sub.add_parser(
        "reports",
        help="Administer reports",
    )
    reports_sub = reports.add_subparsers(
        dest="admin_reports_command",
        required=True,
    )

    # reports list
    rl = reports_sub.add_parser(
        "list",
        help="List reports (admin view)",
        parents=[COMMON_PARSER],
    )
    rl.add_argument("--status")
    rl.add_argument("--severity")
    rl.add_argument("--target-type")
    rl.add_argument("--limit", type=int)
    rl.add_argument("--cursor")
    rl.set_defaults(handler=handle_admin_reports_list)

    # reports get
    rg = reports_sub.add_parser(
        "get",
        help="Get report details",
        parents=[COMMON_PARSER],
    )
    rg.add_argument("report_id", metavar="REPORT_ID")
    rg.set_defaults(handler=handle_admin_reports_get)

    # reports resolve
    rr = reports_sub.add_parser(
        "resolve",
        help="Resolve a report",
        parents=[COMMON_PARSER],
    )
    rr.add_argument("report_id", metavar="REPORT_ID")
    rr.add_argument("--note")
    rr.add_argument("--yes", action="store_true")
    rr.set_defaults(handler=handle_admin_reports_resolve)

    # reports dismiss
    rd = reports_sub.add_parser(
        "dismiss",
        help="Dismiss a report",
        parents=[COMMON_PARSER],
    )
    rd.add_argument("report_id", metavar="REPORT_ID")
    rd.add_argument("--reason", required=True)
    rd.add_argument("--yes", action="store_true")
    rd.set_defaults(handler=handle_admin_reports_dismiss)


def handle_admin_reports_list(args: argparse.Namespace) -> int:
    """Execute the admin reports list command."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        kwargs = only_not_none(
            {},
            status=args.status,
            severity=args.severity,
            target_type=args.target_type,
            limit=args.limit,
            cursor=args.cursor,
        )
        result = client.v1.admin.list_reports(**kwargs)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_admin_reports_get(args: argparse.Namespace) -> int:
    """Execute the admin reports get command."""
    bad_id = validate_uuid_id(args.report_id, "REPORT_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.admin.get_report(report_id=args.report_id)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_admin_reports_resolve(args: argparse.Namespace) -> int:
    """Execute the admin reports resolve command."""
    bad_id = validate_uuid_id(args.report_id, "REPORT_ID")
    if bad_id is not None:
        return bad_id
    refusal = require_yes(args.yes, "resolve this report")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        kwargs = only_not_none(
            {"report_id": args.report_id},
            note=args.note,
        )
        result = client.v1.admin.resolve_report(**kwargs)
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_admin_reports_dismiss(args: argparse.Namespace) -> int:
    """Execute the admin reports dismiss command."""
    bad_id = validate_uuid_id(args.report_id, "REPORT_ID")
    if bad_id is not None:
        return bad_id
    refusal = require_yes(args.yes, "dismiss this report")
    if refusal is not None:
        return refusal
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.admin.dismiss_report(
            report_id=args.report_id,
            reason=args.reason,
        )
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()
