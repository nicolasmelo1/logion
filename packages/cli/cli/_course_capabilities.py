# SPDX-License-Identifier: MIT
"""Local capability manifest validator for the Logion CLI.

Validates and normalizes ``course/capabilities.yaml`` WITHOUT calling the
API.  Rules mirror the server-side validation closely enough for
author feedback.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from cli._json import (
    JsonObject,
    JsonValue,
    child,
    children,
    elements,
    opt_str,
    strings,
)

CAPABILITY_MANIFEST_PATH = Path("course/capabilities.yaml")
ALLOWED_TOOLS = {"browser", "terminal", "file", "web", "vision"}
ENV_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
BIN_RE = re.compile(r"^[A-Za-z0-9._+-]+$")
OS_VALUES = {"linux", "macos", "windows"}
INSTALL_KINDS = {
    "uv",
    "npm",
    "pip",
    "brew",
    "apt",
    "go",
    "cargo",
    "external",
    "manual",
}
SOFTWARE_INSTALL_KINDS = {"external", "manual", "vendor", "unknown"}

_RUNTIME_WARNING_CODES = {
    "runtime_env_not_declared_as_secret",
    "runtime_declares_host_dependencies_without_terminal",
    "install_steps_without_human_approval",
    "install_steps_without_network_domains",
}


class CapabilityManifestError(ValueError):
    """Raised when a capability manifest fails validation."""


def load_and_validate_capability_manifest(
    bundle_dir: Path,
) -> JsonObject:
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
    raw: JsonObject,
) -> JsonObject:
    """Normalise and validate a raw parsed capability manifest."""
    unknown = set(raw) - {
        "version",
        "summary",
        "tools",
        "network",
        "filesystem",
        "secrets",
        "human_approval",
        "runtime",
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
    summary = raw.get("summary", "")
    if not isinstance(summary, str):
        raise CapabilityManifestError("summary must be a string")
    if len(summary) > 512:
        raise CapabilityManifestError("summary must be at most 512 characters")
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
    runtime = _normalize_runtime(raw.get("runtime"))
    return {
        "version": 1,
        "summary": summary,
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
        "runtime": runtime,
    }


def summarize_capability_manifest(
    manifest: JsonObject,
) -> JsonObject:
    """Return a human-oriented summary dict from a normalised manifest."""
    tools = elements(manifest, "tools")
    domains = strings(child(manifest, "network"), "allow_domains")
    fs = child(manifest, "filesystem")
    secrets = child(manifest, "secrets")
    runtime = child(manifest, "runtime")
    requires = child(runtime, "requires")
    install = children(runtime, "install")
    summary: JsonObject = {
        "tools": tools,
        "allows_shell": "terminal" in tools,
        "allows_network": (
            bool(domains) or "web" in tools or "browser" in tools
        ),
        "allowed_domains": domains,
        "filesystem_read": elements(fs, "read"),
        "filesystem_write": elements(fs, "write"),
        "secrets_env": elements(secrets, "env"),
        "human_approval_required": bool(
            child(manifest, "human_approval").get("required", False)
        ),
        "runtime_requires_env": elements(requires, "env"),
        "runtime_requires_bins": elements(requires, "bins"),
        "runtime_requires_any_bins": elements(requires, "any_bins"),
        "runtime_requires_config": elements(requires, "config"),
        "runtime_requires_os": elements(requires, "os"),
        "runtime_requires_software": elements(requires, "software"),
        "runtime_install": install,
    }
    warnings = runtime_requirement_warnings(manifest)
    summary["runtime_warning_codes"] = [
        opt_str(warning, "code", "") for warning in warnings
    ]
    summary["runtime_warnings"] = warnings
    return summary


# ---------------------------------------------------------------------------
# Internal normalisers
# ---------------------------------------------------------------------------


def _mapping_or_empty(value: JsonValue, field_name: str) -> JsonObject:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise CapabilityManifestError(f"{field_name} must be a mapping")
    return value


def _default_list(value: JsonValue) -> JsonValue:
    return [] if value is None else value


def _normalize_tools(tools: JsonValue) -> list[str]:
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


def _normalize_domains(domains: JsonValue) -> list[str]:
    if not isinstance(domains, list):
        raise CapabilityManifestError("allow_domains must be a list")
    result: list[str] = []
    for d in domains:
        if not isinstance(d, str):
            raise CapabilityManifestError(f"Invalid domain: {d!r}")
        if not d:
            raise CapabilityManifestError("Domain must not be empty")
        if d == "*":
            raise CapabilityManifestError("Wildcard domain not allowed")
        if "://" in d:
            raise CapabilityManifestError(
                f"Domain must not include scheme: {d!r}"
            )
        if "/" in d:
            raise CapabilityManifestError(
                f"Domain must not contain a slash path: {d!r}"
            )
        if d.strip() != d:
            raise CapabilityManifestError(
                "Domain must not contain leading/trailing whitespace"
            )
        result.append(d)
    return sorted(set(result))


def _normalize_paths(paths: JsonValue) -> list[str]:
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
    return sorted(set(result))


def _normalize_env(env_vars: JsonValue) -> list[str]:
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


# ---------------------------------------------------------------------------
# Runtime requirements normalisers
# ---------------------------------------------------------------------------


def _normalize_runtime(value: JsonValue) -> JsonObject:
    """Normalise the optional top-level ``runtime`` mapping.

    Defaults to an empty requires/install shape when absent.
    """
    if value is None:
        return {"requires": _empty_requires(), "install": []}
    if not isinstance(value, dict):
        raise CapabilityManifestError("runtime must be a mapping")
    unknown = set(value) - {"requires", "install"}
    if unknown:
        raise CapabilityManifestError(
            f"Unknown runtime key: {sorted(unknown)[0]}"
        )
    requires = _normalize_runtime_requires(value.get("requires"))
    install = _normalize_install(value.get("install"))
    return {"requires": requires, "install": install}


def _empty_requires() -> JsonObject:
    return {
        "env": [],
        "bins": [],
        "any_bins": [],
        "config": [],
        "os": [],
        "software": [],
    }


def _normalize_runtime_requires(value: JsonValue) -> JsonObject:
    if value is None:
        return _empty_requires()
    if not isinstance(value, dict):
        raise CapabilityManifestError("runtime.requires must be a mapping")
    unknown = set(value) - {
        "env",
        "bins",
        "any_bins",
        "config",
        "os",
        "software",
    }
    if unknown:
        raise CapabilityManifestError(
            f"Unknown runtime.requires key: {sorted(unknown)[0]}"
        )
    return {
        "env": _normalize_env(_default_list(value.get("env"))),
        "bins": _normalize_required_bins(_default_list(value.get("bins"))),
        "any_bins": _normalize_any_bins(_default_list(value.get("any_bins"))),
        "config": _normalize_paths(_default_list(value.get("config"))),
        "os": _normalize_os(_default_list(value.get("os"))),
        "software": _normalize_software(_default_list(value.get("software"))),
    }


def _normalize_required_bins(value: JsonValue) -> list[str]:
    if not isinstance(value, list):
        raise CapabilityManifestError("runtime.requires.bins must be a list")
    result: list[str] = []
    for b in value:
        if not isinstance(b, str):
            raise CapabilityManifestError(f"Invalid binary name: {b!r}")
        if not b:
            raise CapabilityManifestError("Binary name must not be empty")
        if not BIN_RE.match(b):
            raise CapabilityManifestError(
                f"Invalid binary name (slashes, spaces, "
                f"or shell metacharacters not allowed): {b!r}"
            )
        result.append(b)
    return sorted(set(result))


def _normalize_any_bins(value: JsonValue) -> list[list[str]]:
    if not isinstance(value, list):
        raise CapabilityManifestError(
            "runtime.requires.any_bins must be a list"
        )
    groups: list[list[str]] = []
    for group in value:
        if not isinstance(group, list):
            raise CapabilityManifestError(
                "runtime.requires.any_bins entries must be lists"
            )
        if not group:
            raise CapabilityManifestError(
                "runtime.requires.any_bins groups must not be empty"
            )
        normalised = _normalize_required_bins(group)
        groups.append(normalised)
    # Dedupe groups by their tuple representation, preserving order.
    seen: set[tuple[str, ...]] = set()
    deduped: list[list[str]] = []
    for g in groups:
        key = tuple(g)
        if key not in seen:
            seen.add(key)
            deduped.append(g)
    return deduped


def _normalize_os(value: JsonValue) -> list[str]:
    if not isinstance(value, list):
        raise CapabilityManifestError("runtime.requires.os must be a list")
    result: list[str] = []
    for o in value:
        if not isinstance(o, str):
            raise CapabilityManifestError(f"Invalid os value: {o!r}")
        if o not in OS_VALUES:
            raise CapabilityManifestError(
                f"Unknown os value: {o!r} (allowed: "
                f"{', '.join(sorted(OS_VALUES))})"
            )
        result.append(o)
    return sorted(set(result))


def _normalize_software(value: JsonValue) -> list[JsonObject]:
    if not isinstance(value, list):
        raise CapabilityManifestError(
            "runtime.requires.software must be a list"
        )
    result: list[JsonObject] = []
    for i, entry in enumerate(value):
        if not isinstance(entry, dict):
            raise CapabilityManifestError(
                f"runtime.requires.software[{i}] must be a mapping"
            )
        unknown = set(entry) - {"name", "required", "install", "notes"}
        if unknown:
            raise CapabilityManifestError(
                f"Unknown runtime.requires.software key: {sorted(unknown)[0]}"
            )
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise CapabilityManifestError(
                f"runtime.requires.software[{i}].name must be a non-empty "
                "string"
            )
        if len(name) > 120:
            raise CapabilityManifestError(
                f"runtime.requires.software[{i}].name must be at most 120 "
                "characters"
            )
        required = entry.get("required", True)
        if not isinstance(required, bool):
            raise CapabilityManifestError(
                f"runtime.requires.software[{i}].required must be a boolean"
            )
        install = entry.get("install", "external")
        if not isinstance(install, str):
            raise CapabilityManifestError(
                f"runtime.requires.software[{i}].install must be a string"
            )
        if install not in SOFTWARE_INSTALL_KINDS:
            raise CapabilityManifestError(
                f"Unknown software install kind: {install!r} (allowed: "
                f"{', '.join(sorted(SOFTWARE_INSTALL_KINDS))})"
            )
        notes = entry.get("notes", "")
        if not isinstance(notes, str):
            raise CapabilityManifestError(
                f"runtime.requires.software[{i}].notes must be a string"
            )
        if len(notes) > 512:
            raise CapabilityManifestError(
                f"runtime.requires.software[{i}].notes must be at most 512 "
                "characters"
            )
        result.append({
            "name": name,
            "required": required,
            "install": install,
            "notes": notes,
        })
    return result


def _normalize_install(value: JsonValue) -> list[JsonObject]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise CapabilityManifestError("runtime.install must be a list")
    result: list[JsonObject] = []
    for i, entry in enumerate(value):
        result.append(_normalize_install_entry(entry, i))
    return result


def _normalize_install_entry(entry: JsonValue, i: int) -> JsonObject:
    """Validate and normalise a single runtime.install entry."""
    if not isinstance(entry, dict):
        raise CapabilityManifestError(
            f"runtime.install[{i}] must be a mapping"
        )
    unknown = set(entry) - {"kind", "command", "required", "notes"}
    if unknown:
        raise CapabilityManifestError(
            f"Unknown runtime.install key: {sorted(unknown)[0]}"
        )
    kind = entry.get("kind")
    if not isinstance(kind, str):
        raise CapabilityManifestError(
            f"runtime.install[{i}].kind must be a string"
        )
    if kind not in INSTALL_KINDS:
        raise CapabilityManifestError(
            f"Unknown install kind: {kind!r} (allowed: "
            f"{', '.join(sorted(INSTALL_KINDS))})"
        )
    command = entry.get("command", "")
    if not isinstance(command, str):
        raise CapabilityManifestError(
            f"runtime.install[{i}].command must be a string"
        )
    if "\n" in command or "\r" in command:
        raise CapabilityManifestError(
            f"runtime.install[{i}].command must not contain newlines"
        )
    if len(command) > 240:
        raise CapabilityManifestError(
            f"runtime.install[{i}].command must be at most 240 characters"
        )
    required = entry.get("required", True)
    if not isinstance(required, bool):
        raise CapabilityManifestError(
            f"runtime.install[{i}].required must be a boolean"
        )
    notes = entry.get("notes", "")
    if not isinstance(notes, str):
        raise CapabilityManifestError(
            f"runtime.install[{i}].notes must be a string"
        )
    if len(notes) > 512:
        raise CapabilityManifestError(
            f"runtime.install[{i}].notes must be at most 512 characters"
        )
    return {
        "kind": kind,
        "command": command,
        "required": required,
        "notes": notes,
    }


def runtime_requirement_warnings(
    manifest: JsonObject,
) -> list[JsonObject]:
    """Derive cross-field warnings from a normalised manifest.

    Warnings are reviewer/author-facing disclosure only. They never become
    hard validation failures; ``runtime.requires`` lowers false rejections
    for legitimate external dependencies but must not hide behaviour that
    still needs the normal ``tools``/``secrets``/``filesystem``/
    ``network``/``human_approval`` declarations.
    """
    warnings: list[JsonObject] = []
    runtime = child(manifest, "runtime")
    requires = child(runtime, "requires")
    install = children(runtime, "install")
    secrets_env = set(strings(child(manifest, "secrets"), "env"))
    tools = elements(manifest, "tools")
    human_approval_required = bool(
        child(manifest, "human_approval").get("required", False)
    )
    domains = strings(child(manifest, "network"), "allow_domains")

    for env_name in elements(requires, "env"):
        if env_name not in secrets_env:
            warnings.append({
                "code": "runtime_env_not_declared_as_secret",
                "severity": "medium",
                "message": (
                    f"runtime.requires.env includes {env_name} but "
                    "secrets.env does not."
                ),
            })

    has_host_deps = bool(
        requires.get("bins") or requires.get("any_bins") or install
    )
    if has_host_deps and "terminal" not in tools:
        warnings.append({
            "code": "runtime_declares_host_dependencies_without_terminal",
            "severity": "low",
            "message": (
                "runtime declares host dependencies or install steps "
                "but 'terminal' is not in tools."
            ),
        })

    if install and not human_approval_required:
        warnings.append({
            "code": "install_steps_without_human_approval",
            "severity": "medium",
            "message": (
                "runtime.install is non-empty but "
                "human_approval.required is false."
            ),
        })

    network_kinds = {"uv", "npm", "pip", "brew", "apt", "go", "cargo"}
    install_kinds = {opt_str(step, "kind", "") for step in install}
    if install_kinds & network_kinds and not domains:
        warnings.append({
            "code": "install_steps_without_network_domains",
            "severity": "low",
            "message": (
                "runtime.install includes package-manager steps but no "
                "network allow_domains are declared."
            ),
        })

    return warnings
