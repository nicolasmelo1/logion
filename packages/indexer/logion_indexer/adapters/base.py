"""Hub adapter protocol — re-exported for clarity."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from ..models import DiscoveredSkill


@runtime_checkable
class HubAdapter(Protocol):
    """Protocol for hub adapters.

    Each adapter discovers skills from a hub and yields
    :class:`DiscoveredSkill` objects with a canonical GitHub identity.
    Items without a GitHub source are dropped with reason
    ``no_github_source`` by the caller (dedup pipeline).
    """

    hub_slug: str

    def discover(
        self,
        target: str,
        *,
        limit: int | None = None,
    ) -> Iterable[DiscoveredSkill]:
        """Discover skills from this hub."""
        ...
