# SPDX-License-Identifier: MIT
"""Course-bundle validation for upload-time CLI flows."""

from __future__ import annotations

import tempfile
from pathlib import Path

from cli._course_bundle import CourseBundleError, validate_course_bundle


def validate_bundle_files_for_upload(
    *,
    file_map: dict[str, Path],
    paid: bool,
) -> tuple[bool, str | None]:
    """Validate the local upload set as a publishable course bundle."""
    with tempfile.TemporaryDirectory() as tmp:
        bundle_dir = Path(tmp)
        for upload_path, local_path in file_map.items():
            target = bundle_dir / upload_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(local_path.read_bytes())
        try:
            validate_course_bundle(bundle_dir, paid=paid)
        except CourseBundleError as exc:
            return False, str(exc)
    return True, None
