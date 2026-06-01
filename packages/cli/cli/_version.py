# SPDX-License-Identifier: MIT
"""Dynamic CLI version from package metadata."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def get_cli_version() -> str:
    """Return the installed logion-cli version, or a fallback."""
    try:
        return version("logion-cli")
    except PackageNotFoundError:
        return "0.0.0+editable"
