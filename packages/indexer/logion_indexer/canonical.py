"""Canonical skill identity: one skill == one GitHub repo[/subpath].

Normalization rules:
- owner and repo are lowercased
- trailing ``.git`` is stripped
- GitHub URL prefixes (https://github.com/, git@github.com:) are stripped
- subpath is stripped of leading/trailing ``/`` and lowercased
- str form: ``gh:{owner}/{repo}`` or ``gh:{owner}/{repo}#{subpath}``
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_GITHUB_URL_RE = re.compile(
    r"^(?:https?://github\.com/|git@github\.com:)"
    r"([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?(?:/.*)?$"
)
_GITHUB_SSH_RE = re.compile(
    r"^git@github\.com:([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?(?:/.*)?$"
)


def _strip_github_url(raw: str) -> str:
    """Strip GitHub URL/SSH prefixes, return ``owner/repo`` or the raw."""
    m = _GITHUB_URL_RE.match(raw)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    m = _GITHUB_SSH_RE.match(raw)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return raw


def _strip_dotgit(s: str) -> str:
    if s.endswith(".git"):
        return s[:-4]
    return s


@dataclass(frozen=True, order=True)
class CanonicalSkillId:
    """Canonical identity for a skill: ``gh:owner/repo[#subpath]``.

    Attributes:
        owner: GitHub owner login, lowercased.
        repo: GitHub repository name, lowercased, ``.git`` stripped.
        subpath: Normalized subpath (no leading/trailing ``/``),
            lowercased; empty for repo-root skills.
    """

    owner: str
    repo: str
    subpath: str = ""

    def __post_init__(self) -> None:
        # dataclass(frozen=True) doesn't allow assignment, so use
        # object.__setattr__ for normalization.
        object.__setattr__(self, "owner", self.owner.lower())
        object.__setattr__(self, "repo", _strip_dotgit(self.repo.lower()))
        object.__setattr__(
            self,
            "subpath",
            self.subpath.strip("/").lower() if self.subpath else "",
        )

    def __str__(self) -> str:
        if self.subpath:
            return f"gh:{self.owner}/{self.repo}#{self.subpath}"
        return f"gh:{self.owner}/{self.repo}"

    @classmethod
    def from_str(cls, raw: str) -> CanonicalSkillId:
        """Parse a canonical id string ``gh:owner/repo[#subpath]``.

        Also accepts raw ``owner/repo`` or ``https://github.com/owner/repo``
        forms, normalizing them.
        """
        s = raw.strip()
        if s.startswith("gh:"):
            s = s[3:]

        subpath = ""
        if "#" in s:
            s, subpath = s.split("#", 1)

        s = _strip_dotgit(s)
        s = _strip_github_url(s)
        s = _strip_dotgit(s)

        # Handle github.com/owner/repo/extra/path → subpath
        parts = s.split("/", 2)
        if len(parts) < 2:
            raise ValueError(f"invalid canonical id: {raw!r}")
        owner = parts[0]
        repo = parts[1]
        extra = parts[2] if len(parts) > 2 else ""

        if extra and not subpath:
            subpath = extra

        return cls(owner=owner, repo=repo, subpath=subpath)

    @classmethod
    def from_github_url(cls, url: str) -> CanonicalSkillId:
        """Parse a GitHub URL like ``https://github.com/o/r[/subpath]``."""
        s = url.strip()
        # Strip query/fragment
        s = s.split("#", 1)[0]
        s = s.split("?", 1)[0]
        if s.endswith(".git"):
            s = s[:-4]
        # Strip the scheme+host prefix.
        for prefix in (
            "https://github.com/",
            "http://github.com/",
            "git@github.com:",
        ):
            if s.lower().startswith(prefix):
                s = s[len(prefix) :]
                break
        else:
            raise ValueError(f"not a github URL: {url!r}")
        # Now s is "owner/repo[/extra/path]"
        parts = s.split("/", 2)
        if len(parts) < 2:
            raise ValueError(f"invalid github URL: {url!r}")
        owner = parts[0]
        repo = parts[1]
        subpath = parts[2] if len(parts) > 2 else ""
        return cls(owner=owner, repo=repo, subpath=subpath)
