"""Structural tests for the Logion Marketplace Companion.

Verifies the companion package has the required structure,
SKILL.md has valid frontmatter, referenced files exist, and
no banned content is present.
"""

from __future__ import annotations

import re
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

MAX_SKILL_CHAR_BUDGET = 4608

REQUIRED_SKILL_SECTIONS = [
    "## When to use Logion",
    "## When not to use Logion",
    "## Decision tree",
    "## Local Recall Guardrail",
    "## Safe discovery commands",
    "## Course inspection checklist",
    "## Install/update approval rules",
    "## Context budget rules",
    "## Troubleshooting",
]

IMPLEMENTED_COMMANDS = {
    'logion listings search --query "video cuts" --limit 5',
    "logion courses get COURSE_ID",
    "logion courses versions get COURSE_ID VERSION_ID",
    "logion notifications unread-count",
    "logion notifications list --unread-only --limit 20",
}

PLANNED_COMMANDS = {
    'logion recall search "video cuts" --limit 5',
    'logion skills search "video cuts" --limit 5',
    "logion skills inspect COURSE_ID",
    "logion skills install COURSE_ID --version VERSION_ID",
    "logion skills installed",
    "logion skills updates",
    "logion skills update COURSE_ID",
}

REQUIRED_CONFIRMATION_ACTIONS = {
    "paid_checkout",
    "install_new_capability",
    "update_paid_capability",
    "permission_expansion",
    "publish_or_unpublish_course",
    "upload_new_course_version",
    "change_course_price",
}


def _read_skill() -> str:
    return (ROOT / "SKILL.md").read_text(encoding="utf-8")


def _skill_body(content: str) -> str:
    lines = content.splitlines()
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[i + 1 :])
    return content


def _bash_command_lines(content: str) -> list[str]:
    blocks = re.findall(r"```bash\n(.*?)```", content, flags=re.DOTALL)
    lines: list[str] = []
    for block in blocks:
        for raw_line in block.splitlines():
            line = raw_line.strip()
            if line:
                lines.append(line)
    return lines


def _split_command_line(line: str) -> tuple[str, str]:
    command, _, comment = line.partition("#")
    return command.rstrip(), comment.strip()


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
        content = _read_skill()
        char_count = len(content)
        assert char_count <= MAX_SKILL_CHAR_BUDGET, (
            f"SKILL.md is {char_count} chars, "
            f"exceeds budget of {MAX_SKILL_CHAR_BUDGET} chars"
        )

    def test_skill_md_no_banned_terms_in_body(self) -> None:
        body = _skill_body(_read_skill())

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

        required_tools = fm.get("required_tools")
        assert isinstance(required_tools, list), (
            "SKILL.md required_tools must be a list"
        )
        assert {"terminal", "file"}.issubset(set(required_tools)), (
            "SKILL.md required_tools missing required values"
        )

        required_env = fm.get("required_env")
        assert isinstance(required_env, list), (
            "SKILL.md required_env must be a list"
        )

        confirmation_actions = fm.get("safety", {}).get(
            "requires_confirmation"
        )
        assert isinstance(confirmation_actions, list), (
            "SKILL.md safety.requires_confirmation must be a list"
        )
        assert confirmation_actions, (
            "SKILL.md safety.requires_confirmation must not be empty"
        )
        assert REQUIRED_CONFIRMATION_ACTIONS.issubset(
            set(confirmation_actions)
        ), "SKILL.md safety.requires_confirmation missing required actions"

    def test_skill_md_references_resolve(self) -> None:
        """Verify all file references in SKILL.md exist."""
        content = _read_skill()

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
        body = _skill_body(_read_skill()).lower()
        assert "local recall" in body, (
            "SKILL.md body does not mention local recall guardrail"
        )
        recall_pos = body.find("local recall guardrail")
        search_pos = body.find("search logion only")
        if recall_pos >= 0 and search_pos >= 0:
            assert recall_pos < search_pos, (
                "Local recall should appear before "
                "marketplace search in the decision tree"
            )

    def test_decision_tree_prefers_existing_local_skill_or_tool(self) -> None:
        body = _skill_body(_read_skill()).lower()
        assert "existing local" in body
        assert "use that local path first" in body
        assert "skill/tool" in body or "skill or tool" in body

    def test_skill_md_has_required_sections(self) -> None:
        content = _read_skill()
        for section in REQUIRED_SKILL_SECTIONS:
            assert section in content, (
                f"SKILL.md missing required section: {section}"
            )

    def test_install_checkout_and_update_require_explicit_approval(
        self,
    ) -> None:
        body = _skill_body(_read_skill()).lower()
        assert "explicit user approval" in body
        assert "before install" in body
        assert "before any paid checkout" in body
        assert "before updates that change price" in body
        assert "permissions, required tools, or execution policy" in body

    def test_recall_examples_are_read_only_and_not_automatic(self) -> None:
        body = _skill_body(_read_skill()).lower()
        recall_command = (
            'logion recall search "video cuts" --limit 5  # planned/read-only'
        )
        assert recall_command in body
        assert "read-only" in body
        assert "do not execute automatically" in body or (
            "never implies automatic execution" in body
        )

    def test_skill_md_never_instructs_loading_full_marketplace(self) -> None:
        body = _skill_body(_read_skill()).lower()
        forbidden = [
            "load the full marketplace",
            "load the whole marketplace",
            "load the entire marketplace",
        ]
        for phrase in forbidden:
            assert phrase not in body, (
                "SKILL.md should never instruct the agent to "
                f"load the full marketplace: {phrase}"
            )

    def test_command_examples_are_present_and_tagged_correctly(self) -> None:
        content = _read_skill()
        command_lines = _bash_command_lines(content)
        parsed_commands = dict(
            _split_command_line(line) for line in command_lines
        )

        assert IMPLEMENTED_COMMANDS.issubset(parsed_commands), (
            "Missing one or more implemented command examples"
        )
        assert PLANNED_COMMANDS.issubset(parsed_commands), (
            "Missing one or more planned command examples"
        )

        recall_comment = parsed_commands[
            'logion recall search "video cuts" --limit 5'
        ]
        assert "planned/read-only" in recall_comment

        for command in PLANNED_COMMANDS - {
            'logion recall search "video cuts" --limit 5'
        }:
            assert "planned" in parsed_commands[command], (
                f"Planned command must be tagged as planned: {command}"
            )
