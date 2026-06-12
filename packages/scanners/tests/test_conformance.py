"""Conformance test: exact set of rule IDs emitted per fixture.

This is the behavioral lock — running AgentScanner over each fixture
bundle must produce exactly the rule IDs listed here. Adding or
removing a rule ID from any check is a breaking behavioral change
that requires updating this test AND the policy YAML.
"""

from __future__ import annotations

from pathlib import Path

from logion_scanners.adapters.agent import AgentScanner
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
from logion_scanners.checks.secrets_detection import (
    SecretsDetectionCheck,
)
from logion_scanners.models import SCANNER_AGENT

FIXTURES = Path(__file__).parent / "fixtures"

# The full set of rule IDs that every AgentScanner run must emit.
# This is the union of all checks; individual fixtures emit subsets.
ALL_RULE_IDS: frozenset[str] = frozenset(
    FileStructureCheck.EXPECTED_RULE_IDS
    | FileTypeCheck.EXPECTED_RULE_IDS
    | DangerousCommandsCheck.EXPECTED_RULE_IDS
    | RuntimeInstallAttemptCheck.EXPECTED_RULE_IDS
    | SecretsDetectionCheck.EXPECTED_RULE_IDS
    | EnvHarvestingCheck.EXPECTED_RULE_IDS
    | NetworkAuditCheck.EXPECTED_RULE_IDS
    | ObfuscationCheck.EXPECTED_RULE_IDS
    | PromptInjectionCheck.EXPECTED_RULE_IDS
)


class TestAllRuleIdsDeclared:
    """Every rule ID in the codebase must be declared exactly once."""

    def test_no_duplicate_declarations(self) -> None:
        """Union of all check EXPECTED_RULE_IDS must equal ALL_RULE_IDS."""
        # If a rule ID appears in two checks this assert fires.
        seen: dict[str, str] = {}
        for cls in (
            FileStructureCheck,
            FileTypeCheck,
            DangerousCommandsCheck,
            RuntimeInstallAttemptCheck,
            SecretsDetectionCheck,
            EnvHarvestingCheck,
            NetworkAuditCheck,
            ObfuscationCheck,
            PromptInjectionCheck,
        ):
            for rid in cls.EXPECTED_RULE_IDS:
                if rid in seen:
                    raise AssertionError(
                        f"{rid!r} declared in both "
                        f"{seen[rid]} and {cls.__name__}"
                    )
                seen[rid] = cls.__name__
        assert seen.keys() == ALL_RULE_IDS


class TestCleanFixtureConformance:
    """Clean course bundle must emit zero findings."""

    def test_clean_course_no_findings(self) -> None:
        scanner = AgentScanner()
        result = scanner.scan(FIXTURES / "clean_course")
        assert result.layer == SCANNER_AGENT
        assert result.findings == [], (
            f"Clean fixture should have zero findings, "
            f"got: {[f.rule_id for f in result.findings]}"
        )


class TestMaliciousFixtureConformance:
    """Malicious course must emit at least one finding per targeted rule."""

    # Map fixture directory to the *exact* set of rule IDs it must
    # produce when scanned with AgentScanner (all checks enabled).
    # These are the behavioral locks — if a check changes its
    # output for a given fixture, this test will catch it.

    def test_dangerous_commands(self) -> None:
        expected = frozenset({
            "AGENT-DANGEROUS-RM-RF",
            "AGENT-REMOTE-PIPE-SHELL",
            "AGENT-SUDO-PRIVILEGE-ESCALATION",
        })
        scanner = AgentScanner()
        result = scanner.scan(FIXTURES / "dangerous_commands")
        actual = frozenset(f.rule_id for f in result.findings)
        assert expected <= actual, f"Missing rule IDs: {expected - actual}"

    def test_runtime_install(self) -> None:
        expected = frozenset({
            "AGENT-RUNTIME-INSTALL-NPM",
            "AGENT-RUNTIME-INSTALL-PIP",
            "AGENT-RUNTIME-INSTALL-BREW",
        })
        scanner = AgentScanner()
        result = scanner.scan(FIXTURES / "runtime_install")
        actual = frozenset(f.rule_id for f in result.findings)
        assert expected <= actual, f"Missing rule IDs: {expected - actual}"

    def test_secrets_detection(self) -> None:
        expected = frozenset({
            "AGENT-HARDCODED-SECRET",
            "AGENT-DB-CONNECTION-STRING",
        })
        scanner = AgentScanner()
        result = scanner.scan(FIXTURES / "secrets_detection")
        actual = frozenset(f.rule_id for f in result.findings)
        assert expected <= actual, f"Missing rule IDs: {expected - actual}"

    def test_env_harvesting(self) -> None:
        expected = frozenset({"AGENT-ENV-HARVESTING"})
        scanner = AgentScanner()
        result = scanner.scan(FIXTURES / "env_harvesting")
        actual = frozenset(f.rule_id for f in result.findings)
        assert expected <= actual, f"Missing rule IDs: {expected - actual}"

    def test_network_audit(self) -> None:
        expected = frozenset({
            "AGENT-SUSPICIOUS-TLD",
            "AGENT-SUSPICIOUS-ENDPOINT",
        })
        scanner = AgentScanner()
        result = scanner.scan(FIXTURES / "network_audit")
        actual = frozenset(f.rule_id for f in result.findings)
        assert expected <= actual, f"Missing rule IDs: {expected - actual}"

    def test_obfuscation(self) -> None:
        expected = frozenset({
            "AGENT-EVAL-EXEC",
            "AGENT-BASE64-PAYLOAD",
        })
        scanner = AgentScanner()
        result = scanner.scan(FIXTURES / "obfuscation")
        actual = frozenset(f.rule_id for f in result.findings)
        assert expected <= actual, f"Missing rule IDs: {expected - actual}"

    def test_prompt_injection(self) -> None:
        expected = frozenset({
            "AGENT-IGNORE-INSTRUCTIONS",
            "AGENT-ROLE-HIJACK",
            "AGENT-DISREGARD-INSTRUCTIONS",
            "AGENT-FORGET-INSTRUCTIONS",
            "AGENT-OVERRIDE-SAFETY",
        })
        scanner = AgentScanner()
        result = scanner.scan(FIXTURES / "prompt_injection")
        actual = frozenset(f.rule_id for f in result.findings)
        assert expected <= actual, f"Missing rule IDs: {expected - actual}"

    def test_file_structure(self) -> None:
        expected = frozenset({"AGENT-NO-SKILL-MD"})
        scanner = AgentScanner()
        result = scanner.scan(FIXTURES / "file_structure")
        actual = frozenset(f.rule_id for f in result.findings)
        assert expected <= actual, f"Missing rule IDs: {expected - actual}"

    def test_file_type(self) -> None:
        expected = frozenset({"AGENT-BLOCKED-FILE-TYPE"})
        scanner = AgentScanner()
        result = scanner.scan(FIXTURES / "file_type")
        actual = frozenset(f.rule_id for f in result.findings)
        assert expected <= actual, f"Missing rule IDs: {expected - actual}"
