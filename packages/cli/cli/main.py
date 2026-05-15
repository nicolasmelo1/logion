"""Logion CLI entry point."""

from __future__ import annotations

import sys

from cli._errors import handle_error
from cli._parser import build_parser


def main(argv: list[str] | None = None) -> int:
    """Parse args and dispatch to the appropriate command handler."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except Exception as exc:
        return handle_error(exc)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
