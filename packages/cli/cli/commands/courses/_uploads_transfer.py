# SPDX-License-Identifier: MIT
"""Presigned-URL transfer for course bundle uploads.

The upload manifest comes from the SDK, but the PUTs themselves go to
short-lived presigned object-storage URLs that have no SDK wrapper, so
they use httpx directly (allowlisted in ``scripts/check_cli_http.lock``).
"""

from __future__ import annotations

import time
from pathlib import Path

from cli._json import JsonObject, child, opt_str


def put_one(
    upload: JsonObject,
    local_path: Path,
    max_retries: int,
    timeout: float,
) -> tuple[bool, str]:
    """PUT *local_path* to ``upload['put_url']`` with retries.

    Returns ``(success, message)``.  Retries on transient httpx
    errors and HTTP 5xx; aborts immediately on 4xx (presigned URL
    rejected — usually a content-length / header mismatch).
    """
    import httpx

    url = opt_str(upload, "put_url", "")
    if not url:
        return False, "missing put_url"
    # httpx wants real strings; the manifest is decoded JSON.
    raw_headers = child(upload, "required_headers")
    headers = {key: str(value) for key, value in raw_headers.items()}

    last_err = ""
    for attempt in range(max_retries + 1):
        try:
            with local_path.open("rb") as fh:
                response = httpx.request(
                    opt_str(upload, "method", "PUT"),
                    url,
                    content=fh,
                    headers=headers,
                    timeout=timeout,
                )
        except httpx.RequestError as exc:
            last_err = f"network error: {exc}"
        else:
            if 200 <= response.status_code < 300:
                return True, f"HTTP {response.status_code}"
            if 400 <= response.status_code < 500:
                # Client errors won't recover on retry.
                return False, (
                    f"HTTP {response.status_code}: {response.text[:200]}"
                )
            last_err = f"HTTP {response.status_code}"
        if attempt < max_retries:
            # Linear backoff is enough — presigned URLs are short-lived.
            time.sleep(0.5 * (attempt + 1))
    return False, last_err or "exhausted retries"
