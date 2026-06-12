"""Tests for the AgentScanner adapter."""

from __future__ import annotations

from pathlib import Path

from logion_scanners.adapters.agent import AgentScanner
from logion_scanners.models import SCANNER_AGENT

FIXTURES = Path(__file__).parent / "fixtures"


class TestAgentScanner:
    def test_clean_course_passes(self) -> None:
        scanner = AgentScanner()
        result = scanner.scan(FIXTURES / "clean_course")
        assert result.layer == SCANNER_AGENT
        # Clean course should pass (no critical/high findings)
        assert result.passed is True or len(result.findings) == 0

    def test_dangerous_commands_fails(self) -> None:
        scanner = AgentScanner()
        result = scanner.scan(FIXTURES / "dangerous_commands")
        assert result.layer == SCANNER_AGENT
        assert result.passed is False
        assert len(result.findings) > 0

    def test_runtime_install_fails(self) -> None:
        scanner = AgentScanner()
        result = scanner.scan(FIXTURES / "runtime_install")
        assert result.passed is False

    def test_secrets_detection_fails(self) -> None:
        scanner = AgentScanner()
        result = scanner.scan(FIXTURES / "secrets_detection")
        assert result.passed is False

    def test_env_harvesting_fails(self) -> None:
        scanner = AgentScanner()
        result = scanner.scan(FIXTURES / "env_harvesting")
        assert result.passed is False

    def test_network_audit_fails(self) -> None:
        scanner = AgentScanner()
        result = scanner.scan(FIXTURES / "network_audit")
        assert result.passed is False

    def test_obfuscation_fails(self) -> None:
        scanner = AgentScanner()
        result = scanner.scan(FIXTURES / "obfuscation")
        assert result.passed is False

    def test_prompt_injection_fails(self) -> None:
        scanner = AgentScanner()
        result = scanner.scan(FIXTURES / "prompt_injection")
        assert result.passed is False

    def test_file_type_blocked_fails(self) -> None:
        scanner = AgentScanner()
        result = scanner.scan(FIXTURES / "file_type")
        assert result.passed is False

    def test_file_structure_no_skill_md(self) -> None:
        scanner = AgentScanner()
        result = scanner.scan(FIXTURES / "file_structure")
        assert any(f.rule_id == "AGENT-NO-SKILL-MD" for f in result.findings)

    def test_enabled_checks_filtering(self) -> None:
        scanner = AgentScanner(enabled_checks=["FileStructureCheck"])
        result = scanner.scan(FIXTURES / "dangerous_commands")
        # Only file structure check runs — dangerous_commands
        # fixture has no SKILL.md issue relative to our fixture
        # so all findings should be from FileStructureCheck only
        assert all(
            f.rule_id.startswith("AGENT-NO-SKILL-MD")
            or f.rule_id.startswith("AGENT-EXCESSIVE-FILE-COUNT")
            or f.rule_id.startswith("AGENT-OVERSIZED-FILE")
            for f in result.findings
        )

    def test_unknown_check_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="Unknown check"):
            AgentScanner(enabled_checks=["NonexistentCheck"])

    def test_custom_limits(self) -> None:
        scanner = AgentScanner(max_file_count=1, max_file_size_mb=1)
        result = scanner.scan(FIXTURES / "clean_course")
        # clean_course has >1 file, so should flag excessive file count
        assert any(
            f.rule_id == "AGENT-EXCESSIVE-FILE-COUNT" for f in result.findings
        )
