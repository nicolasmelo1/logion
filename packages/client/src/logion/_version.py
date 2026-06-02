# SPDX-License-Identifier: MIT
"""Runtime-accessible package version."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    __version__: str = _pkg_version("logion-client")
except PackageNotFoundError:  # local checkout / sdist
    import tomllib
    from pathlib import Path

    _pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    with _pyproject.open("rb") as _f:
        __version__ = tomllib.load(_f)["project"]["version"]

__all__ = ["__version__"]
