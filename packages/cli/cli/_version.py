# SPDX-License-Identifier: MIT
"""Runtime-accessible package version.

The source of truth is the wheel's metadata; this module reads it
via importlib.metadata so editable installs and built wheels report
the same string. When the package is not installed (e.g. running
from a checkout without uv sync), falls back to reading
pyproject.toml directly.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    __version__: str = _pkg_version("logion-cli")
except PackageNotFoundError:  # local checkout / sdist
    import tomllib
    from pathlib import Path

    _pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with _pyproject.open("rb") as _f:
        __version__ = tomllib.load(_f)["project"]["version"]

__all__ = ["__version__"]
