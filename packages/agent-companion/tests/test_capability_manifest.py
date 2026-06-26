# SPDX-License-Identifier: MIT
"""Tests for the agent-companion course/capabilities.yaml manifest.

The only contract worth enforcing here is "the manifest parses and
validates against the same schema the Logion API enforces on
publish."  The exact set of declared env vars, network hosts, and
filesystem paths is a fast-moving editorial decision — let the
manifest evolve in place without re-touching the test file.

Runtime requirements (bins, any_bins, os, install) are also validated
here because the companion dogfoods the runtime schema alongside the
core permission fields.
"""

from __future__ import annotations

from pathlib import Path

from cli._course_capabilities import (
    load_and_validate_capability_manifest,
    summarize_capability_manifest,
)

ROOT = Path(__file__).resolve().parent.parent


def test_manifest_validates() -> None:
    """Must pass the same validator the CLI / marketplace API use."""
    manifest = load_and_validate_capability_manifest(ROOT)
    assert manifest["version"] == 1
    assert isinstance(manifest["summary"], str)
    assert manifest["summary"].strip()


def test_manifest_has_runtime_requirements() -> None:
    """The companion declares runtime host dependencies."""
    manifest = load_and_validate_capability_manifest(ROOT)
    runtime = manifest["runtime"]
    requires = runtime["requires"]
    # The companion needs at least Python 3 and uv.
    assert "python3" in requires["bins"]
    assert "uv" in requires["bins"]
    # any_bins groups must be non-empty lists of valid binary names.
    for group in requires["any_bins"]:
        assert isinstance(group, list)
        assert len(group) >= 2
    # Install steps are disclosure-only metadata.
    assert len(runtime["install"]) >= 1
    for step in runtime["install"]:
        assert "kind" in step
        assert "command" in step


def test_summary_includes_runtime_fields() -> None:
    """summarize_capability_manifest surfaces runtime keys for companion."""
    manifest = load_and_validate_capability_manifest(ROOT)
    summary = summarize_capability_manifest(manifest)
    assert "runtime_requires_bins" in summary
    assert "runtime_install" in summary
    assert "runtime_warning_codes" in summary
