# SPDX-License-Identifier: MIT
"""Indexed listings resource — read-only external discovery."""

from __future__ import annotations

from uuid import UUID

from logion._http import HttpClient


class IndexedListingsResource:
    """Read-only access to indexed external listings."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def get(
        self,
        *,
        listing_id: str | UUID,
    ) -> dict[str, object]:
        """Get detail for an indexed listing.

        Args:
            listing_id: The indexed listing's UUID.

        Returns:
            Raw JSON object from the API. The response shape follows
            the indexed listing detail contract.
        """
        result = self._http.request(
            "GET", f"/v1/indexed-listings/{listing_id}"
        )
        if not isinstance(result, dict):
            msg = (
                f"Expected a JSON object from "
                f"GET /v1/indexed-listings/{listing_id}, "
                f"got {type(result).__name__}"
            )
            raise TypeError(msg)
        return result
