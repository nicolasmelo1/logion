# SPDX-License-Identifier: MIT
"""Tests for SKILL.md frontmatter capability manifest extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from cli._course_capabilities import CapabilityManifestError
from cli.commands.courses.capability_frontmatter import (
    extract_logion_capabilities_from_skill,
)


def _write_skill(
    tmp_path: Path, frontmatter: str, body: str = "# Skill\n"
) -> Path:
    """Write a SKILL.md with YAML frontmatter and return its path."""
    skill = tmp_path / "SKILL.md"
    skill.write_text(f"---\n{frontmatter}---\n{body}", encoding="utf-8")
    return skill


class TestExtractFromMetadataLogion:
    def test_scaffold_from_skill_metadata_logion_writes_capabilities_yaml(
        self, tmp_path: Path
    ) -> None:
        """SKILL.md with metadata.logion containing a valid manifest."""
        skill = _write_skill(
            tmp_path,
            "metadata:\n"
            "  logion:\n"
            "    version: 1\n"
            '    summary: "A test skill manifest."\n'
            "    tools:\n"
            "      - file\n"
            "      - terminal\n",
        )
        manifest = extract_logion_capabilities_from_skill(skill)
        assert manifest is not None
        assert manifest["version"] == 1
        assert manifest["summary"] == "A test skill manifest."
        assert manifest["tools"] == ["file", "terminal"]

    def test_scaffold_from_skill_metadata_logion_capabilities_nested_shape(
        self, tmp_path: Path
    ) -> None:
        """SKILL.md with metadata.logion.capabilities nested shape."""
        skill = _write_skill(
            tmp_path,
            "metadata:\n"
            "  logion:\n"
            "    capabilities:\n"
            "      version: 1\n"
            '      summary: "Nested shape manifest."\n'
            "      tools:\n"
            "        - web\n",
        )
        manifest = extract_logion_capabilities_from_skill(skill)
        assert manifest is not None
        assert manifest["version"] == 1
        assert manifest["summary"] == "Nested shape manifest."
        assert manifest["tools"] == ["web"]


class TestExtractConflictAndError:
    def test_scaffold_from_skill_rejects_conflicting_logion_shapes(
        self, tmp_path: Path
    ) -> None:
        """Both direct and nested present should raise."""
        skill = _write_skill(
            tmp_path,
            "metadata:\n"
            "  logion:\n"
            "    version: 1\n"
            '    summary: "Direct."\n'
            "    capabilities:\n"
            "      version: 1\n"
            '      summary: "Nested."\n',
        )
        with pytest.raises(CapabilityManifestError, match="both"):
            extract_logion_capabilities_from_skill(skill)

    def test_scaffold_from_skill_no_metadata_logion_returns_none(
        self, tmp_path: Path
    ) -> None:
        """No metadata.logion section returns None."""
        skill = _write_skill(
            tmp_path,
            "metadata:\n  other:\n    key: value\n",
        )
        assert extract_logion_capabilities_from_skill(skill) is None

    def test_scaffold_from_skill_no_frontmatter_returns_none(
        self, tmp_path: Path
    ) -> None:
        """File without frontmatter returns None."""
        skill = tmp_path / "SKILL.md"
        skill.write_text(
            "# Just markdown, no frontmatter.\n\nSome content.\n",
            encoding="utf-8",
        )
        assert extract_logion_capabilities_from_skill(skill) is None

    def test_scaffold_from_skill_not_a_mapping_raises(
        self, tmp_path: Path
    ) -> None:
        """metadata.logion is a string should raise."""
        skill = _write_skill(
            tmp_path,
            "metadata:\n  logion: not-a-mapping\n",
        )
        with pytest.raises(CapabilityManifestError):
            extract_logion_capabilities_from_skill(skill)
