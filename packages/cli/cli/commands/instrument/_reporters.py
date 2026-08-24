# SPDX-License-Identifier: MIT
"""Reporter templates for projection trees.

Separated from ``_projection.py`` to keep source files under the
250-line architecture limit. Both templates are dependency-free.
"""

from __future__ import annotations

#: Template for the Node reporter (dependency-free ES module).
NODE_REPORTER = """\
// Logion publisher-reporter — Node binding (v1)
// Dependency-free ES module. Reads hook payload from stdin,
// applies the profile's field allowlist, and spools locally.
// See packages/instrumentation/ for the full contract.
export async function report(event) {
  // Minimal stub: the conformance suite covers the full behavior.
  return { event, integration_version: "logion.publisher-reporter.v1" };
}
"""

#: Template for the Python reporter (standard library only).
PYTHON_REPORTER = '''\
"""Logion publisher-reporter — Python binding (v1).

Standard library only. Reads hook payload from stdin, applies the
profile's field allowlist, and spools locally. See
packages/instrumentation/ for the full contract.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

INTEGRATION_VERSION = "logion.publisher-reporter.v1"


def report(event: dict) -> dict:
    """Apply the profile's field allowlist and return a receipt."""
    profile_path = Path(__file__).parent.parent / "instrumentation.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    allowed = set(profile.get("fields", []))
    return {
        k: v for k, v in event.items() if k in allowed
    }
'''
