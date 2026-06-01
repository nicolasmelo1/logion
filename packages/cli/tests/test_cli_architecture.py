# SPDX-License-Identifier: MIT
"""Architectural constraints for CLI command modules."""

from __future__ import annotations

import importlib
from pathlib import Path

COMMANDS_DIR = Path(__file__).resolve().parent.parent / "cli" / "commands"
REQUIRED_FILES = {"__init__.py", "parser.py", "handlers.py"}
MAX_SOURCE_LINES = 250


def _command_packages() -> list[Path]:
    return [
        path
        for path in COMMANDS_DIR.iterdir()
        if path.is_dir() and not path.name.startswith("__")
    ]


def test_command_modules_use_package_layout() -> None:
    """Every CLI command must live in a package with a fixed layout."""
    package_names = set()

    for path in _command_packages():
        package_names.add(path.name)
        child_names = {
            child.name for child in path.iterdir() if child.is_file()
        }
        assert child_names >= REQUIRED_FILES, (
            f"{path.name} must contain {sorted(REQUIRED_FILES)}; "
            f"found {sorted(child_names)}"
        )

    assert package_names, "Expected at least one CLI command package."


def test_command_packages_export_register() -> None:
    """Each command package must expose a register() entrypoint."""
    for path in _command_packages():
        module = importlib.import_module(f"cli.commands.{path.name}")
        assert callable(getattr(module, "register", None)), (
            f"cli.commands.{path.name} must export register()"
        )


def test_command_package_source_files_stay_small() -> None:
    """Command packages must be split before files grow too large."""
    for path in _command_packages():
        for file_path in path.rglob("*.py"):
            if file_path.name == "__init__.py":
                continue
            line_count = len(file_path.read_text().splitlines())
            assert line_count <= MAX_SOURCE_LINES, (
                f"{path.name}/{file_path.name} has {line_count} lines; "
                f"split it before it exceeds {MAX_SOURCE_LINES}."
            )
