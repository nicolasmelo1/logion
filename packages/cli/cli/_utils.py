# SPDX-License-Identifier: MIT
"""CLI utility helpers — generic kwarg building, etc.

This module holds the one sanctioned use of ``typing.Any`` in the CLI.
See :func:`only_not_none`.
"""

from __future__ import annotations

from typing import Any


def only_not_none(
    base: dict[str, object],
    **optional: object,
) -> dict[str, Any]:
    """Return *base* merged with only the non-None *optional* entries.

    The return type is the one place ``Any`` survives the repo-wide ban,
    and it is a limitation of the type system rather than a shortcut.
    Every caller does ``client.v1.<resource>.<op>(**kwargs)``, and Python
    cannot express "this mapping's keys and values line up with that
    callable's typed parameters". ``dict[str, object]`` is rejected at
    the expansion site just as firmly as a wrong type would be, so it
    buys no safety — it only moves the error somewhere less useful.

    The keyword arguments are still ``object``: a wrongly typed value is
    caught at the SDK call, by the SDK's own signature.
    """
    result: dict[str, Any] = dict(base)
    result.update({k: v for k, v in optional.items() if v is not None})
    return result
