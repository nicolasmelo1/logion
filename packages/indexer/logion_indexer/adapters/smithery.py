"""Smithery public skills sitemap adapter."""

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

_REPOSITORY_RE = re.compile(
    r">\s*Repository\s*</span>.{0,2500}?href=[\"'](https://github\.com/[^\"']+)",
    re.IGNORECASE | re.DOTALL,
)


class SmitheryAdapter:
    """Discover GitHub-backed skills from Smithery's public sitemaps."""

    hub_slug = "smithery"

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
        sitemap_urls = self._xml_locations(f"{base_url}/sitemap_index.xml")
        skill_urls: set[str] = set()

        for sitemap_url in sitemap_urls:
            parsed = urlparse(sitemap_url)
            if not self._same_origin(base, parsed):
                continue
            if not parsed.path.startswith("/skills/sitemap/"):
                continue
            skill_urls.update(
                url
                for url in self._xml_locations(sitemap_url)
                if self._same_origin(base, urlparse(url))
                and urlparse(url).path.startswith("/skills/")
            )

        seen: set[CanonicalSkillId] = set()
        count = 0
        for skill_url in sorted(skill_urls):
            if limit is not None and count >= limit:
                return
            page = self.crawler.fetch_page(skill_url)
            if page is None:
                raise RuntimeError(f"Smithery skill fetch failed: {skill_url}")
            canonical = self._repository(page)
            if canonical is None or canonical in seen:
                continue
            seen.add(canonical)
            title = urlparse(skill_url).path.rstrip("/").rsplit("/", 1)[-1]
            yield DiscoveredSkill(
                canonical=canonical,
                title=title,
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
    def _repository(page: str) -> CanonicalSkillId | None:
        match = _REPOSITORY_RE.search(page)
        if match is None:
            return None
        try:
            source = CanonicalSkillId.from_github_url(
                html.unescape(match.group(1))
            )
        except ValueError:
            return None
        return CanonicalSkillId(owner=source.owner, repo=source.repo)

    @staticmethod
    def _same_origin(base: ParseResult, candidate: ParseResult) -> bool:
        return (
            candidate.scheme == base.scheme and candidate.netloc == base.netloc
        )

    def _xml_locations(self, url: str) -> list[str]:
        text = self.crawler.fetch_page(url)
        if text is None:
            raise RuntimeError(f"Smithery sitemap fetch failed: {url}")
        root_pattern = r"<(?:[A-Za-z_][\w.-]*:)?(?:sitemapindex|urlset)\b"
        if re.search(root_pattern, text, re.IGNORECASE) is None:
            raise RuntimeError(f"Smithery sitemap returned invalid XML: {url}")
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
