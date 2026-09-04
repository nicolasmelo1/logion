# SPDX-License-Identifier: MIT
"""Evals resource — upload contracts and submit results."""

from __future__ import annotations

from urllib.parse import quote

from logion._http import HttpClient
from logion._json import JsonObject


class EvalsResource:
    """Upload eval contracts and submit normalized results."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def upload_contract(
        self, document: JsonObject, *, name: str | None = None
    ) -> JsonObject:
        """Upload one eval contract; immutable by digest.

        Re-uploading the same document is idempotent and returns the
        same digest. A ``name`` may be repointed at a newer digest,
        never updated in place.
        """
        payload: JsonObject = {"document": document}
        if name is not None:
            payload["name"] = name
        return self._http.request_object(
            "POST", "/v1/evals/contracts", json=payload
        )

    def get_contract(self, ref: str) -> JsonObject:
        """Get a contract by digest or friendly name."""
        encoded_ref = quote(ref, safe="")
        return self._http.request_object(
            "GET", f"/v1/evals/contracts/{encoded_ref}"
        )

    def validate_job(
        self,
        contract_ref: str,
        subject_digest: str,
        fixture_digests: dict[str, str],
    ) -> JsonObject:
        """Validate resolved eval inputs before execution.

        The five stable rejection codes all return 422 and reject
        before any job row is created, so an invalid job never
        reaches the queue.
        """
        return self._http.request_object(
            "POST",
            "/v1/evals/jobs/validate",
            json={
                "contract_ref": contract_ref,
                "subject_digest": subject_digest,
                "fixture_digests": fixture_digests,
            },
        )

    def submit_result(
        self,
        result: JsonObject,
        *,
        idempotency_key: str | None = None,
    ) -> JsonObject:
        """Submit one normalized eval result (runner-authenticated).

        The body may never declare ``contract_standing``,
        ``reproduced_by``, ``independence_group``,
        ``environment_verified`` or ``issuer_id`` — the standing is
        server-owned.
        """
        payload: JsonObject = {"result": result}
        if idempotency_key is not None:
            payload["idempotency_key"] = idempotency_key
        return self._http.request_object(
            "POST", "/v1/evals/results", json=payload
        )
