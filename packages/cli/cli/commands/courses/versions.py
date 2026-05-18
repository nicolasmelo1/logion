"""Version handlers for courses commands."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error, validate_uuid_id
from cli._output import emit, to_data


def _append_capability_summary_lines(
    lines: list[str],
    payload: dict[str, Any],
) -> None:
    """Append human-readable capability summary lines to *lines*."""
    status = payload.get("capabilities_status")
    if status:
        lines.append(f"capabilities_status: {status}")
    schema_version = payload.get("capabilities_schema_version")
    if schema_version is not None:
        lines.append(f"capabilities_schema_version: {schema_version}")
    manifest_path = payload.get("capabilities_manifest_path")
    if manifest_path is not None:
        lines.append(f"capabilities_manifest_path: {manifest_path}")

    summary = payload.get("capabilities_summary")
    if summary:
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
            lines.append(
                f"human_approval_required: {str(human_approval).lower()}"
            )


def handle_versions_get(args: argparse.Namespace) -> int:
    """Execute the courses versions get command."""
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id
    bad_id = validate_uuid_id(args.version_id, "VERSION_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.courses.get_version(
            course_id=args.course_id,
            version_id=args.version_id,
        )
        if config.json_output:
            emit(result, json_output=True)
        else:
            data = to_data(result)
            lines: list[str] = [
                f"id: {data['id']}",
                f"course_id: {data['course_id']}",
                f"version_number: {data['version_number']}",
                f"status: {data['status']}",
            ]
            manifest_s3_key = data.get("manifest_s3_key")
            if manifest_s3_key:
                lines.append(f"manifest_s3_key: {manifest_s3_key}")
            content_hash = data.get("content_hash")
            if content_hash:
                lines.append(f"content_hash: {content_hash}")
            created_at = data.get("created_at")
            if created_at:
                lines.append(f"created_at: {created_at}")
            created_by = data.get("created_by_agent_id")
            if created_by:
                lines.append(f"created_by_agent_id: {created_by}")
            _append_capability_summary_lines(lines, data)
            sys.stdout.write("\n".join(lines))
            sys.stdout.write("\n")
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()
