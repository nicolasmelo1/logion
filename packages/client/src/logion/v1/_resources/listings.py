# SPDX-License-Identifier: MIT
"""Listings resource — course marketplace search."""

from __future__ import annotations

from logion._http import HttpClient
from logion.v1._types.generated.v1 import SearchListingsResponse

_VALID_SORT_VALUES = (
    "relevance",
    "newest",
    "recently_updated",
    "price_low",
    "price_high",
    "most_useful",
)
_VALID_TIER_VALUES = ("published", "indexed", "improving")


def _build_search_params(
    *,
    query: str | None = None,
    tags: str | None = None,
    category: str | None = None,
    language: str | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
    sort: str | None = None,
    limit: int | None = None,
    cursor: str | None = None,
    include_indexed: bool = False,
    tier: str | None = None,
) -> dict[str, object]:
    params: dict[str, object] = {}
    if query is not None:
        params["query"] = query
    if tags is not None:
        params["tags"] = tags
    if category is not None:
        params["category"] = category
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
    if include_indexed:
        params["include_indexed"] = True
    if tier is not None:
        params["tier"] = tier
    return params


class ListingsResource:
    """Search and browse course listings."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def search(
        self,
        *,
        query: str | None = None,
        tags: str | None = None,
        category: str | None = None,
        language: str | None = None,
        price_min: int | None = None,
        price_max: int | None = None,
        sort: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        include_indexed: bool = False,
        tier: str | None = None,
    ) -> SearchListingsResponse:
        """Search course listings.

        By default only internally published courses are returned.  Set
        ``include_indexed=True`` to also discover externally indexed
        listings.  When indexed listings are included, ``tier`` filters
        the result set to one of ``published``, ``indexed`` or
        ``improving``.

        Parameters
        ----------
        query:
            Free-text search query.
        tags, category, language:
            Taxonomy filters forwarded to the API.
        price_min, price_max:
            Price range in cents.
        sort:
            Result ordering; one of the values in ``_VALID_SORT_VALUES``.
        limit:
            Page size (max 50).
        cursor:
            Pagination cursor from a previous response.  Not supported
            together with ``include_indexed``.
        include_indexed:
            Whether to include externally indexed listings.
        tier:
            Filter by listing tier when ``include_indexed`` is enabled.
        """
        if sort is not None and sort not in _VALID_SORT_VALUES:
            valid = ", ".join(_VALID_SORT_VALUES)
            msg = f"Invalid sort value {sort!r}. Must be one of: {valid}"
            raise ValueError(msg)

        if tier is not None and tier not in _VALID_TIER_VALUES:
            valid = ", ".join(_VALID_TIER_VALUES)
            msg = f"Invalid tier value {tier!r}. Must be one of: {valid}"
            raise ValueError(msg)

        if cursor is not None and include_indexed:
            msg = (
                "cursor pagination is not supported together"
                " with include_indexed=True"
            )
            raise ValueError(msg)

        if tier is not None and not include_indexed:
            msg = "tier filter is only valid when include_indexed=True"
            raise ValueError(msg)

        params = _build_search_params(
            query=query,
            tags=tags,
            category=category,
            language=language,
            price_min=price_min,
            price_max=price_max,
            sort=sort,
            limit=limit,
            cursor=cursor,
            include_indexed=include_indexed,
            tier=tier,
        )
        return self._http.request_model(
            "GET",
            "/v1/listings",
            SearchListingsResponse,
            params=params,
        )
