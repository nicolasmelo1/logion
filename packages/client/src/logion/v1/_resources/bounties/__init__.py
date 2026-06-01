# SPDX-License-Identifier: MIT
"""Bounties resource package."""

from __future__ import annotations

from logion._http import HttpClient

from .core import _BountyCoreMixin
from .submissions import _BountySubmissionsMixin


class BountiesResource(_BountyCoreMixin, _BountySubmissionsMixin):
    """Manage bounties in the Logion marketplace."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http


__all__ = ["BountiesResource"]
