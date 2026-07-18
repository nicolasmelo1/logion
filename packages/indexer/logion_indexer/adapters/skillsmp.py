"""SkillsMP public sitemap adapter."""

from __future__ import annotations

import html
import re
from collections.abc import Iterable
from urllib.parse import ParseResult, urljoin, urlparse

from ..canonical import CanonicalSkillId
from ..crawl import Crawler
from ..models import DiscoveredSkill, DiscoveryChannel
from ..rate_limit import RateLimiter
from ..transport import Transport

_SKILL_SITEMAPS = {
    "/sitemaps/skills-popular.xml",
    "/sitemaps/skills-discovered.xml",
}


class SkillsMpAdapter:
    """Discover GitHub repositories from SkillsMP's public skill sitemaps."""

    hub_slug = "skillsmp"

    def __init__(
        self,
        transport: Transport,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self.crawler = Crawler(transport, rate_limiter=rate_limiter)

    def discover(
        self,
        target: str,
        *,
        limit: int | None = None,
    ) -> Iterable[DiscoveredSkill]:
        base_url = target.rstrip("/")
        base = urlparse(base_url)
        self.crawler.rate_limiter.cap_rps(base.hostname or base.netloc, 1.0)
        sitemap_urls = self._xml_locations(f"{base_url}/sitemap.xml")
        seen: set[CanonicalSkillId] = set()
        count = 0

        for sitemap_url in sitemap_urls:
            parsed_sitemap = urlparse(sitemap_url)
            if not self._same_origin(base, parsed_sitemap):
                continue
            if parsed_sitemap.path not in _SKILL_SITEMAPS:
                continue
            for skill_url in self._xml_locations(sitemap_url):
                parsed_skill = urlparse(skill_url)
                if not self._same_origin(base, parsed_skill):
                    continue
                parts = [part for part in parsed_skill.path.split("/") if part]
                if len(parts) != 4 or parts[0] != "creators":
                    continue
                _, owner, repo, skill_name = parts
                canonical = CanonicalSkillId(owner=owner, repo=repo)
                if canonical in seen:
                    continue
                if limit is not None and count >= limit:
                    return
                seen.add(canonical)
                yield DiscoveredSkill(
                    canonical=canonical,
                    title=skill_name,
                    original_author=canonical.owner,
                    channels=(
                        DiscoveryChannel(
                            hub_slug=self.hub_slug,
                            hub_url=skill_url,
                            hub_verified=False,
                        ),
                    ),
                )
                count += 1

    @staticmethod
    def _same_origin(
        base: ParseResult,
        candidate: ParseResult,
    ) -> bool:
        return (
            candidate.scheme == base.scheme and candidate.netloc == base.netloc
        )

    def _xml_locations(self, url: str) -> list[str]:
        text = self.crawler.fetch_page(url)
        if text is None:
            raise RuntimeError(f"SkillsMP sitemap fetch failed: {url}")
        root_pattern = r"<(?:[A-Za-z_][\w.-]*:)?(?:sitemapindex|urlset)\b"
        if re.search(root_pattern, text, re.IGNORECASE) is None:
            raise RuntimeError(f"SkillsMP sitemap returned invalid XML: {url}")
        locations = re.findall(
            r"<(?:[A-Za-z_][\w.-]*:)?loc\b[^>]*>\s*(.*?)\s*</(?:[A-Za-z_][\w.-]*:)?loc>",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        return [
            urljoin(url, html.unescape(location.strip()))
            for location in locations
            if location.strip()
        ]
