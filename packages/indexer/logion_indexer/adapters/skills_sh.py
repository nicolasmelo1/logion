"""skills.sh hub adapter."""

from __future__ import annotations

import re
from collections.abc import Iterable

from ..canonical import CanonicalSkillId
from ..crawl import Crawler
from ..github_resolver import resolve_hub_page
from ..models import DiscoveredSkill, DiscoveryChannel
from ..rate_limit import RateLimiter
from ..transport import Transport

# Match skill listing entries on skills.sh pages.
_SKILL_LINK_RE = re.compile(
    r'<a[^>]+href="(/skill[s]?/[^"]+)"[^>]*>([^<]*)</a>',
    re.IGNORECASE,
)


class SkillsShAdapter:
    """Adapter for skills.sh hub."""

    hub_slug = "skills_sh"

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
        """Crawl skills.sh, extract GitHub links from each listing."""
        base_url = target.rstrip("/")
        html = self._fetch_page(base_url)
        if not html:
            return

        skill_links = _SKILL_LINK_RE.findall(html)
        count = 0
        for path, title in skill_links:
            if limit is not None and count >= limit:
                return
            skill_url = f"{base_url}{path}"
            resolved = self._resolve_skill_page(skill_url)
            if resolved:
                canonical, _page_html = resolved
                # resolve_hub_page already produced a canonical id
                # (possibly with a subpath).  Only fall back to the
                # regex if it somehow returned without resolving.
                # (The _resolve_skill_page helper guarantees resolution,
                # so this branch is defensive.)
                channel = DiscoveryChannel(
                    hub_slug=self.hub_slug,
                    hub_url=skill_url,
                    hub_verified=False,
                )
                yield DiscoveredSkill(
                    canonical=canonical,
                    title=title.strip(),
                    summary="",
                    original_author=canonical.owner,
                    license_spdx=None,
                    source_commit=None,
                    tags=(),
                    channels=(channel,),
                    inferred_map=None,
                    map_flags=(),
                )
                count += 1

    def _fetch_page(self, url: str) -> str:
        """Fetch a page via the crawler (robots.txt + rate limit)."""
        try:
            html = self.crawler.fetch_page(url)
        except (PermissionError, RuntimeError):
            return ""
        return html if html is not None else ""

    def _resolve_skill_page(
        self, url: str
    ) -> tuple[CanonicalSkillId, str] | None:
        """Fetch a skill page and extract a GitHub link."""
        html = self._fetch_page(url)
        if not html:
            return None
        resolved = resolve_hub_page(url, html)
        if not resolved.resolved or resolved.canonical is None:
            return None
        return resolved.canonical, html
