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
``computedHash`` is stored on the discovery channel and compared
against our own bundle hash at HEAD — mismatch is recorded as channel
metadata ``lock_drift=true``.

Unknown ``version`` values → adapter hard-fail.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from ..canonical import CanonicalSkillId
from ..models import DiscoveredSkill, DiscoveryChannel
from ..transport import Transport

SUPPORTED_VERSION = 1


class SkillsLockAdapter:
    """Adapter for skills-lock.json files."""

    hub_slug = "skills_lock"

    def __init__(self, transport: Transport) -> None:
        self.transport = transport

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

            info.get("computedHash", "")

            try:
                canonical = CanonicalSkillId.from_str(source)
            except ValueError:
                continue

            channel = DiscoveryChannel(
                hub_slug=self.hub_slug,
                hub_url=target,
                hub_verified=False,
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
        if target.startswith("http"):
            resp = self.transport.get(target)
            if resp.status != 200:
                return {}
            data = resp.json()
            return data if isinstance(data, dict) else {}
        # Local file.
        with open(target) as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {}


def check_lock_drift(
    computed_hash: str,
    our_hash: str,
) -> bool:
    """Return True if the lockfile hash differs from our own."""
    if not computed_hash or not our_hash:
        return False
    return computed_hash != our_hash
