"""Structural tests for the Logion Marketplace Companion.

Verifies the companion package has the required structure,
SKILL.md has valid frontmatter, referenced files exist, and
no banned content is present.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_DIRS = [
    "course",
    "references",
    "scripts",
    "tests",
    "templates",
    "vendor",
]

REQUIRED_FILES = [
    "SKILL.md",
    "course/capabilities.yaml",
    "README.md",
    "references/marketplace-flows.md",
    "references/creator-course-management.md",
    "references/safety-and-approval.md",
    "references/low-context-loading.md",
    "references/troubleshooting.md",
    "scripts/package_skill.py",
]

MAX_SKILL_SIZE_KB = 16

BANNED_BODY_TERMS = [
    "api_key",
    "apikey",
    "bearer ",
    "private_key",
    "sk-",
    "ghp_",
    "AKIA",
    "-----BEGIN",
]


class TestSkillStructure:
    """Verify the skill package has the required layout."""

    def test_required_directories_exist(self) -> None:
        for d in REQUIRED_DIRS:
            assert (ROOT / d).is_dir(), f"Missing directory: {d}/"

    def test_required_files_exist(self) -> None:
        for f in REQUIRED_FILES:
            assert (ROOT / f).is_file(), f"Missing file: {f}"

    def test_skill_md_has_frontmatter(self) -> None:
        content = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        assert content.startswith("---"), "SKILL.md missing frontmatter"
        lines = content.splitlines()
        end = None
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                end = i
                break
        assert end is not None, "SKILL.md frontmatter not closed"

    def test_skill_md_within_size_budget(self) -> None:
        content = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        size_kb = len(content.encode("utf-8")) / 1024
        assert size_kb <= MAX_SKILL_SIZE_KB, (
            f"SKILL.md is {size_kb:.1f}KB, "
            f"exceeds budget of {MAX_SKILL_SIZE_KB}KB"
        )

    def test_skill_md_no_banned_terms_in_body(self) -> None:
        content = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        lines = content.splitlines()
        end = None
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                end = i
                break
        body = "\n".join(lines[end + 1 :]) if end else content

        for term in BANNED_BODY_TERMS:
            assert term.lower() not in body.lower(), (
                f"SKILL.md body contains banned term: {term}"
            )

    def test_skill_md_frontmatter_has_required_fields(
        self,
    ) -> None:
        content = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        lines = content.splitlines()
        end = None
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                end = i
                break
        assert end is not None

        fm_text = "\n".join(lines[1:end])
        fm = yaml.safe_load(fm_text)

        for field in (
            "name",
            "version",
            "description",
            "required_tools",
            "safety",
        ):
            assert field in fm, f"SKILL.md frontmatter missing field: {field}"

        assert "requires_confirmation" in fm.get("safety", {}), (
            "SKILL.md frontmatter missing safety.requires_confirmation"
        )

    def test_skill_md_references_resolve(self) -> None:
        """Verify all file references in SKILL.md exist."""
        import re

        content = (ROOT / "SKILL.md").read_text(encoding="utf-8")

        # Extract backticked paths like `references/foo.md`
        # anywhere in a line (not just leading "- `...`")
        refs = re.findall(r"`(references/[^`]+)`", content)
        assert len(refs) > 0, (
            "SKILL.md should reference at least one file in references/"
        )
        for ref in refs:
            ref_path = ROOT / ref
            assert ref_path.is_file(), f"Referenced file missing: {ref}"

    def test_local_recall_guardrail_in_skill_md(self) -> None:
        """Verify SKILL.md mentions local recall as first guardrail."""
        content = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        # Find body (after closing frontmatter ---)
        lines = content.splitlines()
        end = None
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                end = i
                break
        body = (
            "\n".join(lines[end + 1 :]).lower()
            if end is not None
            else content.lower()
        )
        assert "local recall" in body, (
            "SKILL.md body does not mention local recall guardrail"
        )
        recall_pos = body.find("local recall")
        search_pos = body.find("marketplace search")
        if recall_pos >= 0 and search_pos >= 0:
            assert recall_pos < search_pos, (
                "Local recall should appear before "
                "marketplace search in the "
                "runtime policy"
            )
