"""Local capability manifest validator for the Logion CLI.

Validates and normalizes ``course/capabilities.yaml`` WITHOUT calling the
API.  Rules mirror the server-side Phase 2 validation closely enough for
author feedback.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

CAPABILITY_MANIFEST_PATH = Path("course/capabilities.yaml")
ALLOWED_TOOLS = {"browser", "terminal", "file", "web", "vision"}
ENV_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


class CapabilityManifestError(ValueError):
    """Raised when a capability manifest fails validation."""


def load_and_validate_capability_manifest(
    bundle_dir: Path,
) -> dict[str, Any]:
    """Load and validate a capability manifest from *bundle_dir*.

    Returns the normalised manifest dictionary on success.
    Raises :class:`CapabilityManifestError` on any validation failure.
    """
    manifest_path = bundle_dir / CAPABILITY_MANIFEST_PATH
    if not manifest_path.exists():
        raise CapabilityManifestError("Missing course/capabilities.yaml")
    try:
        raw = yaml.safe_load(manifest_path.read_text())
    except yaml.YAMLError as exc:
        raise CapabilityManifestError(
            "Invalid YAML in course/capabilities.yaml"
        ) from exc
    if not isinstance(raw, dict):
        raise CapabilityManifestError("Capability manifest must be a mapping")
    return normalize_capability_manifest(raw)


def normalize_capability_manifest(
    raw: dict[str, Any],
) -> dict[str, Any]:
    """Normalise and validate a raw parsed capability manifest."""
    unknown = set(raw) - {
        "version",
        "summary",
        "tools",
        "network",
        "filesystem",
        "secrets",
        "human_approval",
    }
    if unknown:
        raise CapabilityManifestError(
            f"Unknown top-level key: {sorted(unknown)[0]}"
        )
    version = raw.get("version")
    if (
        not isinstance(version, int)
        or isinstance(version, bool)
        or version != 1
    ):
        raise CapabilityManifestError(
            "Unsupported capability manifest version"
        )
    tools = _normalize_tools(_default_list(raw.get("tools")))
    network = _mapping_or_empty(raw.get("network"), "network")
    filesystem = _mapping_or_empty(raw.get("filesystem"), "filesystem")
    secrets = _mapping_or_empty(raw.get("secrets"), "secrets")
    human_approval = _mapping_or_empty(
        raw.get("human_approval"), "human_approval"
    )
    human_approval_required = human_approval.get("required", False)
    if not isinstance(human_approval_required, bool):
        raise CapabilityManifestError(
            "human_approval.required must be a boolean"
        )
    allow_domains = _normalize_domains(
        _default_list(network.get("allow_domains"))
    )
    return {
        "version": 1,
        "summary": raw.get("summary"),
        "tools": tools,
        "network": {"allow_domains": allow_domains},
        "filesystem": {
            "read": _normalize_paths(_default_list(filesystem.get("read"))),
            "write": _normalize_paths(_default_list(filesystem.get("write"))),
        },
        "secrets": {
            "env": _normalize_env(_default_list(secrets.get("env"))),
        },
        "human_approval": {
            "required": human_approval_required,
        },
    }


def summarize_capability_manifest(
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Return a human-oriented summary dict from a normalised manifest."""
    tools = manifest.get("tools") or []
    domains = manifest.get("network", {}).get("allow_domains") or []
    fs = manifest.get("filesystem", {})
    secrets = manifest.get("secrets", {})
    return {
        "tools": tools,
        "allows_shell": "terminal" in tools,
        "allows_network": (
            bool(domains) or "web" in tools or "browser" in tools
        ),
        "allowed_domains": domains,
        "filesystem_read": fs.get("read") or [],
        "filesystem_write": fs.get("write") or [],
        "secrets_env": secrets.get("env") or [],
        "human_approval_required": bool(
            manifest.get("human_approval", {}).get("required", False)
        ),
    }


# ---------------------------------------------------------------------------
# Internal normalisers
# ---------------------------------------------------------------------------


def _mapping_or_empty(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise CapabilityManifestError(f"{field_name} must be a mapping")
    return value


def _default_list(value: Any) -> Any:
    return [] if value is None else value


def _normalize_tools(tools: Any) -> list[str]:
    if not isinstance(tools, list):
        raise CapabilityManifestError("tools must be a list")
    result: list[str] = []
    for t in tools:
        if not isinstance(t, str):
            raise CapabilityManifestError(f"Invalid tool: {t!r}")
        if t not in ALLOWED_TOOLS:
            raise CapabilityManifestError(f"Unknown tool: {t!r}")
        result.append(t)
    return sorted(set(result))


def _normalize_domains(domains: Any) -> list[str]:
    if not isinstance(domains, list):
        raise CapabilityManifestError("allow_domains must be a list")
    result: list[str] = []
    for d in domains:
        if not isinstance(d, str):
            raise CapabilityManifestError(f"Invalid domain: {d!r}")
        if d == "*":
            raise CapabilityManifestError("Wildcard domain not allowed")
        if "://" in d:
            raise CapabilityManifestError(
                f"Domain must not include scheme: {d!r}"
            )
        result.append(d)
    return sorted(set(result))


def _normalize_paths(paths: Any) -> list[str]:
    if not isinstance(paths, list):
        raise CapabilityManifestError("Filesystem paths must be a list")
    result: list[str] = []
    for p in paths:
        if not isinstance(p, str):
            raise CapabilityManifestError(f"Invalid path: {p!r}")
        path = Path(p)
        if path.is_absolute():
            raise CapabilityManifestError(f"Absolute paths not allowed: {p!r}")
        if ".." in path.parts:
            raise CapabilityManifestError(f"Path traversal not allowed: {p!r}")
        result.append(p)
    return result


def _normalize_env(env_vars: Any) -> list[str]:
    if not isinstance(env_vars, list):
        raise CapabilityManifestError("env must be a list")
    result: list[str] = []
    for e in env_vars:
        if not isinstance(e, str):
            raise CapabilityManifestError(f"Invalid env var: {e!r}")
        if not ENV_RE.match(e):
            raise CapabilityManifestError(f"Invalid env var name: {e!r}")
        result.append(e)
    return sorted(set(result))
