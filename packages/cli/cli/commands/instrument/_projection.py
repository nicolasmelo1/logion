# SPDX-License-Identifier: MIT
"""Projection tree planning per target.

Each target gets a projection tree with a portable core, publisher
artifact, instrumentation profile, capability, and reporter binding.
The generator copies the portable core byte-identical; a digest
comparison proves it. Every receipt names the original publisher
and exact version. Execution lives in ``_write.py``; reporter
templates in ``_reporters.py``; default profile in ``_write.py``.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from cli._json import JsonObject

from ._digest import canonical_json, profile_digest
from ._reporters import NODE_REPORTER, PYTHON_REPORTER

#: The integration version stamped on every projection.
INTEGRATION_VERSION = "logion.publisher-reporter.v1"


def _slugify(value: str) -> str:
    """Normalize *value* into a safe directory slug."""
    normalized = re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip("-.")
    return normalized[:128] if normalized else "resource"


def _resource_slug(resource: JsonObject, version: str) -> str:
    """Derive a slug from the resource title or canonical URI."""
    raw = resource.get("title") or resource.get("canonical_uri") or version
    return _slugify(str(raw))


def _plugin_json(
    resource: JsonObject,
    version: JsonObject,
    publisher_identity: str,
) -> JsonObject:
    """Build the portable core plugin.json (Agent Plugins 1.0.0)."""
    return {
        "schema": "agent-plugin/v1.0.0",
        "name": str(
            resource.get("title") or resource.get("canonical_uri") or ""
        ),
        "version": str(version.get("version") or version.get("id") or ""),
        "publisher": {"identity": publisher_identity},
        "resource_id": str(
            resource.get("id") or resource.get("canonical_uri") or ""
        ),
        "resource_version": str(
            version.get("version") or version.get("id") or ""
        ),
    }


def _receipt(
    resource: JsonObject,
    version: JsonObject,
    publisher_identity: str,
    distribution_digest: str,
    profile_dig: str,
    target: str,
) -> JsonObject:
    """Build an emitted receipt naming the original publisher and version."""
    return {
        "schema": "logion.publisher-receipt/v1",
        "publisher": {"identity": publisher_identity},
        "resource_id": str(
            resource.get("id") or resource.get("canonical_uri") or ""
        ),
        "resource_version": str(
            version.get("version") or version.get("id") or ""
        ),
        "distribution_digest": distribution_digest,
        "profile_digest": profile_dig,
        "integration_version": INTEGRATION_VERSION,
        "target": target,
    }


def _projection_path(output_dir: Path, target: str, slug: str) -> Path:
    """Return the root path for a single target's projection tree."""
    return output_dir / target / slug


def _write_file(path: Path, content: str | bytes) -> None:
    """Write *content* to *path*, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


def _write_json(path: Path, obj: JsonObject) -> None:
    """Write *obj* as canonical JSON to *path*."""
    _write_file(path, canonical_json(obj) + "\n")


def _file_digest_bytes(data: bytes) -> str:
    """Return ``sha256:<hex>`` for *data*."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _compute_planned_digest(files: list[dict[str, str]]) -> str:
    """Compute a deterministic digest over the planned file set."""
    h = hashlib.sha256()
    for entry in sorted(files, key=lambda f: f["path"]):
        relative = entry["path"]
        digest = entry["content_sha256"]
        h.update(f"{relative}\0{digest}\n".encode())
    return f"sha256:{h.hexdigest()}"


def build_projection(
    *,
    target: str,
    resource: JsonObject,
    version: JsonObject,
    profile: JsonObject,
    output_dir: Path,
    publisher_identity: str,
) -> JsonObject:
    """Build a projection plan entry for one target.

    Returns a plan entry describing the files that would be (or were)
    written, the distribution_digest, and the receipt. The function
    never writes to disk — execution lives in ``_write.py``.
    """
    slug = _resource_slug(resource, str(version.get("version") or ""))
    proj_root = _projection_path(output_dir, target, slug)

    plugin = _plugin_json(resource, version, publisher_identity)
    files: list[dict[str, str]] = []

    # plugin.json — the portable core
    core_path = proj_root / "plugin.json"
    core_content = canonical_json(plugin) + "\n"
    files.append({
        "path": str(core_path),
        "role": "portable-core",
        "content_sha256": _file_digest_bytes(core_content.encode()),
    })

    # skills/<slug>/SKILL.md — the publisher's artifact
    skill_path = proj_root / "skills" / slug / "SKILL.md"
    skill_content = f"# {resource.get('title', slug)}\n\n"
    skill_content += f"Version: {version.get('version', '?')}\n"
    files.append({
        "path": str(skill_path),
        "role": "publisher-artifact",
        "content_sha256": _file_digest_bytes(skill_content.encode()),
    })

    # .logion/instrumentation.json — the profile
    profile_path = proj_root / ".logion" / "instrumentation.json"
    profile_content = canonical_json(profile) + "\n"
    files.append({
        "path": str(profile_path),
        "role": "instrumentation-profile",
        "content_sha256": _file_digest_bytes(profile_content.encode()),
    })

    # .logion/capability.json — placeholder; resolved by caller
    capability_path = proj_root / ".logion" / "capability.json"
    files.append({
        "path": str(capability_path),
        "role": "capability",
        "content_sha256": "pending",
    })

    # .logion/consent.json — written at install time, not now
    consent_path = proj_root / ".logion" / "consent.json"
    files.append({
        "path": str(consent_path),
        "role": "consent-placeholder",
        "content_sha256": "not-written",
    })

    # Reporter binding
    if target in ("agent-plugin", "dsh-plugin"):
        reporter_path = proj_root / ".logion" / "reporter" / "report.mjs"
        files.append({
            "path": str(reporter_path),
            "role": "reporter-node",
            "content_sha256": _file_digest_bytes(NODE_REPORTER.encode()),
        })
    if target in ("hermes-plugin", "static-skill"):
        reporter_path = proj_root / ".logion" / "reporter" / "report.py"
        files.append({
            "path": str(reporter_path),
            "role": "reporter-python",
            "content_sha256": _file_digest_bytes(PYTHON_REPORTER.encode()),
        })

    # dsh-plugin emits the Cordis bundle shape
    if target == "dsh-plugin":
        dsh_manifest = proj_root / "package.json"
        dsh_content = (
            canonical_json({
                "name": f"@logionsh/dsh-plugin/{slug}",
                "version": str(version.get("version") or "0.0.0"),
                "tier": "explicit_report",
            })
            + "\n"
        )
        files.append({
            "path": str(dsh_manifest),
            "role": "dsh-bundle-manifest",
            "content_sha256": _file_digest_bytes(dsh_content.encode()),
        })

    distribution_digest = _compute_planned_digest(files)

    receipt = _receipt(
        resource=resource,
        version=version,
        publisher_identity=publisher_identity,
        distribution_digest=distribution_digest,
        profile_dig=profile_digest(profile),
        target=target,
    )

    return {
        "target": target,
        "slug": slug,
        "projection_root": str(proj_root),
        "files": files,
        "distribution_digest": distribution_digest,
        "integration_version": INTEGRATION_VERSION,
        "receipt": receipt,
    }
