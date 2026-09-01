"""HTTP client for the runner endpoints of the Logion coordinator.

Endpoints (all under the configured base URL):

- ``POST /v1/runners/enroll``            enroll a new runner identity
- ``POST /v1/runners/rotate-key``        rotate the runner key
- ``POST /v1/runners/lease``             claim one job (or none)
- ``POST /v1/runners/heartbeat``         renew a lease / read cancel intent
- ``POST /v1/runners/jobs/{id}/artifacts/{name}``  upload raw bytes
- ``POST /v1/runners/jobs/{id}/receipt`` submit the signed receipt

Transient failures (network errors, 5xx) are retried up to three
attempts total. Client errors (4xx) are never retried: a rejected
credential or a lost lease is a fact the loop must observe, not
something backoff will fix.
"""

from __future__ import annotations

from typing import Protocol

import httpx

from logion_runner._json import JsonObject, JsonValue

_MAX_ATTEMPTS = 3
_RETRY_STATUS = {502, 503, 504}


class CoordinatorError(RuntimeError):
    """A non-retryable coordinator response (4xx or bad shape)."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"coordinator responded {status_code}: {detail}")


class CoordinatorUnavailable(RuntimeError):
    """The coordinator stayed unreachable through every attempt."""


class _Transport(Protocol):
    """The slice of httpx.Client the client needs (tests fake this)."""

    def request(
        self,
        method: str,
        url: str,
        *,
        content: bytes | None = None,
        json: JsonValue | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response: ...


def _unwrap(payload: JsonObject) -> JsonObject:
    """Unwrap the ``{"data": ...}`` envelope, tolerating bare bodies."""
    data = payload.get("data")
    if isinstance(data, dict):
        return data
    return payload


def _unwrap_null(payload: JsonObject) -> JsonObject | None:
    """Unwrap an envelope whose data may legitimately be ``null``."""
    if isinstance(payload, dict) and "data" in payload:
        data = payload["data"]
        return data if isinstance(data, dict) else None
    return payload if isinstance(payload, dict) else None


class CoordinatorClient:
    """Synchronous runner-side HTTP surface of the job coordinator."""

    def __init__(self, base_url: str, transport: _Transport | None = None):
        self._base_url = base_url.rstrip("/")
        self._client: httpx.Client = (
            httpx.Client(base_url=self._base_url, timeout=30.0)
            if transport is None
            else transport  # type: ignore[assignment]
        )

    # ── low-level request with retry policy ─────────────────────

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: JsonObject | None = None,
        content: bytes | None = None,
        bearer: str | None = None,
        content_type: str | None = None,
    ) -> httpx.Response:
        headers: dict[str, str] = {}
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        if content_type:
            headers["Content-Type"] = content_type
        last_error: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                response = self._client.request(
                    method,
                    path,
                    content=content,
                    json=json_body,
                    headers=headers,
                )
            except httpx.TransportError as exc:
                last_error = exc
                if attempt < _MAX_ATTEMPTS - 1:
                    continue
                raise CoordinatorUnavailable(
                    f"coordinator unreachable after {_MAX_ATTEMPTS} "
                    f"attempts: {exc}"
                ) from exc
            if response.status_code >= 500 and attempt < _MAX_ATTEMPTS - 1:
                last_error = CoordinatorError(
                    response.status_code, "transient server error"
                )
                continue
            return response
        raise CoordinatorUnavailable(f"coordinator kept failing: {last_error}")

    @staticmethod
    def _json(response: httpx.Response) -> JsonObject:
        try:
            payload = response.json()
        except ValueError as exc:
            raise CoordinatorError(
                response.status_code,
                f"non-JSON response body: {exc}",
            ) from exc
        if not isinstance(payload, dict):
            raise CoordinatorError(
                response.status_code, "response body is not a JSON object"
            )
        return payload

    # ── endpoints ────────────────────────────────────────────────

    def enroll(self, name: str, capabilities: list[str]) -> JsonObject:
        """Enroll this runner; returns the enrollment secret envelope."""
        response = self._request(
            "POST",
            "/v1/runners/enroll",
            json_body={"name": name, "capabilities": capabilities},
        )
        if response.status_code != 201:
            raise self._error(response)
        return _unwrap(self._json(response))

    def rotate_key(
        self, runner_key: str, name: str, capabilities: list[str]
    ) -> JsonObject:
        """Rotate the runner key; response shape equals enroll."""
        response = self._request(
            "POST",
            "/v1/runners/rotate-key",
            bearer=runner_key,
            json_body={"name": name, "capabilities": capabilities},
        )
        if response.status_code != 201 and response.status_code != 200:
            raise self._error(response)
        return _unwrap(self._json(response))

    def lease(
        self, runner_key: str, capabilities: list[str]
    ) -> JsonObject | None:
        """Claim one job, or return ``None`` when the queue is empty."""
        response = self._request(
            "POST",
            "/v1/runners/lease",
            bearer=runner_key,
            json_body={"capabilities": capabilities},
        )
        if response.status_code == 200:
            lease = _unwrap_null(self._json(response))
            return lease if isinstance(lease, dict) else None
        raise self._error(response)

    def heartbeat(
        self, runner_key: str, job_id: str, attempt: int
    ) -> JsonObject:
        """Renew the lease; raises on 409 ``lease_lost``."""
        response = self._request(
            "POST",
            "/v1/runners/heartbeat",
            bearer=runner_key,
            json_body={"job_id": job_id, "attempt": attempt},
        )
        if response.status_code != 200:
            raise self._error(response)
        return _unwrap(self._json(response))

    def upload_artifact(
        self, runner_key: str, job_id: str, name: str, data: bytes
    ) -> JsonObject:
        """Upload one artifact; returns sha256/size_bytes/stored."""
        response = self._request(
            "POST",
            f"/v1/runners/jobs/{job_id}/artifacts/{name}",
            bearer=runner_key,
            content=data,
            content_type="application/octet-stream",
        )
        if response.status_code != 200:
            raise self._error(response)
        return _unwrap(self._json(response))

    def submit_receipt(
        self, runner_key: str, job_id: str, body: JsonObject
    ) -> JsonObject:
        """Submit the signed receipt; returns the acceptance envelope."""
        response = self._request(
            "POST",
            f"/v1/runners/jobs/{job_id}/receipt",
            bearer=runner_key,
            json_body=body,
        )
        if response.status_code != 200:
            raise self._error(response)
        return _unwrap(self._json(response))

    def health(self) -> bool:
        """Best-effort reachability probe used by ``doctor``."""
        try:
            response = self._client.get("/health")
        except httpx.TransportError:
            return False
        return response.status_code < 500

    @staticmethod
    def _error(response: httpx.Response) -> CoordinatorError:
        detail = response.text
        try:
            payload = response.json()
            if isinstance(payload, dict):
                detail = str(payload.get("detail", response.text))
        except ValueError:
            pass
        return CoordinatorError(response.status_code, detail)

    def close(self) -> None:
        self._client.close()
