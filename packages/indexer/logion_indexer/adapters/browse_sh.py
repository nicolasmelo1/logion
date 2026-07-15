"""browse.sh adapter."""

from __future__ import annotations

import re
from collections.abc import Iterable

from ..crawl import Crawler
from ..github_resolver import resolve_hub_page
from ..models import DiscoveredSkill, DiscoveryChannel
from ..transport import Transport

_LISTING_RE = re.compile(
    r'<a[^>]+href="([^"]*)"[^>]*class="[^"]*listing[^"]*"[^>]*>(.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)
_TITLE_RE = re.compile(r"<h[23][^>]*>(.*?)</h[23]>", re.DOTALL | re.IGNORECASE)


class BrowseShAdapter:
    """Adapter for browse.sh hub."""

    hub_slug = "browse_sh"

    def __init__(self, transport: Transport) -> None:
        self.transport = transport
        self.crawler = Crawler(transport)

    def discover(
        self,
        target: str,
        *,
        limit: int | None = None,
    ) -> Iterable[DiscoveredSkill]:
        """Crawl browse.sh, extract GitHub links from listings."""
        base_url = target.rstrip("/")
        html = self._fetch_page(base_url)
        if not html:
            return

        listings = _LISTING_RE.findall(html)
        count = 0
        for _href, inner_html in listings:
            if limit is not None and count >= limit:
                return
            resolved = resolve_hub_page(base_url, inner_html)
            if not resolved.resolved or resolved.canonical is None:
                continue

            title_match = _TITLE_RE.search(inner_html)
            title = title_match.group(1).strip() if title_match else ""

            channel = DiscoveryChannel(
                hub_slug=self.hub_slug,
                hub_url=base_url,
                hub_verified=False,
            )
            yield DiscoveredSkill(
                canonical=resolved.canonical,
                title=title,
                summary="",
                original_author=resolved.canonical.owner,
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
