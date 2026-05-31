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
]

REQUIRED_FILES = [
    "SKILL.md",
    "course/capabilities.yaml",
    "README.md",
    "references/creator-course-management.md",
    "references/account-and-identity.md",
    "references/notifications-and-reports.md",
    "references/payments-and-checkout.md",
    "references/bounties.md",
    "references/course-review-queue.md",
    "references/admin-operations.md",
    "references/troubleshooting.md",
    "scripts/package_skill.py",
]

MAX_SKILL_SIZE_BYTES = 16 * 1024

HELP_COMMANDS = {
    "logion --help",
    "logion health --help",
    "logion identity --help",
    "logion listings --help",
    "logion notifications --help",
    "logion courses --help",
    "logion courses versions --help",
    "logion payments --help",
    "logion reports --help",
    "logion course-reviews --help",
    "logion bounties --help",
    "LOGION_ENABLE_ADMIN=1 logion admin --help",
}

IMPLEMENTED_COMMANDS = {
    'logion listings search --query "video cuts" --limit 5',
    "logion courses get COURSE_ID",
    "logion courses versions get COURSE_ID VERSION_ID",
    "logion notifications unread-count",
    "logion notifications list --unread-only --limit 20",
    'logion recall search "video cuts" --limit 5',
    "logion skills installed",
    "logion skills inspect COURSE_ID",
    "logion skills updates",
    'logion skills search "video cuts" --limit 5',
    (
        "logion skills install --source ./BUNDLE "
        "--course-id COURSE_ID --version-id VERSION_ID"
    ),
    (
        "logion skills update COURSE_ID --version-id VERSION_ID "
        "--source ./BUNDLE"
    ),
    "logion recall record --id WORKFLOW_ID --title TITLE --command CMD",
    "logion courses capabilities scaffold --bundle-dir ./new-course",
    ("logion courses capabilities validate --bundle-dir ./new-course --json"),
    "logion courses create --title ... --slug ... --json",
    "logion courses update COURSE_ID --json",
    "logion courses reviews list COURSE_ID --limit 5",
    "logion courses reviews summary COURSE_ID",
    ("logion courses uploads create COURSE_ID --file ... --json"),
    (
        "logion courses uploads push COURSE_ID VERSION_ID "
        "--session-file session.json --file ... --json"
    ),
    "logion courses uploads complete COURSE_ID VERSION_ID --json",
    ("logion courses publication request COURSE_ID --json"),
    ("logion courses publication latest COURSE_ID --json"),
    ("logion courses feedback COURSE_ID --json"),
    "logion payments seller-readiness --json",
    "logion payments onboarding-link --json",
    ("logion courses capabilities print --bundle-dir ./new-course --json"),
}

PLANNED_COMMANDS: set[str] = set()

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
    blocks = re.findall(
        r"```bash[ \t]*\r?\n(.*?)```",
        content,
        flags=re.DOTALL,
    )
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
        size_bytes = len(content.encode("utf-8"))
        assert size_bytes <= MAX_SKILL_SIZE_BYTES, (
            f"SKILL.md is {size_bytes} bytes, "
            f"exceeds budget of {MAX_SKILL_SIZE_BYTES} bytes"
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
        assert "local path first" in body or "use that local" in body
        assert "skill/tool" in body or "skill or tool" in body

    def test_skill_md_exposes_cli_help_entrypoints(self) -> None:
        skill_commands = _bash_command_lines(_read_skill())
        parsed_commands = dict(
            _split_command_line(line) for line in skill_commands
        )
        assert HELP_COMMANDS.issubset(parsed_commands), (
            "SKILL.md must list CLI help entrypoints so the agent can explore "
            "the available Logion command surface"
        )
        admin_help = "LOGION_ENABLE_ADMIN=1 logion admin --help"
        assert "gated" in parsed_commands[admin_help]

    def test_install_checkout_and_update_require_explicit_approval(
        self,
    ) -> None:
        body = _skill_body(_read_skill()).lower()
        assert "explicit user approval" in body
        assert "install" in body
        assert "paid checkout" in body
        assert (
            "change price" in body
            or "change price," in body
            or "price," in body
        )
        assert "permissions" in body
        assert "required tools" in body
        assert "execution policy" in body

    def test_recall_examples_are_read_only_and_not_automatic(self) -> None:
        body = _skill_body(_read_skill()).lower()
        recall_command = (
            'logion recall search "video cuts" --limit 5  # read-only'
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
            "Missing one or more implemented command examples: "
            f"{sorted(IMPLEMENTED_COMMANDS - set(parsed_commands))}"
        )
        assert PLANNED_COMMANDS.issubset(parsed_commands), (
            "Missing one or more planned command examples: "
            f"{sorted(PLANNED_COMMANDS - set(parsed_commands))}"
        )

        recall_comment = parsed_commands[
            'logion recall search "video cuts" --limit 5'
        ]
        assert "read-only" in recall_comment, (
            "logion recall search must remain tagged read-only"
        )

        for command in PLANNED_COMMANDS:
            assert "planned" in parsed_commands[command], (
                f"Planned command must be tagged as planned: {command}"
            )
