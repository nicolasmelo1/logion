# SPDX-License-Identifier: MIT
"""Tests for the agent-companion course/capabilities.yaml manifest.

The only contract worth enforcing here is "the manifest parses and
validates against the same schema the Logion API enforces on
publish."  The exact set of declared env vars, network hosts, and
filesystem paths is a fast-moving editorial decision — let the
manifest evolve in place without re-touching the test file.
"""

from __future__ import annotations

from pathlib import Path

from cli._course_capabilities import load_and_validate_capability_manifest

ROOT = Path(__file__).resolve().parent.parent


def test_manifest_validates() -> None:
    """Must pass the same validator the CLI / marketplace API use."""
    manifest = load_and_validate_capability_manifest(ROOT)
    assert manifest["version"] == 1
    assert isinstance(manifest["summary"], str)
    assert manifest["summary"].strip()
