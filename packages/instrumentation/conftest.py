# SPDX-License-Identifier: MIT
"""Conftest for instrumentation tests.

Adds the tests directory to sys.path so the conformance suite can
be imported as ``tests.conformance.suite``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))
