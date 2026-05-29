"""Handler for ``logion skills inspect``.

Kept separate from :mod:`handlers` so each file stays under the
CLI's per-source-file line budget.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import emit_error_json
from cli._local_state import (
    UnsafeIdentifierError,
    _safe_segment,
    list_installed,
    read_manifest,
)
from cli._output import emit_json

from ._install_helpers import resolve_target

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
    "tags",
)


def _error(
    args: argparse.Namespace, code: str, message: str, exit_code: int
) -> int:
    """Emit a compliant error in JSON or human form."""
    if getattr(args, "json_output", False):
        emit_error_json(code, message, exit_code)
    else:
        print(f"ERROR: {message}", file=sys.stderr)
    return exit_code


def _to_plain_dict(value: Any) -> dict[str, Any] | None:
    """Convert SDK values to plain dicts when possible."""
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")  # type: ignore[union-attr]
    if isinstance(value, dict):
        return dict(value)
    return None


def _fetch_remote_payloads(
    args: argparse.Namespace,
    course_id: str,
    version_id: str | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Fetch remote course and version payloads when SDK support exists."""
    try:
        config = resolve_config_from_args(args)
        client = make_client(config)
    except Exception:
        return None, None

    try:
        remote_course = None
        remote_version = None
        try:
            remote_course = _to_plain_dict(
                client.v1.courses.get(course_id=course_id)
            )
        except Exception:
            remote_course = None

        if version_id is not None and hasattr(
            client.v1.courses, "get_version"
        ):
            try:
                remote_version = _to_plain_dict(
                    client.v1.courses.get_version(
                        course_id=course_id,
                        version_id=version_id,
                    )
                )
            except Exception:
                remote_version = None
        return remote_course, remote_version
    finally:
        client.close()


def _local_manifest_for_course(
    home: Any, course_id: str
) -> dict[str, Any] | None:
    """Return the newest available local manifest for *course_id*."""
    candidates = [
        m for m in list_installed(home) if m.get("course_id") == course_id
    ]
    if not candidates:
        return None
    return candidates[-1]


def _synthesized_remote_manifest(
    course_id: str,
    version_id: str | None,
    remote_course: dict[str, Any],
) -> dict[str, Any]:
    """Build a provenance-compatible inspect payload
    for remote-only courses.
    """
    latest_version = remote_course.get("latest_version_id")
    return {
        "course_id": course_id,
        "version_id": version_id or latest_version,
        "title": remote_course.get("title", ""),
        "source": "logion-marketplace",
        "entitlement_status": "missing",
        "license_scope": "unknown",
        "official_update_channel": True,
        "last_verified_at": None,
        "manifest_path": None,
        "entrypoint": "SKILL.md",
    }


def handle_skills_inspect(args: argparse.Namespace) -> int:
    """Inspect a local skill install, enriched with remote metadata."""
    home = resolve_target(args)
    course_id: str = args.course_id
    version_id: str | None = getattr(args, "version_id", None)
    verbose = bool(getattr(args, "verbose", False))

    try:
        _safe_segment(course_id, "course_id")
        if version_id is not None:
            _safe_segment(version_id, "version_id")
    except UnsafeIdentifierError as exc:
        return _error(args, "unsafe_identifier", str(exc), 2)

    manifest = (
        read_manifest(course_id, version_id, home)
        if version_id is not None
        else _local_manifest_for_course(home, course_id)
    )
    remote_course, remote_version = _fetch_remote_payloads(
        args, course_id, version_id
    )

    if manifest is None and remote_course is None:
        target = f"{course_id}/{version_id}" if version_id else course_id
        return _error(
            args, "not_found", f"No skill metadata found for {target}", 1
        )

    merged: dict[str, Any] = (
        dict(manifest)
        if manifest is not None
        else _synthesized_remote_manifest(
            course_id, version_id, remote_course or {}
        )
    )
    if remote_course is not None:
        for key in _REMOTE_MERGE_KEYS:
            if key in remote_course and remote_course[key] is not None:
                merged[key] = remote_course[key]
        if verbose:
            merged["remote_course"] = remote_course
    if remote_version is not None:
        merged["remote_version"] = remote_version
        merged["version_id"] = remote_version.get(
            "id", merged.get("version_id")
        )
        merged.setdefault(
            "capabilities_manifest_path",
            remote_version.get("capabilities_manifest_path"),
        )
        merged.setdefault("version_status", remote_version.get("status"))

    if getattr(args, "json_output", False):
        emit_json("logion.skills.inspect", merged)
    else:
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
            ("manifest_path", merged.get("manifest_path", "") or "n/a"),
        ]
        for label, value in fields:
            print(f"  {label}: {value}")
        if verbose and remote_version is not None:
            print(
                f"  remote_version_status: {remote_version.get('status', '')}"
            )

    return 0
