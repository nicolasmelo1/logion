"""Hermes docs adapter: scrape skills from the documentation site."""

from __future__ import annotations

import re
from collections.abc import Iterable

from ..canonical import CanonicalSkillId
from ..crawl import Crawler
from ..models import DiscoveredSkill, DiscoveryChannel
from ..transport import Transport

# Match GitHub repo links in the docs pages.
_GITHUB_LINK_RE = re.compile(
    r'href="(https?://github\.com/([^/"]+)/([^/"]+))"',
    re.IGNORECASE,
)
_SKILL_TITLE_RE = re.compile(
    r'<h[12][^>]*id="([^"]*)"[^>]*>(.*?)</h[12]>',
    re.DOTALL | re.IGNORECASE,
)


class HermesDocsAdapter:
    """Adapter for hermes-agent.nousresearch.com/docs/skills."""

    hub_slug = "hermes_docs"

    def __init__(self, transport: Transport) -> None:
        self.transport = transport
        self.crawler = Crawler(transport)

    def discover(
        self,
        target: str,
        *,
        limit: int | None = None,
    ) -> Iterable[DiscoveredSkill]:
        """Crawl the Hermes docs skills page, extract GitHub links."""
        base_url = target.rstrip("/")
        html = self._fetch_page(base_url)
        if not html:
            return

        github_links = _GITHUB_LINK_RE.findall(html)
        count = 0
        seen: set[str] = set()
        for _full_url, owner, repo in github_links:
            if limit is not None and count >= limit:
                return
            cid_str = f"{owner}/{repo}".lower()
            if cid_str in seen:
                continue
            seen.add(cid_str)

            channel = DiscoveryChannel(
                hub_slug=self.hub_slug,
                hub_url=base_url,
                hub_verified=False,
            )
            yield DiscoveredSkill(
                canonical=CanonicalSkillId(owner=owner, repo=repo),
                title="",
                summary="",
                original_author=owner,
                license_spdx=None,
                source_commit=None,
                tags=(),
                channels=(channel,),
                inferred_map=None,
                map_flags=(),
            )
            count += 1

    def _fetch_page(self, url: str) -> str:
        try:
            return self.crawler.fetch_page(url)
        except (PermissionError, RuntimeError):
            return ""
