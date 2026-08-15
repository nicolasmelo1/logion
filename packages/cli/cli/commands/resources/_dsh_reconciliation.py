"""DeepSeek Harness native-state reader used by reconciliation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def discover_dsh_state(scope_root: Path) -> list[dict[str, Any]]:
    """Read dsh profile state without invoking or mutating the manager."""
    results: list[dict[str, Any]] = []
    profiles = scope_root / ".dsh" / "profiles"
    if not profiles.is_dir():
        return results
    for profile in sorted(profiles.iterdir()):
        package_path = profile / "package.json"
        profile_path = profile / "dsh.profile"
        if not package_path.is_file() or not profile_path.is_file():
            continue
        try:
            package = json.loads(package_path.read_text(encoding="utf-8"))
            manifest = json.loads(profile_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            results.append({
                "manager": "dsh",
                "unsupported": "invalid profile state",
                "path": str(profile),
            })
            continue
        bundles = (
            (manifest.get("dsh") or {}).get("profile", {}).get("bundles")
            if isinstance(manifest, dict)
            else None
        )
        if not isinstance(bundles, list) or not isinstance(package, dict):
            results.append({
                "manager": "dsh",
                "unsupported": "unknown profile state",
                "path": str(profile),
            })
            continue
        for name in bundles:
            if not isinstance(name, str):
                continue
            plugin_manifest = profile / "node_modules" / name / "package.json"
            try:
                plugin = json.loads(
                    plugin_manifest.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                results.append({
                    "manager": "dsh",
                    "source": name,
                    "revision": "",
                    "path": str(plugin_manifest),
                    "unsupported": "plugin manifest missing",
                })
                continue
            revision = (
                str(plugin.get("gitHead") or "")
                if isinstance(plugin, dict)
                else ""
            )
            results.append({
                "manager": "dsh",
                "name": name,
                "source": str((plugin or {}).get("repository") or name),
                "revision": revision,
                "path": str(plugin_manifest.parent),
                "resource_version_id": None,
            })
    return results
