# SPDX-License-Identifier: MIT
"""Indexed listings resource — read-only external discovery."""

from __future__ import annotations

from uuid import UUID

from logion._http import HttpClient
from logion._json import JsonObject


class IndexedListingsResource:
    """Read-only access to indexed external listings."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def get(
        self,
        *,
        listing_id: str | UUID,
    ) -> JsonObject:
        """Get detail for an indexed listing.

        Args:
            listing_id: The indexed listing's UUID.

        Returns:
            Raw JSON object from the API. The response shape follows
            the indexed listing detail contract.
        """
        return self._http.request_object(
            "GET", f"/v1/indexed-listings/{listing_id}"
        )
