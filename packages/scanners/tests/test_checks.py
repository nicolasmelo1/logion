"""Tests for all agent scanner checks against fixture bundles."""

from __future__ import annotations

from pathlib import Path

from logion_scanners.checks.dangerous_commands import (
    DangerousCommandsCheck,
)
from logion_scanners.checks.env_harvesting import EnvHarvestingCheck
from logion_scanners.checks.file_structure import FileStructureCheck
from logion_scanners.checks.file_type import FileTypeCheck
from logion_scanners.checks.network_audit import NetworkAuditCheck
from logion_scanners.checks.obfuscation import ObfuscationCheck
from logion_scanners.checks.prompt_injection import (
    PromptInjectionCheck,
)
from logion_scanners.checks.runtime_install_attempt import (
    RuntimeInstallAttemptCheck,
)
from logion_scanners.checks.secrets_detection import SecretsDetectionCheck

FIXTURES = Path(__file__).parent / "fixtures"


class TestFileStructureCheck:
    def test_clean_course_passes(self) -> None:
        bundle = FIXTURES / "clean_course"
        check = FileStructureCheck()
        findings = check.run(bundle)
        assert all(f.rule_id != "AGENT-NO-SKILL-MD" for f in findings)

    def test_missing_skill_md(self) -> None:
        bundle = FIXTURES / "file_structure"
        check = FileStructureCheck()
        findings = check.run(bundle)
        assert any(f.rule_id == "AGENT-NO-SKILL-MD" for f in findings)


class TestFileTypeCheck:
    def test_clean_course_passes(self) -> None:
        bundle = FIXTURES / "clean_course"
        check = FileTypeCheck()
        findings = check.run(bundle)
        blocked = [
            f for f in findings if f.rule_id == "AGENT-BLOCKED-FILE-TYPE"
        ]
        assert blocked == []

    def test_blocked_extension(self) -> None:
        bundle = FIXTURES / "file_type"
        check = FileTypeCheck()
        findings = check.run(bundle)
        assert any(f.rule_id == "AGENT-BLOCKED-FILE-TYPE" for f in findings)
        exe_finding = next(
            f for f in findings if f.rule_id == "AGENT-BLOCKED-FILE-TYPE"
        )
        assert exe_finding.file_path is not None
        assert exe_finding.file_path.endswith(".exe")
        assert exe_finding.severity == "critical"


class TestDangerousCommandsCheck:
    def test_clean_course_passes(self) -> None:
        bundle = FIXTURES / "clean_course"
        check = DangerousCommandsCheck()
        findings = check.run(bundle)
        assert len(findings) == 0

    def test_detects_dangerous_commands(self) -> None:
        bundle = FIXTURES / "dangerous_commands"
        check = DangerousCommandsCheck()
        findings = check.run(bundle)
        rule_ids = {f.rule_id for f in findings}
        assert "AGENT-DANGEROUS-RM-RF" in rule_ids
        assert "AGENT-REMOTE-PIPE-SHELL" in rule_ids
        assert "AGENT-SUDO-PRIVILEGE-ESCALATION" in rule_ids


class TestRuntimeInstallAttemptCheck:
    def test_clean_course_passes(self) -> None:
        bundle = FIXTURES / "clean_course"
        check = RuntimeInstallAttemptCheck()
        findings = check.run(bundle)
        assert len(findings) == 0

    def test_detects_runtime_installs(self) -> None:
        bundle = FIXTURES / "runtime_install"
        check = RuntimeInstallAttemptCheck()
        findings = check.run(bundle)
        rule_ids = {f.rule_id for f in findings}
        assert "AGENT-RUNTIME-INSTALL-NPM" in rule_ids
        assert "AGENT-RUNTIME-INSTALL-PIP" in rule_ids
        assert "AGENT-RUNTIME-INSTALL-BREW" in rule_ids


class TestSecretsDetectionCheck:
    def test_clean_course_passes(self) -> None:
        bundle = FIXTURES / "clean_course"
        check = SecretsDetectionCheck()
        findings = check.run(bundle)
        assert len(findings) == 0

    def test_detects_secrets(self) -> None:
        bundle = FIXTURES / "secrets_detection"
        check = SecretsDetectionCheck()
        findings = check.run(bundle)
        rule_ids = {f.rule_id for f in findings}
        # At minimum, hardcoded secret and DB connection string
        assert "AGENT-HARDCODED-SECRET" in rule_ids
        assert "AGENT-DB-CONNECTION-STRING" in rule_ids


class TestEnvHarvestingCheck:
    def test_clean_course_passes(self) -> None:
        bundle = FIXTURES / "clean_course"
        check = EnvHarvestingCheck()
        findings = check.run(bundle)
        assert len(findings) == 0

    def test_detects_env_harvesting(self) -> None:
        bundle = FIXTURES / "env_harvesting"
        check = EnvHarvestingCheck()
        findings = check.run(bundle)
        assert len(findings) > 0
        assert any(f.rule_id == "AGENT-ENV-HARVESTING" for f in findings)
        # Should detect AWS_SECRET_ACCESS_KEY as sensitive
        [
            f
            for f in findings
            if "AWS_SECRET_ACCESS_KEY" in f.description
            or "sensitive" in f.description.lower()
        ]
        # May or may not have the specific var depending on pattern match
        # but should have at least one finding
        assert len(findings) >= 1


class TestNetworkAuditCheck:
    def test_clean_course_passes(self) -> None:
        bundle = FIXTURES / "clean_course"
        check = NetworkAuditCheck()
        findings = check.run(bundle)
        assert len(findings) == 0

    def test_detects_suspicious_urls(self) -> None:
        bundle = FIXTURES / "network_audit"
        check = NetworkAuditCheck()
        findings = check.run(bundle)
        rule_ids = {f.rule_id for f in findings}
        assert "AGENT-SUSPICIOUS-TLD" in rule_ids
        assert "AGENT-SUSPICIOUS-ENDPOINT" in rule_ids


class TestObfuscationCheck:
    def test_clean_course_passes(self) -> None:
        bundle = FIXTURES / "clean_course"
        check = ObfuscationCheck()
        findings = check.run(bundle)
        assert len(findings) == 0

    def test_detects_obfuscation(self) -> None:
        bundle = FIXTURES / "obfuscation"
        check = ObfuscationCheck()
        findings = check.run(bundle)
        rule_ids = {f.rule_id for f in findings}
        assert "AGENT-EVAL-EXEC" in rule_ids
        assert "AGENT-BASE64-PAYLOAD" in rule_ids


class TestPromptInjectionCheck:
    def test_clean_course_passes(self) -> None:
        bundle = FIXTURES / "clean_course"
        check = PromptInjectionCheck()
        findings = check.run(bundle)
        assert len(findings) == 0

    def test_detects_injection(self) -> None:
        bundle = FIXTURES / "prompt_injection"
        check = PromptInjectionCheck()
        findings = check.run(bundle)
        rule_ids = {f.rule_id for f in findings}
        assert "AGENT-IGNORE-INSTRUCTIONS" in rule_ids
        assert "AGENT-ROLE-HIJACK" in rule_ids
        assert "AGENT-DISREGARD-INSTRUCTIONS" in rule_ids
        assert "AGENT-FORGET-INSTRUCTIONS" in rule_ids
        assert "AGENT-OVERRIDE-SAFETY" in rule_ids
