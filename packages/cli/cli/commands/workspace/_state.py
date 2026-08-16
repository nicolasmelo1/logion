# SPDX-License-Identifier: MIT
"""Workspace layout helpers: paths, atomic writes, timestamps."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from cli._errors import print_err
from cli._json import JsonObject


class UserError(Exception):
    """Raised when a local precondition is not met (e.g. dirty workspace)."""


def has_dirty_files(path: Path) -> bool:
    """Return ``True`` if *path* contains any regular files (recursively)."""
    return any(item.is_file() for item in path.rglob("*"))


def write_json_atomic(path: Path, data: JsonObject) -> None:
    """Write *data* as JSON to *path* atomically via a temp file.

    Uses a uniquely-named temp file in the same directory so that
    ``os.replace()`` is atomic on POSIX and overwrites on Windows.
    """
    import contextlib
    import os
    import tempfile

    data_str = json.dumps(data, indent=2, sort_keys=True)
    dir_path = path.parent
    dir_path.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_path)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(data_str)
        os.replace(tmp_path, str(path))
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def read_json(path: Path) -> JsonObject:
    """Read and parse a JSON file.

    Returns an empty dict when the file does not exist.
    Returns an empty dict and prints a warning when the file
    contains invalid JSON (corrupt state is treated as missing).
    """
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        print_err(f"Warning: {path} contains invalid JSON, resetting.")
        return {}
    if not isinstance(data, dict):
        print_err(f"Warning: {path} is not a JSON object, resetting.")
        return {}
    return data


def now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def resolve_workspace(workspace: str | None) -> Path:
    """Resolve the workspace root directory.

    If *workspace* is given (via ``--workspace``), use it directly.
    Otherwise default to ``.logion/bounty-workspace`` relative to cwd.
    """
    if workspace is not None:
        return Path(workspace).resolve()
    return (Path.cwd() / ".logion" / "bounty-workspace").resolve()


# ---------------------------------------------------------------------------
# Sub-command handlers
# ---------------------------------------------------------------------------
