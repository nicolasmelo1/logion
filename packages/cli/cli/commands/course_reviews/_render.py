# SPDX-License-Identifier: MIT
"""Capability evidence rendering for course-reviews CLI commands."""

from __future__ import annotations

from cli._json import JsonObject, child, children, opt_str, strings


def append_review_capability_evidence_lines(
    lines: list[str],
    payload: JsonObject,
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

    declared = child(payload, "declared_capabilities")
    if declared:
        lines.append("declared_capabilities:")
        _append_declared_lines(lines, declared)

    observed = child(payload, "observed_capabilities")
    if observed:
        lines.append("observed_capabilities:")
        _append_observed_lines(lines, observed)

    mismatches = children(payload, "capability_mismatches")
    if mismatches:
        lines.append("capability_mismatches:")
        for m in mismatches:
            severity = opt_str(m, "severity", "unknown")
            code = opt_str(m, "code", "unknown")
            lines.append(f"  - {severity}: {code}")
            if "observed" in m:
                lines.append(f"    observed: {m['observed']}")
            if "declared" in m:
                lines.append(f"    declared: {m['declared']}")
            if "message" in m:
                lines.append(f"    message: {m['message']}")


def append_queue_capability_summary_lines(
    lines: list[str],
    item: JsonObject,
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
    declared: JsonObject,
) -> None:
    tools = strings(declared, "tools")
    if tools:
        lines.append(f"  tools: {', '.join(tools)}")

    network = child(declared, "network")
    if network:
        domains = strings(network, "allow_domains")
        if domains:
            lines.append(f"  network.allow_domains: {', '.join(domains)}")

    filesystem = child(declared, "filesystem")
    if filesystem:
        write_paths = strings(filesystem, "write")
        if write_paths:
            lines.append(f"  filesystem.write: {', '.join(write_paths)}")

    secrets = child(declared, "secrets")
    if secrets:
        env_vars = strings(secrets, "env")
        if env_vars:
            lines.append(f"  secrets.env: {', '.join(env_vars)}")

    human_approval = child(declared, "human_approval")
    if human_approval:
        required = human_approval.get("required")
        if required is not None:
            lines.append(f"  human_approval.required: {str(required).lower()}")


def _append_observed_lines(
    lines: list[str],
    observed: JsonObject,
) -> None:
    tools = strings(observed, "tools")
    if tools:
        lines.append(f"  tools: {', '.join(tools)}")

    hosts = strings(observed, "network_hosts")
    if hosts:
        lines.append(f"  network_hosts: {', '.join(hosts)}")

    fs_write = strings(observed, "filesystem_write")
    if fs_write:
        lines.append(f"  filesystem_write: {', '.join(fs_write)}")

    env_vars = strings(observed, "secrets_env")
    if env_vars:
        lines.append(f"  secrets_env: {', '.join(env_vars)}")

    dangerous = observed.get("dangerous_commands_detected")
    if dangerous is not None:
        lines.append(
            f"  dangerous_commands_detected: {str(dangerous).lower()}"
        )
