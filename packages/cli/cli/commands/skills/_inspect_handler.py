"""Handler for ``logion skills inspect``.

Kept separate from :mod:`handlers` so each file stays under the
CLI's per-source-file line budget.
"""

from __future__ import annotations

import argparse
from typing import Any

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._local_state import list_installed, read_manifest
from cli._output import emit_json

from ._install_helpers import resolve_target


def _fetch_remote_course(
    args: argparse.Namespace, course_id: str
) -> dict[str, Any] | None:
    """Try to fetch remote course metadata; return None on failure."""
    try:
        config = resolve_config_from_args(args)
        client = make_client(config)
        try:
            result = client.v1.courses.get(course_id=course_id)
        except Exception:
            return None
        else:
            if hasattr(result, "model_dump"):
                return result.model_dump(mode="json")  # type: ignore[union-attr]
            if isinstance(result, dict):
                return result
            return None
        finally:
            client.close()
    except Exception:
        return None


_REMOTE_MERGE_KEYS = (
    "title",
    "slug",
    "status",
    "visibility",
    "description",
    "short_summary",
    "price_cents",
    "currency",
    "language",
    "owner_agent_id",
)


def handle_skills_inspect(args: argparse.Namespace) -> int:
    """Inspect an installed skill, enriched with remote data when available."""
    home = resolve_target(args)
    course_id: str = args.course_id
    version_id: str | None = getattr(args, "version_id", None)
    if version_id is None:
        candidates = [
            m for m in list_installed(home) if m.get("course_id") == course_id
        ]
        if not candidates:
            print(
                f"No installation found for course {course_id}",
            )
            return 1
        manifest: dict[str, Any] = candidates[-1]
    else:
        manifest = read_manifest(course_id, version_id, home) or {}
        if not manifest:
            print(
                f"No installation found for {course_id}/{version_id}",
            )
            return 1

    remote_data = _fetch_remote_course(args, course_id)

    # Merge: start with local manifest, overlay remote metadata
    merged: dict[str, Any] = dict(manifest)
    if remote_data is not None:
        for key in _REMOTE_MERGE_KEYS:
            if key in remote_data and remote_data[key] is not None:
                merged.setdefault(key, remote_data[key])

    if getattr(args, "json_output", False):
        emit_json("logion.skills.inspect", merged)
    else:
        # Print key provenance fields for human readability
        fields = [
            ("course_id", merged.get("course_id", "")),
            ("version_id", merged.get("version_id", "")),
            ("title", merged.get("title", "")),
            ("source", merged.get("source", "")),
            ("entitlement_status", merged.get("entitlement_status", "")),
            ("license_scope", merged.get("license_scope", "")),
            (
                "official_update_channel",
                merged.get("official_update_channel", ""),
            ),
            (
                "last_verified_at",
                merged.get("last_verified_at", "") or "never",
            ),
        ]
        for label, value in fields:
            print(f"  {label}: {value}")

    return 0
