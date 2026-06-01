# SPDX-License-Identifier: MIT
"""Logion CLI entry point."""

from __future__ import annotations

import sys

from cli._parser import build_parser


def main(argv: list[str] | None = None) -> int:
    """Parse args and dispatch to the appropriate command handler."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
