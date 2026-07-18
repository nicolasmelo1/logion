"""browse.sh adapter."""

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

_SOURCE_OWNER = "browserbase"
_SOURCE_REPO = "browse.sh"


class BrowseShAdapter:
    """Discover the browse.sh skill catalog from its published sitemap."""

    hub_slug = "browse_sh"

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
        """Emit the official source repo when the sitemap lists skills."""
        if limit is not None and limit < 1:
            return
        base_url = target.rstrip("/")
        base = urlparse(base_url)
        locations = self._xml_locations(f"{base_url}/sitemap.xml")
        skill_count = sum(
            1
            for location in locations
            if self._is_skill_url(location, base.scheme, base.netloc)
        )
        if skill_count == 0:
            return

        channel = DiscoveryChannel(
            hub_slug=self.hub_slug,
            hub_url=base_url,
            hub_verified=True,
            metadata=(("catalogEntries", str(skill_count)),),
        )
        yield DiscoveredSkill(
            canonical=CanonicalSkillId(
                owner=_SOURCE_OWNER,
                repo=_SOURCE_REPO,
            ),
            title="browse.sh skills",
            summary="",
            original_author=_SOURCE_OWNER,
            license_spdx=None,
            source_commit=None,
            tags=(),
            channels=(channel,),
            inferred_map=None,
            map_flags=(),
            bundle=None,
        )

    @staticmethod
    def _is_skill_url(url: str, scheme: str, netloc: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme != scheme or parsed.netloc != netloc:
            return False
        parts = [part for part in parsed.path.split("/") if part]
        return len(parts) == 3 and parts[0] == "skills"

    def _xml_locations(self, url: str) -> list[str]:
        text = self.crawler.fetch_page(url)
        if text is None:
            raise RuntimeError("browse.sh sitemap fetch failed")
        root_pattern = r"<(?:[A-Za-z_][\w.-]*:)?urlset\b"
        if re.search(root_pattern, text, re.IGNORECASE) is None:
            raise RuntimeError("browse.sh sitemap returned invalid XML")
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
