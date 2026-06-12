"""Conformance test: exact set of rule IDs per check class.

This is the behavioral lock — if a rule ID is added or removed
from any check, this test will fail and require an explicit
update, preventing accidental regressions.
"""

from __future__ import annotations

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


class TestRuleIdConformance:
    """Each check class must emit exactly the rule IDs listed here.

    Adding or removing a rule ID is a breaking behavioral change
    that requires updating this test AND the policy YAML.
    """

    def test_file_structure_rule_ids(self) -> None:
        assert (
            frozenset({
                "AGENT-NO-SKILL-MD",
                "AGENT-EXCESSIVE-FILE-COUNT",
                "AGENT-OVERSIZED-FILE",
            })
            == FileStructureCheck.EXPECTED_RULE_IDS
        )

    def test_file_type_rule_ids(self) -> None:
        assert (
            frozenset({
                "AGENT-BLOCKED-FILE-TYPE",
                "AGENT-SUSPICIOUS-FILE-TYPE",
            })
            == FileTypeCheck.EXPECTED_RULE_IDS
        )

    def test_dangerous_commands_rule_ids(self) -> None:
        assert (
            frozenset({
                "AGENT-DANGEROUS-RM-RF",
                "AGENT-REMOTE-PIPE-SHELL",
                "AGENT-SUDO-PRIVILEGE-ESCALATION",
                "AGENT-INSECURE-PERMISSIONS",
                "AGENT-FORK-BOMB",
                "AGENT-DD-DESTRUCTIVE",
            })
            == DangerousCommandsCheck.EXPECTED_RULE_IDS
        )

    def test_runtime_install_rule_ids(self) -> None:
        assert (
            frozenset({
                "AGENT-RUNTIME-INSTALL-APK",
                "AGENT-RUNTIME-INSTALL-APT",
                "AGENT-RUNTIME-INSTALL-BREW",
                "AGENT-RUNTIME-INSTALL-BUN",
                "AGENT-RUNTIME-INSTALL-CARGO",
                "AGENT-RUNTIME-INSTALL-CHOCO",
                "AGENT-RUNTIME-INSTALL-COMPOSER",
                "AGENT-RUNTIME-INSTALL-CONDA",
                "AGENT-RUNTIME-INSTALL-CPAN",
                "AGENT-RUNTIME-INSTALL-DENO",
                "AGENT-RUNTIME-INSTALL-DOTNET",
                "AGENT-RUNTIME-INSTALL-FLATPAK",
                "AGENT-RUNTIME-INSTALL-GEM",
                "AGENT-RUNTIME-INSTALL-GO",
                "AGENT-RUNTIME-INSTALL-NIX",
                "AGENT-RUNTIME-INSTALL-NPM",
                "AGENT-RUNTIME-INSTALL-NPX",
                "AGENT-RUNTIME-INSTALL-PACMAN",
                "AGENT-RUNTIME-INSTALL-PIP",
                "AGENT-RUNTIME-INSTALL-PIPX",
                "AGENT-RUNTIME-INSTALL-POETRY",
                "AGENT-RUNTIME-INSTALL-RPM",
                "AGENT-RUNTIME-INSTALL-SCOOP",
                "AGENT-RUNTIME-INSTALL-SNAP",
                "AGENT-RUNTIME-INSTALL-UV",
                "AGENT-RUNTIME-INSTALL-WINGET",
                "AGENT-RUNTIME-INSTALL-YARN-PNPM",
                "AGENT-RUNTIME-INSTALL-ZYPPER",
            })
            == RuntimeInstallAttemptCheck.EXPECTED_RULE_IDS
        )

    def test_secrets_detection_rule_ids(self) -> None:
        assert (
            frozenset({
                "AGENT-AWS-ACCESS-KEY",
                "AGENT-HARDCODED-API-KEY",
                "AGENT-PRIVATE-KEY-EXPOSED",
                "AGENT-GITHUB-TOKEN",
                "AGENT-DB-CONNECTION-STRING",
                "AGENT-SLACK-TOKEN",
                "AGENT-STRIPE-KEY",
                "AGENT-HARDCODED-SECRET",
            })
            == SecretsDetectionCheck.EXPECTED_RULE_IDS
        )

    def test_env_harvesting_rule_ids(self) -> None:
        assert (
            frozenset({
                "AGENT-ENV-HARVESTING",
            })
            == EnvHarvestingCheck.EXPECTED_RULE_IDS
        )

    def test_network_audit_rule_ids(self) -> None:
        assert (
            frozenset({
                "AGENT-SUSPICIOUS-TLD",
                "AGENT-SUSPICIOUS-ENDPOINT",
            })
            == NetworkAuditCheck.EXPECTED_RULE_IDS
        )

    def test_obfuscation_rule_ids(self) -> None:
        assert (
            frozenset({
                "AGENT-BASE64-PAYLOAD",
                "AGENT-EVAL-EXEC",
                "AGENT-DYNAMIC-IMPORT",
                "AGENT-HEX-ESCAPE-CHAIN",
                "AGENT-GETATTR-CONCAT",
                "AGENT-COMPILE-EXEC",
                "AGENT-CHR-CHAIN",
            })
            == ObfuscationCheck.EXPECTED_RULE_IDS
        )

    def test_prompt_injection_rule_ids(self) -> None:
        assert (
            frozenset({
                "AGENT-IGNORE-INSTRUCTIONS",
                "AGENT-ROLE-HIJACK",
                "AGENT-DISREGARD-INSTRUCTIONS",
                "AGENT-FORGET-INSTRUCTIONS",
                "AGENT-OVERRIDE-SAFETY",
                "AGENT-MARKDOWN-IMAGE-EXFIL",
                "AGENT-MARKDOWN-LINK-EXFIL",
                "AGENT-SYSTEM-PREFIX",
                "AGENT-DATA-EXFILTRATION-CMD",
            })
            == PromptInjectionCheck.EXPECTED_RULE_IDS
        )
