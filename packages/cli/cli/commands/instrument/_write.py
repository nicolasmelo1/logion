# SPDX-License-Identifier: MIT
"""Projection execution and default profile building.

Extracted from ``_projection.py`` to keep source files under the
250-line architecture limit. ``execute_projection`` writes the
projection tree to disk after approval; ``build_default_profile``
generates a default instrumentation profile from a ResourceVersion.
"""

from __future__ import annotations

from pathlib import Path

from cli._json import JsonObject

from ._digest import directory_digest, profile_digest
from ._projection import (
    INTEGRATION_VERSION,
    _plugin_json,
    _write_file,
    _write_json,
)
from ._reporters import NODE_REPORTER, PYTHON_REPORTER


def execute_projection(
    plan_entry: JsonObject,
    *,
    resource: JsonObject,
    version: JsonObject,
    profile: JsonObject,
    publisher_identity: str,
    capability: JsonObject,
) -> JsonObject:
    """Write the projection tree to disk from a plan entry.

    Called only after approval. Writes every file described in the
    plan, then verifies the distribution_digest matches.
    """
    proj_root = Path(str(plan_entry["projection_root"]))
    slug = str(plan_entry["slug"])
    target = str(plan_entry["target"])

    # plugin.json
    plugin = _plugin_json(resource, version, publisher_identity)
    _write_json(proj_root / "plugin.json", plugin)

    # skills/<slug>/SKILL.md
    skill_path = proj_root / "skills" / slug / "SKILL.md"
    skill_content = f"# {resource.get('title', slug)}\n\n"
    skill_content += f"Version: {version.get('version', '?')}\n"
    _write_file(skill_path, skill_content)

    # .logion/instrumentation.json
    _write_json(proj_root / ".logion" / "instrumentation.json", profile)

    # .logion/capability.json
    _write_json(proj_root / ".logion" / "capability.json", capability)

    # .logion/reporter/
    if target in ("agent-plugin", "dsh-plugin"):
        _write_file(
            proj_root / ".logion" / "reporter" / "report.mjs",
            NODE_REPORTER,
        )
    if target in ("hermes-plugin", "static-skill"):
        _write_file(
            proj_root / ".logion" / "reporter" / "report.py",
            PYTHON_REPORTER,
        )

    # dsh-plugin bundle manifest
    if target == "dsh-plugin":
        dsh_manifest: JsonObject = {
            "name": f"@logionsh/dsh-plugin/{slug}",
            "version": str(version.get("version") or "0.0.0"),
            "tier": "explicit_report",
        }
        _write_json(proj_root / "package.json", dsh_manifest)

    # Verify the distribution_digest after writing
    actual_digest = directory_digest(proj_root)

    return {
        "target": target,
        "projection_root": str(proj_root),
        "distribution_digest": actual_digest,
        "profile_digest": profile_digest(profile),
        "integration_version": INTEGRATION_VERSION,
        "verified": actual_digest == plan_entry.get("distribution_digest"),
        "receipt": plan_entry["receipt"],
    }


def build_default_profile(
    *,
    resource: JsonObject,
    version: JsonObject,
    events: list[str],
    delivery_endpoint: str,
    delivery_mode: str,
    max_batch: int,
    max_spool_bytes: int,
    publisher_identity: str,
) -> JsonObject:
    """Build a default instrumentation profile from a ResourceVersion.

    The profile uses the canonical vocabulary from the instrumentation
    package's schema and includes all sensitive categories in the
    ``excluded`` array.
    """
    resource_id = str(
        resource.get("id") or resource.get("canonical_uri") or ""
    )
    resource_version = str(version.get("version") or version.get("id") or "")

    return {
        "schema": "logion.instrumentation/v1",
        "subject": {
            "resource_id": resource_id,
            "resource_version": resource_version,
        },
        "publisher": {"identity": publisher_identity},
        "delivery": {
            "endpoint": delivery_endpoint,
            "mode": delivery_mode,
            "max_batch": max_batch,
            "max_spool_bytes": max_spool_bytes,
        },
        "events": events,
        "fields": [
            "resource_id",
            "resource_version",
            "distribution_digest",
            "event",
            "outcome",
            "duration_bucket",
            "harness",
            "integration_version",
        ],
        "excluded": [
            "prompt",
            "file_content",
            "local_path",
            "tool_arguments",
            "tool_results",
            "model_context",
            "secrets",
            "user_identity",
        ],
        "integration_version": INTEGRATION_VERSION,
    }
