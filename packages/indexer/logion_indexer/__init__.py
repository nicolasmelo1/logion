"""External skillhub indexer for Logion.

Crawls skill hubs, resolves every skill to its GitHub identity, dedups
across hubs, and batch-upserts to the Logion admin API.  Skill-root
detection and package-map inference are delegated to
``logion_skillmap.infer()`` — never reimplemented here.
"""

from __future__ import annotations

from .canonical import CanonicalSkillId
from .models import DiscoveredSkill, DiscoveryChannel

__all__ = [
    "CanonicalSkillId",
    "DiscoveredSkill",
    "DiscoveryChannel",
]
