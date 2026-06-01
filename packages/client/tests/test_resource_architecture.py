# SPDX-License-Identifier: MIT
"""Architectural constraints for manual v1 resource code."""

from __future__ import annotations

import ast
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src" / "logion"
RESOURCES_DIR = SRC_DIR / "v1" / "_resources"
MAX_RESOURCE_LINES = 250


def _manual_resource_files() -> list[Path]:
    return [
        path
        for path in RESOURCES_DIR.rglob("*.py")
        if "__pycache__" not in path.parts
    ]


def _imports_generated_operations(path: Path) -> bool:
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "logion.v1._generated"
            and any(alias.name == "operations" for alias in node.names)
        ):
            return True
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "logion.v1._generated.operations":
                    return True
    return False


def test_manual_resource_source_files_stay_small() -> None:
    """Manual resource files must stay small enough to remain navigable."""
    for path in _manual_resource_files():
        if path.name == "__init__.py":
            continue
        line_count = len(path.read_text().splitlines())
        assert line_count <= MAX_RESOURCE_LINES, (
            f"{path.relative_to(SRC_DIR)} has {line_count} lines; "
            f"split it before it exceeds {MAX_RESOURCE_LINES}."
        )


def test_generated_operations_imports_stay_in_resource_layer() -> None:
    """Only resource implementation files may import generated operations."""
    for path in SRC_DIR.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        if not _imports_generated_operations(path):
            continue
        assert path.is_relative_to(RESOURCES_DIR), (
            f"{path.relative_to(SRC_DIR)} imports generated operations "
            "outside the resource layer."
        )
