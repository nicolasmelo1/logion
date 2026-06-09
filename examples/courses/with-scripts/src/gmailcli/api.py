"""Gmail REST API client using only the Python standard library.

Hits the Gmail v1 REST API directly via urllib.request. No third-party
HTTP client, no OAuth library, no transitive dependencies. The bundle
is what runs.

Reference: https://developers.google.com/gmail/api/reference/rest
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from .auth import get_oauth_token

_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
_TIMEOUT_SECONDS = 30


class GmailAPIError(Exception):
    """Raised when the Gmail API returns a non-2xx response."""


def _request(path: str, params: dict | None = None) -> dict:
    token = get_oauth_token()
    url = _API_BASE + path
    if params:
        # Drop None values so callers can pass optional kwargs cleanly.
        clean = {k: v for k, v in params.items() if v is not None}
        if clean:
            url = url + "?" + urllib.parse.urlencode(clean)
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise GmailAPIError(
            f"Gmail API returned HTTP {exc.code}: {body[:200]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise GmailAPIError(f"Gmail API request failed: {exc.reason}") from exc


def search_messages(query: str, max_results: int = 10) -> list[dict]:
    """Search the user's mailbox using Gmail's standard query syntax.

    Returns a list of {id, threadId} dicts. Use get_message for details.
    """
    result = _request(
        "/messages",
        {"q": query, "maxResults": max_results},
    )
    return result.get("messages", [])


def get_message(message_id: str, format: str = "metadata") -> dict:
    """Fetch a single message by id.

    format: 'minimal' | 'full' | 'metadata' | 'raw'. Default 'metadata'
    keeps payload small (subject + headers, no body).
    """
    return _request(f"/messages/{message_id}", {"format": format})


def list_labels() -> list[dict]:
    """List the labels (folders) configured on the user's mailbox."""
    result = _request("/labels")
    return result.get("labels", [])
