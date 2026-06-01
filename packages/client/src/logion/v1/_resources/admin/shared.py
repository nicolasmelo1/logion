# SPDX-License-Identifier: MIT
"""Shared admin resource types."""

from __future__ import annotations

from logion._http import HttpClient


class _AdminResourceBase:
    """Base for admin resource mixins."""

    _http: HttpClient
