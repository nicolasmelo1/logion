# SPDX-License-Identifier: MIT
"""Architectural constraints for CLI command modules."""

from __future__ import annotations

import ast
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


def _command_source_files() -> list[Path]:
    """Every command source file, packaged or flat.

    Flat modules are included deliberately. The size cap used to apply
    only to files inside a command package, so a command that had not
    been split yet was exempt from the very rule meant to make it split
    -- which is how bounties.py reached 670 lines.
    """
    files = [
        path
        for package in _command_packages()
        for path in package.rglob("*.py")
        if path.name != "__init__.py"
    ]
    files.extend(
        path
        for path in COMMANDS_DIR.glob("*.py")
        if path.name != "__init__.py"
    )
    return files


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


def test_top_level_command_imports_are_registered() -> None:
    """Every command imported by the parser must register its CLI surface."""
    parser_path = COMMANDS_DIR.parent / "_parser.py"
    tree = ast.parse(parser_path.read_text())
    imported: set[str] = set()
    registered: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "cli.commands":
            imported.update(alias.asname or alias.name for alias in node.names)
        if isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "register"
                and isinstance(func.value, ast.Name)
            ):
                registered.add(func.value.id)
    assert registered == imported


def test_command_source_files_stay_small() -> None:
    """Command modules must be split before files grow too large."""
    for file_path in _command_source_files():
        line_count = len(file_path.read_text().splitlines())
        relative = file_path.relative_to(COMMANDS_DIR)
        assert line_count <= MAX_SOURCE_LINES, (
            f"{relative} has {line_count} lines; "
            f"split it before it exceeds {MAX_SOURCE_LINES}."
        )
