# SPDX-License-Identifier: MIT
"""Parser registration for portable eval workflows."""

from __future__ import annotations

import argparse

from cli._options import COMMON_PARSER
from cli.commands.eval.handlers import (
    handle_eval_export,
    handle_eval_inspect,
    handle_eval_run,
    handle_eval_scaffold,
    handle_eval_validate,
    handle_eval_verify,
)


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``eval`` command tree."""
    parser = subparsers.add_parser(
        "eval", help="Create, run, and reproduce portable evals"
    )
    sub = parser.add_subparsers(dest="eval_command", required=True)

    scaffold = sub.add_parser(
        "scaffold", help="Create a portable starter eval"
    )
    scaffold.add_argument("directory", help="Directory to create")
    scaffold.add_argument(
        "--force", action="store_true", help="Replace scaffold files"
    )
    scaffold.add_argument("--json", action="store_true", help="Emit JSON")
    scaffold.set_defaults(handler=handle_eval_scaffold)

    validate = sub.add_parser(
        "validate",
        help="Validate a contract and its local fixtures",
        parents=[COMMON_PARSER],
    )
    validate.add_argument("contract", help="Contract file (YAML or JSON)")
    validate.set_defaults(handler=handle_eval_validate)

    run = sub.add_parser(
        "run",
        help="Resolve and execute a local subject",
        parents=[COMMON_PARSER],
    )
    run.add_argument("contract", help="Contract file (YAML or JSON)")
    run.add_argument("--subject", required=True, help="Subject file path")
    run.add_argument("--output", help="Write the normalized result to FILE")
    run.add_argument(
        "--force", action="store_true", help="Replace the output file"
    )
    run.add_argument(
        "--publish",
        action="store_true",
        help="Upload the contract and submit the normalized result",
    )
    run.add_argument(
        "--runner-credentials",
        help="JSON file containing runner_id and runner_key",
    )
    run.set_defaults(handler=handle_eval_run)

    export = sub.add_parser(
        "export", help="Package a contract and two run results"
    )
    export.add_argument("contract", help="Contract file (YAML or JSON)")
    export.add_argument("--subject", required=True, help="Subject file path")
    export.add_argument(
        "--result",
        action="append",
        required=True,
        help="Normalized result file; pass at least twice",
    )
    export.add_argument("--output", required=True, help="Bundle ZIP path")
    export.add_argument(
        "--force", action="store_true", help="Replace the output bundle"
    )
    export.add_argument("--json", action="store_true", help="Emit JSON")
    export.set_defaults(handler=handle_eval_export)

    verify = sub.add_parser(
        "verify", help="Validate and reproduce an exported bundle twice"
    )
    verify.add_argument("bundle", help="Reproduction bundle ZIP")
    verify.add_argument("--json", action="store_true", help="Emit JSON")
    verify.set_defaults(handler=handle_eval_verify)

    inspect = sub.add_parser(
        "inspect", help="Inspect a normalized result or reproduction bundle"
    )
    inspect.add_argument("artifact", help="Result JSON/YAML or bundle ZIP")
    inspect.add_argument("--json", action="store_true", help="Emit JSON")
    inspect.set_defaults(handler=handle_eval_inspect)
