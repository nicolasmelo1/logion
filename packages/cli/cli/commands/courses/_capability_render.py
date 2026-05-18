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


def append_capability_summary_lines(
    lines: list[str],
    payload: dict[str, Any],
) -> None:
    """Append human-readable capability summary lines to *lines*."""
    _append_meta_fields(lines, payload)
    summary = payload.get("capabilities_summary")
    if summary:
        _append_summary_fields(lines, summary)
