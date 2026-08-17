# SPDX-License-Identifier: MIT
"""Shared fixtures for CLI tests.

Every CLI test runs against a throwaway ``LOGION_HOME``. Without this a
test that exercises consent state, the observation spool, or a report
tombstone writes into the developer's real ``~/.logion`` — and then
leaks that state into the next test.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_logion_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Point ``LOGION_HOME`` at a per-test directory."""
    home = tmp_path / "logion_home"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LOGION_HOME", str(home))
    monkeypatch.delenv("DO_NOT_TRACK", raising=False)
    monkeypatch.delenv("LOGION_DO_NOT_TRACK", raising=False)
    return home
