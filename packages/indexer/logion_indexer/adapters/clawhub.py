"""ClawHub adapter."""

from __future__ import annotations

import re
from collections.abc import Iterable

from ..crawl import Crawler
from ..github_resolver import resolve_hub_page
from ..models import DiscoveredSkill, DiscoveryChannel
from ..transport import Transport

# Match skill card entries on ClawHub.
_CARD_RE = re.compile(
    r'(<div[^>]*class="[^"]*skill[^"]*"[^>]*>.*?</div>)',
    re.DOTALL | re.IGNORECASE,
)
_TITLE_RE = re.compile(r"<h[23][^>]*>(.*?)</h[23]>", re.DOTALL | re.IGNORECASE)
_VERIFIED_RE = re.compile(r'class="[^"]*verified[^"]*"', re.IGNORECASE)


class ClawhubAdapter:
    """Adapter for ClawHub (clawhub.ai)."""

    hub_slug = "clawhub"

    def __init__(self, transport: Transport) -> None:
        self.transport = transport
        self.crawler = Crawler(transport)

    def discover(
        self,
        target: str,
        *,
        limit: int | None = None,
    ) -> Iterable[DiscoveredSkill]:
        """Crawl clawhub.ai, extract GitHub links from skill cards."""
        base_url = target.rstrip("/")
        html = self._fetch_page(base_url)
        if not html:
            return

        cards = _CARD_RE.findall(html)
        count = 0
        for card_html in cards:
            if limit is not None and count >= limit:
                return
            resolved = resolve_hub_page(base_url, card_html)
            if not resolved.resolved or resolved.canonical is None:
                continue

            title_match = _TITLE_RE.search(card_html)
            title = title_match.group(1).strip() if title_match else ""
            verified = bool(_VERIFIED_RE.search(card_html))

            channel = DiscoveryChannel(
                hub_slug=self.hub_slug,
                hub_url=base_url,
                hub_verified=verified,
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
