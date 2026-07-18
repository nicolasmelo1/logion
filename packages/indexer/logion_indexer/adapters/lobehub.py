"""LobeHub adapter."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from urllib.parse import urlencode, urlparse

from ..canonical import CanonicalSkillId
from ..crawl import Crawler
from ..models import DiscoveredSkill, DiscoveryChannel
from ..rate_limit import RateLimiter
from ..transport import Transport

_RSC_CHUNK_RE = re.compile(
    r'self\.__next_f\.push\(\[1,("(?:\\.|[^"\\])*")\]\)</script>'
)
_PAGE_META_RE = re.compile(
    r'"currentPage":(\d+),"pageSize":(\d+),'
    r'"tab":"skills","total":(\d+)'
)


class LobehubAdapter:
    """Discover GitHub repositories from LobeHub's paginated SSR catalog."""

    hub_slug = "lobehub"

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
        """Crawl every catalog page and emit each GitHub repository once."""
        if limit is not None and limit < 1:
            return
        base_url = target.rstrip("/")
        parsed_base = urlparse(base_url)
        seen_repos: set[CanonicalSkillId] = set()
        page = 1
        count = 0

        while True:
            items, current_page, page_size, total = self._fetch_catalog_page(
                base_url,
                parsed_base.path,
                page,
            )
            if current_page != page:
                raise RuntimeError(
                    f"LobeHub returned page {current_page} for request {page}"
                )

            for item in items:
                skill = self._repo_discovery(item, base_url)
                if skill is None or skill.canonical in seen_repos:
                    continue
                if limit is not None and count >= limit:
                    return
                seen_repos.add(skill.canonical)
                yield skill
                count += 1

            if limit is not None and count >= limit:
                return
            if page * page_size >= total:
                return
            if not items:
                raise RuntimeError(
                    f"LobeHub page {page} was empty before catalog end"
                )
            page += 1

    def _repo_discovery(
        self,
        item: dict,
        base_url: str,
    ) -> DiscoveredSkill | None:
        github = item.get("github")
        if not isinstance(github, dict):
            return None
        repo_url = github.get("url")
        if not isinstance(repo_url, str):
            return None
        try:
            source = CanonicalSkillId.from_github_url(repo_url)
        except ValueError:
            return None
        canonical = CanonicalSkillId(owner=source.owner, repo=source.repo)
        title = item.get("name")
        summary = item.get("description")
        license_spdx = item.get("license")
        channel = DiscoveryChannel(
            hub_slug=self.hub_slug,
            hub_url=base_url,
            hub_verified=False,
        )
        return DiscoveredSkill(
            canonical=canonical,
            title=title if isinstance(title, str) else "",
            summary=summary if isinstance(summary, str) else "",
            original_author=canonical.owner,
            license_spdx=(
                license_spdx if isinstance(license_spdx, str) else None
            ),
            source_commit=None,
            tags=(),
            channels=(channel,),
            inferred_map=None,
            map_flags=(),
            bundle=None,
        )

    def _fetch_catalog_page(
        self,
        base_url: str,
        base_path: str,
        page: int,
    ) -> tuple[list[dict], int, int, int]:
        page_url = f"{base_url}?{urlencode({'page': page})}"
        last_error: RuntimeError | None = None
        for _ in range(3):
            text = self.crawler.fetch_page(
                page_url,
                headers={
                    "Accept": "text/x-component",
                    "RSC": "1",
                    "Next-Url": f"{base_path}?page={page}",
                },
                use_cache=False,
            )
            if text is None:
                last_error = RuntimeError(f"LobeHub page {page} fetch failed")
                continue
            try:
                return self._parse_page(text)
            except RuntimeError as exc:
                last_error = exc
        raise last_error or RuntimeError(f"LobeHub page {page} fetch failed")

    @staticmethod
    def _parse_page(text: str) -> tuple[list[dict], int, int, int]:
        chunks: list[str] = []
        for match in _RSC_CHUNK_RE.finditer(text):
            try:
                chunks.append(json.loads(match.group(1)))
            except json.JSONDecodeError:
                continue
        payload = "".join(chunks) if chunks else text

        items: list[dict] = []
        decoder = json.JSONDecoder()
        position = 0
        marker = '"data":['
        while True:
            found = payload.find(marker, position)
            if found < 0:
                break
            start = found + len('"data":')
            try:
                value, _ = decoder.raw_decode(payload, start)
            except json.JSONDecodeError:
                position = start + 1
                continue
            if (
                isinstance(value, list)
                and value
                and isinstance(value[0], dict)
                and "identifier" in value[0]
            ):
                items.extend(item for item in value if isinstance(item, dict))
            position = start + 1

        metadata = _PAGE_META_RE.findall(payload)
        if not metadata:
            raise RuntimeError("LobeHub page has no pagination metadata")
        current_page, page_size, total = (int(value) for value in metadata[-1])
        return items, current_page, page_size, total
