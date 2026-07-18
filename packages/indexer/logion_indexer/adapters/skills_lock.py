"""skills-lock.json adapter (vercel-labs `skills` CLI format).

Parses a ``skills-lock.json`` file with format::

    {
      "version": 1,
      "skills": {
        "skill-name": {
          "source": "owner/repo",
          "sourceType": "github",
          "computedHash": "sha256:..."
        }
      }
    }

Only ``sourceType == "github"`` entries are accepted; others are
dropped with reason ``unsupported_source_type``.  The lockfile's
``computedHash`` is preserved on the discovery channel's ``metadata``.

Unknown ``version`` values → adapter hard-fail.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from urllib.parse import urlparse

from ..canonical import CanonicalSkillId
from ..crawl import Crawler
from ..models import DiscoveredSkill, DiscoveryChannel
from ..rate_limit import RateLimiter
from ..transport import Transport

SUPPORTED_VERSION = 1


class SkillsLockAdapter:
    """Adapter for skills-lock.json files."""

    hub_slug = "skills_lock"

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
        """Parse a skills-lock.json from URL or local path.

        Args:
            target: URL or local file path to the skills-lock.json.
            limit: Maximum items.

        Raises:
            ValueError: If the lockfile version is unsupported.
        """
        data = self._load_lockfile(target)
        if not isinstance(data, dict):
            return

        version = data.get("version", 0)
        if version != SUPPORTED_VERSION:
            raise ValueError(
                f"unsupported skills-lock.json version: {version} "
                f"(expected {SUPPORTED_VERSION})"
            )

        skills = data.get("skills") or {}
        if not isinstance(skills, dict):
            return

        count = 0
        for name, info in skills.items():
            if limit is not None and count >= limit:
                return
            if not isinstance(info, dict):
                continue

            source_type = info.get("sourceType", "")
            if source_type != "github":
                continue

            source = info.get("source", "")
            if not source:
                continue

            computed_hash = info.get("computedHash", "")

            try:
                canonical = CanonicalSkillId.from_str(source)
            except ValueError:
                continue

            channel = DiscoveryChannel(
                hub_slug=self.hub_slug,
                hub_url=target,
                hub_verified=False,
                metadata=(("computedHash", computed_hash),)
                if computed_hash
                else (),
            )

            yield DiscoveredSkill(
                canonical=canonical,
                title=name,
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

    def _load_lockfile(self, target: str) -> dict:
        """Load a skills-lock.json from URL or local path."""
        if urlparse(target).scheme in {"http", "https"}:
            text = self.crawler.fetch_page(target)
            if text is None:
                raise RuntimeError(f"skills-lock fetch failed: {target}")
        else:
            with open(target) as fh:
                text = fh.read()
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid skills-lock JSON: {target}") from exc
        return data if isinstance(data, dict) else {}
