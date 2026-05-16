"""Shared bounty resource types."""

from __future__ import annotations

from logion._http import HttpClient

VALID_SCOPE_VALUES = ("mine", "open", "funded")


class _BountyResourceBase:
    """Base for bounty resource mixins."""

    _http: HttpClient
