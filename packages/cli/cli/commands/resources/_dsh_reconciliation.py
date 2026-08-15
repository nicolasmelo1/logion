"""DeepSeek Harness native-state reader used by reconciliation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cli._harness.dsh import dsh_home_for

from ._dsh_state import read_all_profiles


def discover_dsh_state(scope_root: Path) -> list[dict[str, Any]]:
    """Read dsh profile state without invoking or mutating the manager."""
    results: list[dict[str, Any]] = []
    for bundle in read_all_profiles(dsh_home_for(scope_root)):
        entry: dict[str, Any] = {
            "manager": "dsh",
            "name": bundle.name,
            # Attribution runs off the canonical source and the immutable
            # revision. A bundle whose manifest carries neither stays
            # unlinked rather than being matched on its name.
            "source": bundle.repository or bundle.spec,
            "revision": bundle.revision,
            "resource_version_id": None,
            "path": str(bundle.path),
            "profile": bundle.profile,
        }
        if bundle.unsupported:
            entry["unsupported"] = bundle.unsupported
        results.append(entry)
    return results
