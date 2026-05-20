"""Capability evidence rendering for course-reviews CLI commands."""

from __future__ import annotations

from typing import Any


def append_review_capability_evidence_lines(
    lines: list[str],
    payload: dict[str, Any],
) -> None:
    """Append human-readable capability evidence lines to *lines*.

    Used by course-reviews get to render declared/observed/mismatch
    evidence in a readable format.
    """
    status = payload.get("capabilities_status")
    if status is not None:
        lines.append(f"capabilities_status: {status}")

    score = payload.get("capability_risk_score")
    if score is not None:
        lines.append(f"capability_risk_score: {score}")

    declared = payload.get("declared_capabilities")
    if declared:
        lines.append("declared_capabilities:")
        _append_declared_lines(lines, declared)

    observed = payload.get("observed_capabilities")
    if observed:
        lines.append("observed_capabilities:")
        _append_observed_lines(lines, observed)

    mismatches = payload.get("capability_mismatches")
    if mismatches:
        lines.append("capability_mismatches:")
        for m in mismatches:
            severity = m.get("severity", "unknown")
            code = m.get("code", "unknown")
            lines.append(f"  - {severity}: {code}")
            if "observed" in m:
                lines.append(f"    observed: {m['observed']}")
            if "declared" in m:
                lines.append(f"    declared: {m['declared']}")
            if "message" in m:
                lines.append(f"    message: {m['message']}")


def append_queue_capability_summary_lines(
    lines: list[str],
    item: dict[str, Any],
) -> None:
    """Append compact capability summary lines for queue list items.

    Only shows status, score, and mismatch count — never full payloads.
    """
    status = item.get("capabilities_status")
    if status is not None:
        lines.append(f"capabilities_status: {status}")

    score = item.get("capability_risk_score")
    if score is not None:
        lines.append(f"capability_risk_score: {score}")

    count = item.get("capability_mismatch_count")
    if count is not None:
        lines.append(f"capability_mismatch_count: {count}")


def _append_declared_lines(
    lines: list[str],
    declared: dict[str, Any],
) -> None:
    tools = declared.get("tools")
    if tools:
        lines.append(f"  tools: {', '.join(tools)}")

    network = declared.get("network")
    if network:
        domains = network.get("allow_domains")
        if domains:
            lines.append(f"  network.allow_domains: {', '.join(domains)}")

    filesystem = declared.get("filesystem")
    if filesystem:
        write_paths = filesystem.get("write")
        if write_paths:
            lines.append(f"  filesystem.write: {', '.join(write_paths)}")

    secrets = declared.get("secrets")
    if secrets:
        env_vars = secrets.get("env")
        if env_vars:
            lines.append(f"  secrets.env: {', '.join(env_vars)}")

    human_approval = declared.get("human_approval")
    if human_approval:
        required = human_approval.get("required")
        if required is not None:
            lines.append(f"  human_approval.required: {str(required).lower()}")


def _append_observed_lines(
    lines: list[str],
    observed: dict[str, Any],
) -> None:
    tools = observed.get("tools")
    if tools:
        lines.append(f"  tools: {', '.join(tools)}")

    hosts = observed.get("network_hosts")
    if hosts:
        lines.append(f"  network_hosts: {', '.join(hosts)}")

    fs_write = observed.get("filesystem_write")
    if fs_write:
        lines.append(f"  filesystem_write: {', '.join(fs_write)}")

    env_vars = observed.get("secrets_env")
    if env_vars:
        lines.append(f"  secrets_env: {', '.join(env_vars)}")

    dangerous = observed.get("dangerous_commands_detected")
    if dangerous is not None:
        lines.append(
            f"  dangerous_commands_detected: {str(dangerous).lower()}"
        )
