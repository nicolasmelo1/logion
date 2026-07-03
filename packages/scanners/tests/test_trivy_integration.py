# SPDX-License-Identifier: MIT
"""Integration test: real Trivy container against the clean fixture."""

from __future__ import annotations

from pathlib import Path

import pytest

from logion_scanners.adapters.trivy import TrivyScanner
from logion_scanners.models import SCANNER_TRIVY

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.docker
def test_trivy_clean_course_passes() -> None:
    result = TrivyScanner().scan((FIXTURES / "clean_course").resolve())
    raw_output = result.raw_output or ""
    if result.error and "Docker daemon" in raw_output:
        pytest.skip("Docker daemon unavailable in this environment")
    assert result.layer == SCANNER_TRIVY
    assert result.error is None, f"Trivy errored: {result.error}"
    assert result.passed is True
    assert result.findings == []
