"""Crawl orchestration: robots.txt, rate limiter, ETag cache, UA."""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from .rate_limit import RateLimiter
from .transport import Transport


@dataclass
class RobotsRule:
    """Parsed robots.txt rules for a host."""

    allowed: bool = True
    disallowed_paths: list[str] = field(default_factory=list)


class Crawler:
    """Crawl helper: robots.txt respect, rate limiting, caching.

    Adapters use this to fetch hub pages with crawl discipline:
    - respect robots.txt ``Disallow`` rules
    - rate-limit per host (default 1 req/s)
    - identified User-Agent
    - ETag/Last-Modified cache (handled by Transport)
    """

    def __init__(
        self,
        transport: Transport,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self.transport = transport
        self.rate_limiter = rate_limiter or RateLimiter()
        self._robots_cache: dict[str, RobotsRule] = {}

    def fetch_robots_txt(self, base_url: str) -> RobotsRule:
        """Fetch and parse robots.txt for a host."""
        parsed = urlparse(base_url)
        host = parsed.hostname or ""
        if not host:
            return RobotsRule()

        if host in self._robots_cache:
            return self._robots_cache[host]

        robots_url = f"{parsed.scheme}://{host}/robots.txt"
        self.rate_limiter.wait(robots_url)
        try:
            resp = self.transport.get(robots_url)
        except Exception:
            rule = RobotsRule()
            self._robots_cache[host] = rule
            return rule

        rule = RobotsRule()
        if resp.status == 200:
            rule = _parse_robots_txt(resp.text, self.transport.user_agent)
        self._robots_cache[host] = rule
        return rule

    def is_allowed(self, url: str) -> bool:
        """Check if a URL is allowed by robots.txt."""
        parsed = urlparse(url)
        host = parsed.hostname or ""
        path = parsed.path or "/"
        rule = self._robots_cache.get(host)
        if rule is None:
            rule = self.fetch_robots_txt(url)
        if not rule.allowed:
            return False
        for disallowed in rule.disallowed_paths:
            if path.startswith(disallowed):
                return False
        return True

    def fetch_page(self, url: str) -> str:
        """Fetch a page with rate limiting and robots.txt respect."""
        if not self.is_allowed(url):
            raise PermissionError(f"blocked by robots.txt: {url}")
        self.rate_limiter.wait(url)
        resp = self.transport.get(url)
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status} for {url}")
        return resp.text


def _parse_robots_txt(text: str, user_agent: str) -> RobotsRule:
    """Parse a robots.txt file for the given user-agent.

    A ``User-agent: *`` rule applies to everyone.  A specific agent
    rule only applies when it matches our UA.  We look for ``Disallow``
    lines under matching ``User-agent`` sections.
    """
    ua_lower = user_agent.lower()
    disallowed: list[str] = []
    current_agents: list[str] = []
    applies_to_us = False

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if ":" not in line:
            continue

        field_name, _, value = line.partition(":")
        field_name = field_name.strip().lower()
        value = value.strip()

        if field_name == "user-agent":
            # New section starts.
            if current_agents and applies_to_us:
                # Already collected disallows for a matching section.
                pass
            current_agents = [value.lower()]
            applies_to_us = (
                value == "*"
                or value.lower() in ua_lower
                or ua_lower.startswith(value.lower())
            )
        elif field_name == "disallow":
            if applies_to_us and value:
                disallowed.append(value)

    return RobotsRule(allowed=True, disallowed_paths=disallowed)
