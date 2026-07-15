"""LobeHub adapter."""

from __future__ import annotations

import re
from collections.abc import Iterable

from ..canonical import CanonicalSkillId
from ..crawl import Crawler
from ..github_resolver import resolve_hub_page
from ..models import DiscoveredSkill, DiscoveryChannel
from ..transport import Transport

# LobeHub may serve JSON or HTML.
_LOBEHUB_SKILL_RE = re.compile(
    r'"(?:github_url|source_url|repo_url)":\s*'
    r'"(https?://github\.com/([^/"]+)/([^/"]+))"',
    re.IGNORECASE,
)
_TITLE_FIELD_RE = re.compile(r'"(?:title|name)":\s*"([^"]*)"', re.IGNORECASE)
_VERIFIED_RE = re.compile(r'"(?:verified|featured)":\s*true', re.IGNORECASE)


class LobehubAdapter:
    """Adapter for LobeHub (lobehub.com/skills)."""

    hub_slug = "lobehub"

    def __init__(self, transport: Transport) -> None:
        self.transport = transport
        self.crawler = Crawler(transport)

    def discover(
        self,
        target: str,
        *,
        limit: int | None = None,
    ) -> Iterable[DiscoveredSkill]:
        """Crawl lobehub.com/skills, extract GitHub links from listings."""
        base_url = target.rstrip("/")
        html = self._fetch_page(base_url)
        if not html:
            return

        # Try JSON first (LobeHub may embed JSON data).
        skills = self._parse_json(html, base_url, limit)
        if skills:
            yield from skills
            return

        # Fall back to HTML parsing.
        yield from self._parse_html(html, base_url, limit)

    def _parse_json(
        self,
        html: str,
        base_url: str,
        limit: int | None,
    ) -> list[DiscoveredSkill]:
        """Parse JSON-embedded skill data from the page."""
        results: list[DiscoveredSkill] = []
        matches = _LOBEHUB_SKILL_RE.findall(html)
        count = 0
        for full_url, owner, repo in matches:
            if limit is not None and count >= limit:
                break
            title_match = _TITLE_FIELD_RE.search(
                html[
                    max(0, matches[0][0].find(full_url) - 500) : matches[0][
                        0
                    ].find(full_url)
                    + 500
                ]
                if full_url in html
                else ""
            )
            title = title_match.group(1) if title_match else ""
            verified = bool(_VERIFIED_RE.search(html))
            channel = DiscoveryChannel(
                hub_slug=self.hub_slug,
                hub_url=f"{base_url}/skills/{owner}/{repo}",
                hub_verified=verified,
            )
            results.append(
                DiscoveredSkill(
                    canonical=CanonicalSkillId(owner=owner, repo=repo),
                    title=title,
                    summary="",
                    original_author=owner,
                    license_spdx=None,
                    source_commit=None,
                    tags=(),
                    channels=(channel,),
                    inferred_map=None,
                    map_flags=(),
                )
            )
            count += 1  # noqa: SIM113
        return results

    def _parse_html(
        self,
        html: str,
        base_url: str,
        limit: int | None,
    ) -> Iterable[DiscoveredSkill]:
        """Parse HTML skill listings."""
        resolved = resolve_hub_page(base_url, html)
        if not resolved.resolved or resolved.canonical is None:
            return
        if limit is not None and limit < 1:
            return
        verified = bool(_VERIFIED_RE.search(html))
        channel = DiscoveryChannel(
            hub_slug=self.hub_slug,
            hub_url=base_url,
            hub_verified=verified,
        )
        yield DiscoveredSkill(
            canonical=resolved.canonical,
            title="",
            summary="",
            original_author=resolved.canonical.owner,
            license_spdx=None,
            source_commit=None,
            tags=(),
            channels=(channel,),
            inferred_map=None,
            map_flags=(),
        )

    def _fetch_page(self, url: str) -> str:
        try:
            return self.crawler.fetch_page(url)
        except (PermissionError, RuntimeError):
            return ""
