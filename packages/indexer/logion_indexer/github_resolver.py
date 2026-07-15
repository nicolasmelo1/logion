"""GitHub resolver: hub page/url -> owner/repo[#subpath].

Given a hub listing page, extract the GitHub repository link and
return a :class:`CanonicalSkillId`.  Hub items without a GitHub source
are dropped with reason ``no_github_source``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .canonical import CanonicalSkillId
from .transport import Transport

# Match github.com/owner/repo URLs in href attributes.
_GITHUB_HREF_RE = re.compile(
    r'href="(https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)'
    r'(?:/tree/[^/]+/([^"]+))?[^"]*)"',
    re.IGNORECASE,
)
# Match github.com/owner/repo in plain text.
_GITHUB_TEXT_RE = re.compile(
    r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)",
    re.IGNORECASE,
)


@dataclass
class ResolvedSource:
    """Result of resolving a hub page to a GitHub source."""

    canonical: CanonicalSkillId | None
    reason: str = ""

    @property
    def resolved(self) -> bool:
        return self.canonical is not None


def resolve_hub_page(
    page_url: str,  # noqa: ARG001
    html: str,
) -> ResolvedSource:
    """Extract a GitHub repo link from a hub page's HTML.

    Returns ``ResolvedSource(canonical=None, reason='no_github_source')``
    when no GitHub link is found.
    """
    # Try href first — it gives us the subpath too.
    for m in _GITHUB_HREF_RE.finditer(html):
        owner = m.group(2)
        repo = m.group(3)
        subpath = m.group(4) or ""
        full = m.group(1)
        # Skip non-repo paths (issues, pulls, wiki, settings, fork).
        path_after_repo = full.split(f"/{repo}/", 1)
        if len(path_after_repo) > 1:
            next_segment = path_after_repo[1].split("/")[0]
            # Strip trailing quote or query params.
            next_segment = next_segment.rstrip('"?')
            if next_segment in {
                "issues",
                "pulls",
                "wiki",
                "settings",
                "fork",
                "new",
                "actions",
                "projects",
                "security",
                "pulse",
                "graphs",
            }:
                continue
        return ResolvedSource(
            canonical=CanonicalSkillId(owner=owner, repo=repo, subpath=subpath)
        )

    # Fall back to plain text.
    for m in _GITHUB_TEXT_RE.finditer(html):
        owner = m.group(1)
        repo = m.group(2)
        # Check what follows the repo in the text — skip
        # non-repo paths like /issues, /pulls, etc.
        match_end = m.end()
        rest = html[match_end:]
        next_char = rest[:1]
        if next_char == "/":
            next_segment = rest[1:].split("/")[0].split('"')[0].split("?")[0]
            if next_segment in {
                "issues",
                "pulls",
                "wiki",
                "settings",
                "fork",
                "new",
                "actions",
                "projects",
                "security",
                "pulse",
                "graphs",
            }:
                continue
        return ResolvedSource(
            canonical=CanonicalSkillId(owner=owner, repo=repo)
        )

    return ResolvedSource(canonical=None, reason="no_github_source")


def resolve_github_url(url: str) -> ResolvedSource:
    """Parse a direct GitHub URL into a canonical id."""
    try:
        return ResolvedSource(canonical=CanonicalSkillId.from_github_url(url))
    except ValueError:
        return ResolvedSource(canonical=None, reason="no_github_source")


def fetch_and_resolve(
    page_url: str,
    transport: Transport,
) -> ResolvedSource:
    """Fetch a hub page and resolve it to a GitHub source."""
    resp = transport.get(page_url)
    if resp.status != 200:
        return ResolvedSource(canonical=None, reason=f"http_{resp.status}")
    return resolve_hub_page(page_url, resp.text)
