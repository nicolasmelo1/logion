"""Upload handlers for courses commands."""

from __future__ import annotations

import argparse
import collections
import mimetypes
import sys
from pathlib import Path

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error, print_err, validate_uuid_id
from cli._output import emit, to_data
from cli.commands.courses._capability_render import (
    append_capability_summary_lines,
)


def _parse_upload_file_spec(spec: str) -> tuple[str, Path]:
    """Return ``(upload_path, file_path)`` from a ``--file`` argument."""
    if "=" not in spec:
        file_path = Path(spec)
        return (file_path.name, file_path)

    upload_path, file_path_str = spec.split("=", 1)
    if not upload_path.strip():
        raise ValueError("upload path before '=' must not be empty")
    return (upload_path, Path(file_path_str))


def _resolve_upload_files(
    file_specs: list[str],
) -> list[tuple[str, Path]] | None:
    resolved: list[tuple[str, Path]] = []
    for file_spec in file_specs:
        try:
            upload_path, path = _parse_upload_file_spec(file_spec)
        except ValueError as exc:
            print_err(f"Error: {exc}")
            return None
        if not path.is_file():
            print_err(f"file not found: {path}")
            return None
        resolved.append((upload_path, path))

    duplicates = [
        name
        for name, count in collections.Counter(
            upload_path for upload_path, _ in resolved
        ).items()
        if count > 1
    ]
    if duplicates:
        print_err(
            f"duplicate file names not allowed: {sorted(set(duplicates))}"
        )
        return None
    return resolved


def handle_uploads_create(args: argparse.Namespace) -> int:
    """Execute the courses uploads create command."""
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id
    if not args.files:
        print_err("Error: at least one --file is required")
        return 2

    resolved = _resolve_upload_files(args.files)
    if resolved is None:
        return 2

    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        files = [
            {
                "path": upload_path,
                "size_bytes": path.stat().st_size,
                "content_type": mimetypes.guess_type(str(path))[0]
                or "application/octet-stream",
            }
            for upload_path, path in resolved
        ]
        result = client.v1.courses.create_upload_session(
            course_id=args.course_id,
            files=files,
        )
        emit(result, json_output=config.json_output)
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()


def handle_uploads_complete(args: argparse.Namespace) -> int:
    """Execute the courses uploads complete command."""
    bad_id = validate_uuid_id(args.course_id, "COURSE_ID")
    if bad_id is not None:
        return bad_id
    bad_id = validate_uuid_id(args.version_id, "VERSION_ID")
    if bad_id is not None:
        return bad_id
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        result = client.v1.courses.complete_upload_session(
            course_id=args.course_id,
            version_id=args.version_id,
        )
        if config.json_output:
            emit(result, json_output=True)
        else:
            data = to_data(result)
            lines: list[str] = [
                f"version_id: {data['version_id']}",
                f"version_number: {data['version_number']}",
                f"status: {data['status']}",
            ]
            manifest_s3_key = data.get("manifest_s3_key")
            if manifest_s3_key:
                lines.append(f"manifest_s3_key: {manifest_s3_key}")
            content_hash = data.get("content_hash")
            if content_hash:
                lines.append(f"content_hash: {content_hash}")
            append_capability_summary_lines(lines, data)
            sys.stdout.write("\n".join(lines))
            sys.stdout.write("\n")
    except Exception as exc:
        return handle_error(exc)
    else:
        return 0
    finally:
        client.close()
