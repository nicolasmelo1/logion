# SPDX-License-Identifier: MIT
"""Verify _version modules import and match pyproject.toml."""

from __future__ import annotations

import importlib
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

PACKAGES = {
    "logion-cli": (
        "cli._version",
        REPO_ROOT / "packages" / "cli" / "pyproject.toml",
    ),
    "logion-client": (
        "logion._version",
        REPO_ROOT / "packages" / "client" / "pyproject.toml",
    ),
    "logion-agent-companion": (
        "_version",
        REPO_ROOT / "packages" / "agent-companion" / "pyproject.toml",
    ),
}


@pytest.mark.parametrize(
    ("package_name", "info"),
    list(PACKAGES.items()),
    ids=list(PACKAGES.keys()),
)
def test_version_matches_pyproject(
    package_name: str,
    info: tuple[str, Path],
) -> None:
    # The companion _version.py lives at package root (not under a
    # namespace package), so importlib cannot find it without
    # sys.path adjustment.  We inject the directory when needed.
    version_module, pyproject_path = info
    companion_dir = str(pyproject_path.resolve().parent)
    _injected = False
    if package_name == "logion-agent-companion":
        sys.path.insert(0, companion_dir)
        _injected = True
    try:
        mod = importlib.import_module(version_module)
    finally:
        if _injected:
            sys.path.remove(companion_dir)
    version = mod.__version__
    assert isinstance(version, str)
    assert version, f"{package_name} __version__ is empty"

    with pyproject_path.open("rb") as f:
        pyproject_version = tomllib.load(f)["project"]["version"]
    assert version == pyproject_version, (
        f"{package_name}: _version.py={version!r} != "
        f"pyproject.toml={pyproject_version!r}"
    )


def test_cli_version_flag_prints_version() -> None:
    from cli.main import main

    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
