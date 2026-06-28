# SPDX-License-Identifier: MIT
"""Validation helpers for publishable course bundles."""

from __future__ import annotations

from pathlib import Path

REQUIRED_BUNDLE_FILES = ("SKILL.md", "LICENSE", "course/capabilities.yaml")
LOGION_STANDARD_COURSE_LICENSE_NAME = "Logion Standard Course License v1.0"


class CourseBundleError(ValueError):
    """Raised when a bundle is missing publish-time metadata."""


def read_bundle_license_text(bundle_dir: Path) -> str:
    """Return the stripped bundle LICENSE text."""
    return (bundle_dir / "LICENSE").read_text(encoding="utf-8").strip()


def is_logion_standard_course_license(license_text: str) -> bool:
    """Return whether *license_text* is the Logion paid-course license."""
    return LOGION_STANDARD_COURSE_LICENSE_NAME in license_text


def validate_course_bundle(bundle_dir: Path, *, paid: bool = False) -> None:
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
    license_text = read_bundle_license_text(bundle_dir)
    if not license_text:
        raise CourseBundleError("LICENSE exists but is empty")
    if paid and not is_logion_standard_course_license(license_text):
        raise CourseBundleError(
            "paid courses must ship the Logion Standard Course License v1.0"
        )
