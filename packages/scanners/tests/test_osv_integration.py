# SPDX-License-Identifier: MIT
"""Integration test: real OSV scanner container against the clean fixture."""

from __future__ import annotations

from pathlib import Path

import pytest

from logion_scanners.adapters.osv import OsvScanner
from logion_scanners.models import SCANNER_OSV

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.docker
def test_osv_clean_course_passes() -> None:
    result = OsvScanner().scan((FIXTURES / "clean_course").resolve())
    assert result.layer == SCANNER_OSV
    assert result.error is None, f"OSV errored: {result.error}"
    assert result.passed is True
    assert result.findings == []
