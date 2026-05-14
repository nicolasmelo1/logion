"""Listings resource — course marketplace search."""

from __future__ import annotations

from typing import Any

from logion._http import HttpClient

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
    ) -> dict[str, Any]:
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
        """
        params: dict[str, Any] = {}
        if query is not None:
            params["query"] = query
        if tags is not None:
            params["tags"] = tags
        if language is not None:
            params["language"] = language
        if price_min is not None:
            params["price_min"] = price_min
        if price_max is not None:
            params["price_max"] = price_max
        if sort is not None:
            params["sort"] = sort
        if limit is not None:
            params["limit"] = limit
        if cursor is not None:
            params["cursor"] = cursor
        return self._http.request("GET", "/v1/listings", params=params)
