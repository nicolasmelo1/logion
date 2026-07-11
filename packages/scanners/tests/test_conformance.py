"""Conformance test: exact set of rule IDs emitted per fixture.

This is the behavioral lock — running AgentScanner over each fixture
bundle must produce exactly the rule IDs listed here. Adding or
removing a rule ID from any check is a breaking behavioral change
that requires updating this test AND the policy YAML.
"""

from __future__ import annotations

from pathlib import Path

import pytest

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


# Map fixture directory -> the EXACT set of rule IDs AgentScanner
# (all checks enabled) must emit for it.  Equality, not subset: a new
# or renamed rule ID firing on these fixtures is a behavioral change
# and must be acknowledged here.
FIXTURE_RULE_IDS: dict[str, frozenset[str]] = {
    "clean_course": frozenset(),
    "dangerous_commands": frozenset({
        "AGENT-DANGEROUS-RM-RF",
        "AGENT-INSECURE-PERMISSIONS",
        "AGENT-REMOTE-PIPE-INTERPRETER",
        "AGENT-REMOTE-PIPE-SHELL",
        "AGENT-SUDO-PRIVILEGE-ESCALATION",
    }),
    "env_harvesting": frozenset({"AGENT-ENV-HARVESTING"}),
    "file_structure": frozenset({"AGENT-NO-SKILL-MD"}),
    "file_type": frozenset({"AGENT-BLOCKED-FILE-TYPE"}),
    "network_audit": frozenset({
        "AGENT-SUSPICIOUS-ENDPOINT",
        "AGENT-SUSPICIOUS-TLD",
    }),
    "obfuscation": frozenset({
        "AGENT-BASE64-PAYLOAD",
        "AGENT-EVAL-EXEC",
    }),
    "prompt_injection": frozenset({
        "AGENT-DISREGARD-INSTRUCTIONS",
        "AGENT-FORGET-INSTRUCTIONS",
        "AGENT-IGNORE-INSTRUCTIONS",
        "AGENT-OVERRIDE-SAFETY",
        "AGENT-ROLE-HIJACK",
    }),
    "runtime_install": frozenset({
        "AGENT-RUNTIME-INSTALL-BREW",
        "AGENT-RUNTIME-INSTALL-NPM",
        "AGENT-RUNTIME-INSTALL-PIP",
        "AGENT-RUNTIME-INSTALL-UV",
        "AGENT-RUNTIME-REMOTE-CODE-FETCH",
    }),
    "secrets_detection": frozenset({
        "AGENT-AWS-ACCESS-KEY",
        "AGENT-DB-CONNECTION-STRING",
        "AGENT-GITHUB-TOKEN",
        "AGENT-HARDCODED-API-KEY",
        "AGENT-HARDCODED-SECRET",
        "AGENT-STRIPE-KEY",
    }),
}


class TestFixtureConformance:
    """Behavioral lock: exact rule-ID set per fixture bundle."""

    @pytest.mark.parametrize(
        ("fixture", "expected"),
        sorted(FIXTURE_RULE_IDS.items()),
    )
    def test_exact_rule_ids(
        self,
        fixture: str,
        expected: frozenset[str],
    ) -> None:
        result = AgentScanner().scan(FIXTURES / fixture)
        assert result.layer == SCANNER_AGENT
        actual = frozenset(f.rule_id for f in result.findings)
        assert actual == expected, (
            f"{fixture}: unexpected={sorted(actual - expected)} "
            f"missing={sorted(expected - actual)}"
        )

    def test_every_fixture_dir_is_locked(self) -> None:
        """A new fixture dir must get an entry in FIXTURE_RULE_IDS."""
        on_disk = {d.name for d in FIXTURES.iterdir() if d.is_dir()}
        assert on_disk == FIXTURE_RULE_IDS.keys()
