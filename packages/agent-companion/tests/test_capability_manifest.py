"""Tests for the agent-companion course/capabilities.yaml manifest.

Verifies the manifest is a valid canonical Logion capability manifest
(via the same validator the CLI and marketplace API use) and that the
companion-specific expectations are met.
"""

from __future__ import annotations

from pathlib import Path

from cli._course_capabilities import (
    ALLOWED_TOOLS,
    load_and_validate_capability_manifest,
)

ROOT = Path(__file__).resolve().parent.parent


class TestCanonicalManifest:
    """The manifest must pass the same validator the CLI/API use."""

    def test_manifest_validates(self) -> None:
        manifest = load_and_validate_capability_manifest(ROOT)
        assert manifest["version"] == 1

    def test_summary_is_nonempty(self) -> None:
        manifest = load_and_validate_capability_manifest(ROOT)
        assert manifest["summary"].strip() != ""

    def test_tools_are_subset_of_allowed_enum(self) -> None:
        manifest = load_and_validate_capability_manifest(ROOT)
        assert set(manifest["tools"]).issubset(ALLOWED_TOOLS)

    def test_companion_requires_terminal_and_file(self) -> None:
        manifest = load_and_validate_capability_manifest(ROOT)
        assert "terminal" in manifest["tools"]
        assert "file" in manifest["tools"]

    def test_no_network_by_default(self) -> None:
        """The companion does not call out — recall is offline."""
        manifest = load_and_validate_capability_manifest(ROOT)
        assert manifest["network"]["allow_domains"] == []

    def test_human_approval_required(self) -> None:
        """Companion guides paid/permission-expanding actions, so the
        author-side default is human_approval.required=true."""
        manifest = load_and_validate_capability_manifest(ROOT)
        assert manifest["human_approval"]["required"] is True

    def test_no_writable_filesystem_paths(self) -> None:
        manifest = load_and_validate_capability_manifest(ROOT)
        assert manifest["filesystem"]["write"] == []

    def test_no_environment_secrets(self) -> None:
        manifest = load_and_validate_capability_manifest(ROOT)
        assert manifest["secrets"]["env"] == []
