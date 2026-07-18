"""skills.sh hub adapter."""

from __future__ import annotations

import html
import re
from collections.abc import Iterable
from urllib.parse import urljoin, urlparse

from ..canonical import CanonicalSkillId
from ..crawl import Crawler
from ..models import DiscoveredSkill, DiscoveryChannel
from ..rate_limit import RateLimiter
from ..transport import Transport


class SkillsShAdapter:
    """Discover GitHub repositories from the published skills.sh sitemaps."""

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
        """Fetch skill sitemaps and emit each GitHub repository once."""
        base_url = target.rstrip("/")
        base = urlparse(base_url)
        index_url = f"{base_url}/sitemap.xml"
        sitemap_urls = self._xml_locations(index_url)
        seen_repos: set[tuple[str, str]] = set()
        count = 0

        for sitemap_url in sitemap_urls:
            parsed_sitemap = urlparse(sitemap_url)
            if (
                parsed_sitemap.scheme != base.scheme
                or parsed_sitemap.hostname != base.hostname
                or not parsed_sitemap.path.startswith("/sitemap-skills-")
            ):
                continue

            for skill_url in self._xml_locations(sitemap_url):
                parsed_skill = urlparse(skill_url)
                if (
                    parsed_skill.scheme != base.scheme
                    or parsed_skill.hostname != base.hostname
                ):
                    continue
                parts = [part for part in parsed_skill.path.split("/") if part]
                if len(parts) != 3:
                    continue
                owner, repo, skill_name = parts
                repo_key = (owner.lower(), repo.lower())
                if repo_key in seen_repos:
                    continue
                if limit is not None and count >= limit:
                    return
                seen_repos.add(repo_key)

                channel = DiscoveryChannel(
                    hub_slug=self.hub_slug,
                    hub_url=base_url,
                    hub_verified=False,
                )
                yield DiscoveredSkill(
                    canonical=CanonicalSkillId(owner=owner, repo=repo),
                    title=skill_name,
                    original_author=owner,
                    channels=(channel,),
                )
                count += 1

    def _xml_locations(self, url: str) -> list[str]:
        text = self.crawler.fetch_page(url)
        if text is None:
            raise RuntimeError(f"skills.sh sitemap fetch failed: {url}")
        root_pattern = r"<(?:[A-Za-z_][\w.-]*:)?(?:sitemapindex|urlset)\b"
        if re.search(root_pattern, text, re.IGNORECASE) is None:
            raise RuntimeError(
                f"skills.sh sitemap returned invalid XML: {url}"
            )
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
