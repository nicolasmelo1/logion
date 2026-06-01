# SPDX-License-Identifier: MIT
"""Listings resource — course marketplace search."""

from __future__ import annotations

from logion._http import HttpClient
from logion.v1._generated import operations
from logion.v1._types.generated.v1 import SearchListingsResponse

_VALID_SORT_VALUES = (
    "relevance",
    "newest",
    "recently_updated",
    "price_low",
    "price_high",
    "most_useful",
)


class ListingsResource:
    """Search and browse course listings."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def search(
        self,
        *,
        query: str | None = None,
        tags: str | None = None,
        language: str | None = None,
        price_min: int | None = None,
        price_max: int | None = None,
        sort: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> SearchListingsResponse:
        """Search course listings.

        All parameters are optional filters.

        Args:
            query: Full-text search query.
            tags: Filter by tag names (comma-separated string).
            language: Filter by language code (e.g. "en", "pt").
            price_min: Minimum price in cents.
            price_max: Maximum price in cents.
            sort: Sort order — one of: relevance, newest,
                recently_updated, price_low, price_high, most_useful.
            limit: Maximum number of results per page.
            cursor: Pagination cursor for the next page.

        Returns:
            Search results with items and pagination cursor.

        Raises:
            ValueError: If *sort* is not a recognised value.
        """
        if sort is not None and sort not in _VALID_SORT_VALUES:
            valid = ", ".join(_VALID_SORT_VALUES)
            msg = f"Invalid sort value {sort!r}. Must be one of: {valid}"
            raise ValueError(msg)

        return operations.search_listings(
            self._http,
            query=query,
            tags=tags,
            language=language,
            price_min=price_min,
            price_max=price_max,
            sort=sort,
            limit=limit,
            cursor=cursor,
        )
