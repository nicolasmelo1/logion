"""CLI entry point: logion-social."""

from __future__ import annotations

import argparse
import sys

from social_management.config import SocialConfig
from social_management.content import add, list_drafts
from social_management.discord import DiscordClient
from social_management.errors import (
    BudgetExceededError,
    ConfirmationRequiredError,
    MissingCredentialsError,
    SocialError,
)
from social_management.models import PostDraft
from social_management.x_client import XClient


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="logion-social",
        description="Run Logion's Discord + X presence from local creds.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # discord post --channel general --text "..." [--dry-run]
    dp = sub.add_parser("discord", help="Discord webhook post / bot read")
    dsub = dp.add_subparsers(dest="discord_cmd", required=True)
    d_post = dsub.add_parser("post")
    d_post.add_argument(
        "--channel",
        required=True,
        choices=["announcements", "general", "support", "creators"],
    )
    d_post.add_argument("--text", required=True)
    d_post.add_argument("--dry-run", action="store_true")
    d_read = dsub.add_parser("read")
    d_read.add_argument("--limit", type=int, default=20)
    d_read.add_argument("--dry-run", action="store_true")

    # x post --text "..." [--confirm] [--dry-run]
    xp = sub.add_parser("x", help="Post to X via the official API (gated)")
    xsub = xp.add_subparsers(dest="x_cmd", required=True)
    x_post = xsub.add_parser("post")
    x_post.add_argument("--text", required=True)
    x_post.add_argument(
        "--confirm",
        action="store_true",
        help="required to actually spend money posting",
    )
    x_post.add_argument("--dry-run", action="store_true")

    # queue add|list
    q = sub.add_parser("queue", help="Local content draft queue")
    qsub = q.add_subparsers(dest="queue_cmd", required=True)
    q_add = qsub.add_parser("add")
    q_add.add_argument("--platform", required=True, choices=["discord", "x"])
    q_add.add_argument("--target", required=True)
    q_add.add_argument("--text", required=True)
    q_add.add_argument("--dry-run", action="store_true")
    qsub.add_parser("list")
    return p


def _handle_discord(args: object, config: SocialConfig) -> int:
    client = DiscordClient(config)
    if args.discord_cmd == "post":  # type: ignore[attr-defined]
        try:
            result = client.post_webhook(
                args.channel,  # type: ignore[attr-defined]
                args.text,  # type: ignore[attr-defined]
                dry_run=args.dry_run,  # type: ignore[attr-defined]
            )
        except MissingCredentialsError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if result.dry_run:
            print(f"[dry-run] discord #{args.channel}:")  # type: ignore[attr-defined]
            print(result.rendered)
        else:
            print(
                f"posted to discord #{args.channel} "  # type: ignore[attr-defined]
                f"(sent={result.sent})"
            )
        return 0
    if args.discord_cmd == "read":  # type: ignore[attr-defined]
        channel_id = config.discord_channel_support
        if not channel_id and not args.dry_run:  # type: ignore[attr-defined]
            print(
                "error: DISCORD_CHANNEL_SUPPORT not set",
                file=sys.stderr,
            )
            return 2
        try:
            messages = client.read_recent(
                channel_id or "",
                limit=args.limit,  # type: ignore[attr-defined]
                dry_run=args.dry_run,  # type: ignore[attr-defined]
            )
        except MissingCredentialsError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        for msg in messages:
            print(f"[{msg.created_at}] {msg.author}: {msg.content}")
        return 0
    return 2


def _handle_x(args: object, config: SocialConfig) -> int:
    client = XClient(config)
    try:
        result = client.post(
            args.text,  # type: ignore[attr-defined]
            confirm=args.confirm,  # type: ignore[attr-defined]
            dry_run=args.dry_run,  # type: ignore[attr-defined]
        )
    except ConfirmationRequiredError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except BudgetExceededError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except MissingCredentialsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if result.dry_run:
        print(f"[dry-run] x post ~${result.cost_cents / 100:.2f}:")
        print(result.rendered)
        if result.note:
            print(f"note: {result.note}")
    elif result.sent:
        print(
            f"posted to x (id={result.remote_id}, "
            f"cost=${result.cost_cents / 100:.2f})"
        )
    else:
        print("[manual] x post (backend off):")
        print(result.rendered)
        if result.note:
            print(f"note: {result.note}")
    return 0


def _handle_queue(args: object) -> int:
    if args.queue_cmd == "add":  # type: ignore[attr-defined]
        draft = PostDraft(
            platform=args.platform,  # type: ignore[attr-defined]
            target=args.target,  # type: ignore[attr-defined]
            text=args.text,  # type: ignore[attr-defined]
        )
        path = add(draft, dry_run=args.dry_run)  # type: ignore[attr-defined]
        if args.dry_run:  # type: ignore[attr-defined]
            print(f"[dry-run] would queue: {path}")
        else:
            print(f"queued: {path}")
        return 0
    if args.queue_cmd == "list":  # type: ignore[attr-defined]
        drafts = list_drafts()
        if not drafts:
            print("(queue empty)")
        for draft in drafts:
            print(
                f"[{draft.source_file}] {draft.platform} "
                f"-> {draft.target}: {draft.text}"
            )
        return 0
    return 2


def main(argv: list[str] | None = None) -> int:
    """Dispatch to handlers. Returns process exit code.

    Exit codes: 0 ok, 1 budget/confirmation refused, 2 usage/creds
    error. Each handler prints the rendered text on --dry-run and makes
    no network call. ConfirmationRequiredError and BudgetExceededError
    are caught here, printed to stderr, and mapped to exit code 1.
    """
    args = _build_parser().parse_args(argv)
    try:
        config = SocialConfig.from_env()
    except SocialError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.cmd == "discord":
        return _handle_discord(args, config)
    if args.cmd == "x":
        return _handle_x(args, config)
    if args.cmd == "queue":
        return _handle_queue(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
