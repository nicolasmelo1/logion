"""GitHub observer for proving-ground assertions.

Queries github.com via the GitHub REST API with a token from env. This
is an OBSERVER used by assertions — it does NOT replace
the Logion adapter.

Token env keys: ``LOGION_PROVING_GROUND_GH_TOKEN_CREATOR``,
``LOGION_PROVING_GROUND_GH_TOKEN_BUYER``. If a token is absent, observer
methods return a sentinel that makes dependent assertions
``unsupported`` (skipped if ``optional: true``, failed otherwise) —
mirroring the ``RoleKeyStore`` missing-key behavior.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

GITHUB_API_BASE = "https://api.github.com"
_TIMEOUT_S = 10
_USER_AGENT = "Logion Proving Ground"

CREATOR_TOKEN_ENV = "LOGION_PROVING_GROUND_GH_TOKEN_CREATOR"
BUYER_TOKEN_ENV = "LOGION_PROVING_GROUND_GH_TOKEN_BUYER"


class GithubObserver:
    """Observe GitHub state for proving-ground assertions."""

    def __init__(self, *, token: str, repo: str) -> None:
        self._token = token
        self._repo = repo

    @classmethod
    def from_env(
        cls,
        *,
        role: str = "creator",
        repo: str | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> GithubObserver | None:
        env: dict[str, str] = {**os.environ, **(extra_env or {})}
        if role == "creator":
            token_key = CREATOR_TOKEN_ENV
        elif role == "buyer":
            token_key = BUYER_TOKEN_ENV
        else:
            return None
        token = env.get(token_key)
        if not token:
            return None
        repo_value = repo or env.get("LOGION_PROVING_GROUND_GH_REPO", "")
        if not repo_value:
            return None
        return cls(token=token, repo=repo_value)

    def _get(self, path: str) -> dict[str, Any] | None:
        url = f"{GITHUB_API_BASE}/repos/{self._repo}/{path}"
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "User-Agent": _USER_AGENT,
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:  # nosec B310
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 404):
                return None
            return None
        except urllib.error.URLError:
            return None
        try:
            return json.loads(raw)  # type: ignore[no-any-return]
        except Exception:
            return None

    def _get_raw(self, url: str) -> dict[str, Any] | list[Any] | None:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "User-Agent": _USER_AGENT,
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:  # nosec B310
                raw = resp.read()
        except (urllib.error.HTTPError, urllib.error.URLError):
            return None
        try:
            return json.loads(raw)  # type: ignore[no-any-return]
        except Exception:
            return None

    def pr_exists(
        self,
        *,
        head_branch: str | None = None,
        marker: str | None = None,
    ) -> dict[str, Any] | None:
        """Find an open PR matching head_branch or body marker."""
        query = {"state": "open"}
        if head_branch:
            owner = self._repo.split("/", 1)[0]
            query["head"] = (
                head_branch if ":" in head_branch else f"{owner}:{head_branch}"
            )
        path = f"pulls?{urllib.parse.urlencode(query)}"
        url = f"{GITHUB_API_BASE}/repos/{self._repo}/{path}"
        prs = self._get_raw(url)
        if not isinstance(prs, list):
            return None
        for pr in prs:
            if not isinstance(pr, dict) or pr.get("state") != "open":
                continue
            if marker:
                body = pr.get("body") or ""
                if marker in body:
                    return pr
            elif head_branch:
                return pr
        return None

    def pr_state(self, pr_number: int) -> str:
        """Return 'open', 'merged', 'closed', or 'unknown'."""
        pr = self._get(f"pulls/{pr_number}")
        if pr is None:
            return "unknown"
        if pr.get("merged_at"):
            return "merged"
        if pr.get("state") == "open":
            return "open"
        return "closed"

    def pr_body_contains(self, pr_number: int, needle: str) -> bool:
        pr = self._get(f"pulls/{pr_number}")
        if pr is None:
            return False
        return needle in (pr.get("body") or "")

    def issue_comments(self, issue_number: int) -> list[dict[str, Any]]:
        url = (
            f"{GITHUB_API_BASE}/repos/{self._repo}"
            f"/issues/{issue_number}/comments"
        )
        comments = self._get_raw(url)
        if not isinstance(comments, list):
            return []
        return [c for c in comments if isinstance(c, dict)]
