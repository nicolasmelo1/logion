"""ClawHub adapter."""

from __future__ import annotations

import json
from collections.abc import Iterable

from ..canonical import CanonicalSkillId
from ..crawl import Crawler
from ..models import DiscoveredSkill, DiscoveryChannel
from ..rate_limit import RateLimiter
from ..transport import Transport

_FEED_PATH = "/v1/feeds/skills"


class ClawhubAdapter:
    """Discover verified GitHub-backed skills from ClawHub's public feed."""

    hub_slug = "clawhub"

    def __init__(
        self,
        transport: Transport,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self.transport = transport
        self.crawler = Crawler(transport, rate_limiter=rate_limiter)

    def discover(
        self,
        target: str,
        *,
        limit: int | None = None,
    ) -> Iterable[DiscoveredSkill]:
        """Fetch the official feed and emit GitHub-backed candidates."""
        base_url = target.rstrip("/")
        entries = self._fetch_entries(f"{base_url}{_FEED_PATH}")
        seen: set[CanonicalSkillId] = set()
        count = 0

        for entry in entries:
            if limit is not None and count >= limit:
                return
            skill = self._parse_entry(entry, base_url)
            if skill is None or skill.canonical in seen:
                continue
            seen.add(skill.canonical)
            yield skill
            count += 1

    def _fetch_entries(self, feed_url: str) -> list:
        text = self.crawler.fetch_page(feed_url)
        if text is None:
            raise RuntimeError("ClawHub skills feed fetch failed")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "ClawHub skills feed returned invalid JSON"
            ) from exc
        if not isinstance(data, dict):
            raise TypeError("ClawHub skills feed returned invalid data")
        entries = data.get("entries")
        if not isinstance(entries, list):
            raise TypeError("ClawHub skills feed has no entries list")
        return entries

    def _parse_entry(
        self,
        entry: object,
        base_url: str,
    ) -> DiscoveredSkill | None:
        if not isinstance(entry, dict) or entry.get("state") != "available":
            return None
        candidate = self._github_candidate(entry)
        if candidate is None:
            return None
        github = candidate["github"]
        repo_ref = github.get("repo")
        path = github.get("path")
        if not isinstance(repo_ref, str) or not isinstance(path, str):
            return None
        repo_parts = repo_ref.split("/")
        if len(repo_parts) != 2 or not all(repo_parts) or not path:
            return None
        owner, repo = repo_parts
        canonical = CanonicalSkillId(owner=owner, repo=repo, subpath=path)

        title = entry.get("title")
        summary = entry.get("description")
        commit = github.get("commit")
        metadata = tuple(
            (key, value)
            for key, value in (
                ("version", candidate.get("version")),
                ("integrity", candidate.get("integrity")),
                ("contentHash", github.get("contentHash")),
            )
            if isinstance(value, str) and value
        )
        channel = DiscoveryChannel(
            hub_slug=self.hub_slug,
            hub_url=base_url,
            hub_verified=True,
            metadata=metadata,
        )
        return DiscoveredSkill(
            canonical=canonical,
            title=title if isinstance(title, str) else "",
            summary=summary if isinstance(summary, str) else "",
            original_author=owner,
            license_spdx=None,
            source_commit=commit if isinstance(commit, str) else None,
            tags=(),
            channels=(channel,),
            inferred_map=None,
            map_flags=(),
            bundle=None,
        )

    @staticmethod
    def _github_candidate(entry: dict) -> dict | None:
        install = entry.get("install")
        if not isinstance(install, dict):
            return None
        candidates = install.get("candidates")
        if not isinstance(candidates, list):
            return None
        return next(
            (
                item
                for item in candidates
                if isinstance(item, dict)
                and isinstance(item.get("github"), dict)
            ),
            None,
        )
