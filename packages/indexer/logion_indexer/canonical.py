"""Canonical identity for skills and resources.

``CanonicalSkillId`` is the legacy form: ``gh:owner/repo[#subpath]``.
``CanonicalResourceId`` generalises this with an explicit
``resource_type`` field so the same dedup logic can cover skills,
plugins, MCP servers, models, and hosted courses.

For skills, ``CanonicalResourceId`` with ``resource_type="skill"``
preserves the legacy ``gh:owner/repo`` URI inside the explicit
``skill:`` resource prefix; the legacy ``CanonicalSkillId`` string remains
available through the compatibility adapter.
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
# Matches /tree/<branch>/ or /blob/<branch>/ prefixes in GitHub URLs.
# Captures the subpath after the branch, or empty if just tree/<branch>.
_TREE_BLOB_PREFIX_RE = re.compile(r"^(?:tree|blob)/[^/]+(?:/(.*))?$")


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
        # Strip /tree/<branch>/ or /blob/<branch>/ prefix so that
        # .../tree/main/skills/foo → subpath="skills/foo".
        if subpath:
            tree_match = _TREE_BLOB_PREFIX_RE.match(subpath)
            if tree_match:
                subpath = tree_match.group(1)
        return cls(owner=owner, repo=repo, subpath=subpath)


_VALID_RESOURCE_TYPES = frozenset({
    "course",
    "mcp_server",
    "model",
    "plugin",
    "skill",
})
_RESOURCE_PREFIX_RE = re.compile(r"^([A-Za-z_]+):(.+)$")


@dataclass(frozen=True, order=True)
class CanonicalResourceId:
    """Canonical identity for any indexed resource.

    Attributes:
        resource_type: One of ``skill``, ``plugin``, ``mcp_server``,
            ``model``, or ``course``.
        uri: Normalised URI string.  For skills this is the same as
            ``str(CanonicalSkillId)`` (``gh:owner/repo[#subpath]``).
    """

    resource_type: str
    uri: str

    def __post_init__(self) -> None:
        # Normalise resource_type to lowercase.
        object.__setattr__(self, "resource_type", self.resource_type.lower())
        if self.resource_type not in _VALID_RESOURCE_TYPES:
            msg = (
                f"invalid resource_type {self.resource_type!r}; "
                f"must be one of {sorted(_VALID_RESOURCE_TYPES)}"
            )
            raise ValueError(msg)

    def __str__(self) -> str:
        """Canonical string form: ``<type>:<uri>``.

        For skills this produces ``skill:gh:owner/repo[#subpath]`` which
        preserves the ``gh:`` prefix in the URI component.
        """
        return f"{self.resource_type}:{self.uri}"

    @classmethod
    def from_str(cls, raw: str) -> CanonicalResourceId:
        """Parse ``<type>:<uri>`` or a bare ``gh:`` skill URI.

        Bare ``gh:owner/repo`` strings are interpreted as skills for
        backwards compatibility.
        """
        raw = raw.strip()
        m = _RESOURCE_PREFIX_RE.match(raw)
        if m:
            rtype = m.group(1).lower()
            uri = m.group(2)
            # If the matched prefix is not a known resource type,
            # treat the whole string as a skill URI (e.g. "gh:owner/repo").
            if rtype not in _VALID_RESOURCE_TYPES:
                rtype = "skill"
                uri = raw
        else:
            # Bare string without type prefix — treat as a skill URI.
            rtype = "skill"
            uri = raw
        return cls(resource_type=rtype, uri=uri)

    @classmethod
    def from_skill_id(cls, skill_id: CanonicalSkillId) -> CanonicalResourceId:
        """Lift a :class:`CanonicalSkillId` into a
        :class:`CanonicalResourceId`."""
        return cls(resource_type="skill", uri=str(skill_id))
