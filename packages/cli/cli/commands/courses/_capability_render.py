# SPDX-License-Identifier: MIT
"""Shared capability summary rendering for CLI commands."""

from __future__ import annotations

from typing import Any


def _append_meta_fields(
    lines: list[str],
    payload: dict[str, Any],
) -> None:
    """Append capability metadata fields."""
    status = payload.get("capabilities_status")
    if status:
        lines.append(f"capabilities_status: {status}")
    schema_version = payload.get("capabilities_schema_version")
    if schema_version is not None:
        lines.append(f"capabilities_schema_version: {schema_version}")
    manifest_path = payload.get("capabilities_manifest_path")
    if manifest_path is not None:
        lines.append(f"capabilities_manifest_path: {manifest_path}")


def _append_summary_fields(
    lines: list[str],
    summary: dict[str, Any],
) -> None:
    """Append capability summary detail fields (tools, permissions, paths)."""
    for tool in summary.get("tools") or []:
        lines.append(f"tools: {tool}")
    allows_shell = summary.get("allows_shell")
    if allows_shell is not None:
        lines.append(f"allows_shell: {str(allows_shell).lower()}")
    allows_network = summary.get("allows_network")
    if allows_network is not None:
        lines.append(f"allows_network: {str(allows_network).lower()}")
    for domain in summary.get("allowed_domains") or []:
        lines.append(f"allowed_domains: {domain}")
    for rpath in summary.get("filesystem_read") or []:
        lines.append(f"filesystem_read: {rpath}")
    for wpath in summary.get("filesystem_write") or []:
        lines.append(f"filesystem_write: {wpath}")
    for env_var in summary.get("secrets_env") or []:
        lines.append(f"secrets_env: {env_var}")
    human_approval = summary.get("human_approval_required")
    if human_approval is not None:
        lines.append(f"human_approval_required: {str(human_approval).lower()}")
    _append_runtime_fields(lines, summary)
    _append_runtime_warnings(lines, summary)


def _append_runtime_fields(
    lines: list[str],
    summary: dict[str, Any],
) -> None:
    """Append runtime requirement and install-step detail fields.

    Only rendered when any runtime field is non-empty, so minimal
    manifests stay compact.
    """
    env = summary.get("runtime_requires_env") or []
    bins = summary.get("runtime_requires_bins") or []
    any_bins = summary.get("runtime_requires_any_bins") or []
    config = summary.get("runtime_requires_config") or []
    os_vals = summary.get("runtime_requires_os") or []
    software = summary.get("runtime_requires_software") or []
    install = summary.get("runtime_install") or []
    if not any([env, bins, any_bins, config, os_vals, software, install]):
        return
    lines.append("runtime_requirements:")
    if env:
        lines.append(f"  env: {', '.join(env)}")
    if bins:
        lines.append(f"  bins: {', '.join(bins)}")
    if any_bins:
        groups = [" or ".join(g) for g in any_bins]
        lines.append(f"  any_bins: {', '.join(groups)}")
    if config:
        lines.append(f"  config: {', '.join(config)}")
    if os_vals:
        lines.append(f"  os: {', '.join(os_vals)}")
    if software:
        lines.append("  software:")
        for sw in software:
            req = "required" if sw.get("required") else "optional"
            install_kind = sw.get("install", "external")
            name = sw.get("name", "")
            notes = sw.get("notes", "")
            suffix = f": {notes}" if notes else ""
            lines.append(f"    - {name} ({install_kind}, {req}){suffix}")
    if install:
        lines.append("  install_steps:")
        for step in install:
            req = "required" if step.get("required") else "optional"
            kind = step.get("kind", "")
            command = step.get("command", "")
            notes = step.get("notes", "")
            cmd_part = f": {command}" if command else ""
            note_part = f": {notes}" if notes else ""
            lines.append(
                f"    - {kind}: {cmd_part} ({req}){note_part}".replace(
                    ":  ", ": "
                )
            )


def _append_runtime_warnings(
    lines: list[str],
    summary: dict[str, Any],
) -> None:
    """Append runtime cross-field warning codes."""
    codes = summary.get("runtime_warning_codes") or []
    if not codes:
        return
    lines.append("runtime_warnings:")
    for code in codes:
        lines.append(f"  - {code}")


def append_capability_summary_lines(
    lines: list[str],
    payload: dict[str, Any],
) -> None:
    """Append human-readable capability summary lines to *lines*."""
    _append_meta_fields(lines, payload)
    summary = payload.get("capabilities_summary")
    if summary:
        _append_summary_fields(lines, summary)


def append_approved_capability_summary_lines(
    lines: list[str],
    payload: dict[str, Any],
) -> None:
    """Append human-readable approved capability summary lines.

    Only renders the buyer-safe subset: tools, allows_shell,
    allows_network, allowed_domains, human_approval_required.
    Does not expose review-only evidence.
    """
    approved = payload.get("approved_capabilities_summary")
    if not approved or not isinstance(approved, dict):
        return
    lines.append("approved_capabilities_summary:")
    for tool in approved.get("tools") or []:
        lines.append(f"  tools: {tool}")
    allows_shell = approved.get("allows_shell")
    if allows_shell is not None:
        lines.append(f"  allows_shell: {str(allows_shell).lower()}")
    allows_network = approved.get("allows_network")
    if allows_network is not None:
        lines.append(f"  allows_network: {str(allows_network).lower()}")
    for domain in approved.get("allowed_domains") or []:
        lines.append(f"  allowed_domains: {domain}")
    human_approval = approved.get("human_approval_required")
    if human_approval is not None:
        val = str(human_approval).lower()
        lines.append(f"  human_approval_required: {val}")


def append_capability_feedback_lines(
    lines: list[str],
    payload: dict[str, Any],
) -> None:
    """Append human-readable capability feedback items."""
    feedback_items = payload.get("capability_feedback")
    if not feedback_items:
        return
    lines.append("capability_feedback:")
    for item in feedback_items:
        code = item.get("reason_code", "unknown")
        msg = item.get("message", "")
        lines.append(f"  - reason_code: {code}")
        if msg:
            lines.append(f"    message: {msg}")
        file_path = item.get("file_path")
        if file_path:
            lines.append(f"    file_path: {file_path}")
