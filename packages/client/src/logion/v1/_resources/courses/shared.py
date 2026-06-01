# SPDX-License-Identifier: MIT
"""Shared course resource types."""

from __future__ import annotations

from typing import Literal

from logion._http import HttpClient
from logion.v1._types.generated.v1 import Language, ShortSummary

SENTINEL = object()
Visibility = Literal["public", "unlisted", "private"]


class _CoursesResourceBase:
    """Base for course resource mixins."""

    _http: HttpClient


def normalize_language(language: str | None) -> Language | None:
    """Convert a language code into the generated enum type."""
    if language is None:
        return None
    return Language(language)


def normalize_short_summary(
    short_summary: str | None,
) -> ShortSummary | None:
    """Convert a short summary into the generated constrained type."""
    if short_summary is None:
        return None
    return ShortSummary(short_summary)
