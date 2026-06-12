"""Pytest configuration for logion-scanners tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def clean_course(fixtures_dir: Path) -> Path:
    """Return the path to the clean course fixture."""
    return fixtures_dir / "clean_course"
