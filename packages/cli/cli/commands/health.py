"""Health command — check API availability."""

from __future__ import annotations

import argparse

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error
from cli._options import COMMON_PARSER
from cli._output import emit


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``health`` subcommand."""
    parser = subparsers.add_parser(
        "health",
        help="Check API health",
        parents=[COMMON_PARSER],
    )
    parser.set_defaults(handler=handle_health)


def handle_health(args: argparse.Namespace) -> int:
    """Execute the health check."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.health.check()
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()
