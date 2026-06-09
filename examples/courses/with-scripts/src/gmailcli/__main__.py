"""CLI entrypoint dispatched by scripts/*.sh.

    python -m gmailcli search QUERY [MAX_RESULTS]
    python -m gmailcli labels
    python -m gmailcli get MESSAGE_ID

All commands print JSON to stdout. Errors go to stderr with non-zero
exit. The agent should rely on exit codes, not on parsing stderr.
"""

from __future__ import annotations

import json
import sys

from . import api
from .auth import MissingTokenError


def _print_json(data: object) -> None:
    json.dump(data, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def _cmd_search(args: list[str]) -> int:
    if not args:
        print("usage: search QUERY [MAX_RESULTS]", file=sys.stderr)
        return 2
    query = args[0]
    try:
        max_results = int(args[1]) if len(args) > 1 else 10
    except ValueError:
        print(f"invalid MAX_RESULTS: {args[1]!r}", file=sys.stderr)
        return 2
    try:
        messages = api.search_messages(query, max_results)
    except (MissingTokenError, api.GmailAPIError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _print_json({"messages": messages})
    return 0


def _cmd_labels(_args: list[str]) -> int:
    try:
        labels = api.list_labels()
    except (MissingTokenError, api.GmailAPIError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _print_json({"labels": labels})
    return 0


def _cmd_get(args: list[str]) -> int:
    if not args:
        print("usage: get MESSAGE_ID", file=sys.stderr)
        return 2
    try:
        message = api.get_message(args[0])
    except (MissingTokenError, api.GmailAPIError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _print_json(message)
    return 0


_COMMANDS = {
    "search": _cmd_search,
    "labels": _cmd_labels,
    "get": _cmd_get,
}


def main(argv: list[str]) -> int:
    if not argv:
        print(
            "usage: python -m gmailcli {search,labels,get} [args]",
            file=sys.stderr,
        )
        return 2
    cmd, *rest = argv
    handler = _COMMANDS.get(cmd)
    if handler is None:
        print(f"unknown command: {cmd}", file=sys.stderr)
        return 2
    return handler(rest)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
