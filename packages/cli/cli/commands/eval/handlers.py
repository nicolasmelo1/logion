# SPDX-License-Identifier: MIT
"""Public handlers for the eval command group."""

from cli.commands.eval import _scaffold
from cli.commands.eval._bundle import handle_eval_export
from cli.commands.eval._execution import (
    handle_eval_run,
    handle_eval_scaffold,
    handle_eval_validate,
)
from cli.commands.eval._verify import handle_eval_inspect, handle_eval_verify

make_client = _scaffold.make_client


def _publish_result(args, contract, job, result):
    """Keep the public compatibility seam for SDK-client injection tests."""
    original = _scaffold.make_client
    _scaffold.make_client = make_client
    try:
        return _scaffold._publish_result(args, contract, job, result)
    finally:
        _scaffold.make_client = original


__all__ = [
    "handle_eval_export",
    "handle_eval_inspect",
    "handle_eval_run",
    "handle_eval_scaffold",
    "handle_eval_validate",
    "handle_eval_verify",
]
