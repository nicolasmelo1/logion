"""Crawl orchestration: robots.txt, rate limiter, in-memory cache, UA."""

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
    - in-memory URL cache (handled by Transport)
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

    def fetch_page(self, url: str) -> str | None:
        """Fetch a page with rate limiting and robots.txt respect.

        Returns the page text on success, or ``None`` if the network
        request failed (e.g., transient URLError/DNS error).  HTTP non-200
        still raises ``RuntimeError`` and robots.txt blocks raise
        ``PermissionError``.
        """
        if not self.is_allowed(url):
            raise PermissionError(f"blocked by robots.txt: {url}")
        self.rate_limiter.wait(url)
        try:
            resp = self.transport.get(url)
        except Exception:
            return None
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
    # Collect consecutive User-agent lines before a Disallow/Allow group.
    # If ANY of them match our agent, the group applies to us.
    group_agents: list[str] = []
    applies_to_us = False
    in_rule_group = False

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
            # If we were collecting disallows for a previous group,
            # a new User-agent line starts a fresh group.
            if in_rule_group:
                group_agents = []
                applies_to_us = False
                in_rule_group = False
            group_agents.append(value.lower())
            if (
                value == "*"
                or value.lower() in ua_lower
                or ua_lower.startswith(value.lower())
            ):
                applies_to_us = True
        elif field_name in ("disallow", "allow"):
            in_rule_group = True
            if field_name == "disallow" and applies_to_us and value:
                disallowed.append(value)

    return RobotsRule(allowed=True, disallowed_paths=disallowed)
