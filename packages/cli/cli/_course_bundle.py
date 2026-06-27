# SPDX-License-Identifier: MIT
"""Validation helpers for publishable course bundles."""

from __future__ import annotations

from pathlib import Path

REQUIRED_BUNDLE_FILES = ("SKILL.md", "LICENSE", "course/capabilities.yaml")


class CourseBundleError(ValueError):
    """Raised when a bundle is missing publish-time metadata."""


def validate_course_bundle(bundle_dir: Path) -> None:
    """Require the bundle files Logion needs before publication/install."""
    missing = [
        name
        for name in REQUIRED_BUNDLE_FILES
        if not (bundle_dir / name).is_file()
    ]
    if missing:
        missing_csv = ", ".join(missing)
        raise CourseBundleError(
            "bundle is missing required file(s): "
            f"{missing_csv}. "
            "Every publishable course bundle must ship its own LICENSE file."
        )
    license_text = (bundle_dir / "LICENSE").read_text(encoding="utf-8").strip()
    if not license_text:
        raise CourseBundleError("LICENSE exists but is empty")
