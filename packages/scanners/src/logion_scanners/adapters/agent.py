"""Custom scanner that inspects course bundles for
agent-specific security issues."""

from __future__ import annotations

from pathlib import Path

from logion_scanners.adapters.base import BaseScanner
from logion_scanners.checks.base import (
    BaseCheck,
    FileContent,
    collect_text_files,
)
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
from logion_scanners.models import SCANNER_AGENT, ScannerResult

# Check registry — only classes that implement BaseCheck are allowed.
CHECKS: list[type] = [
    FileStructureCheck,
    FileTypeCheck,
    DangerousCommandsCheck,
    RuntimeInstallAttemptCheck,
    SecretsDetectionCheck,
    EnvHarvestingCheck,
    NetworkAuditCheck,
    ObfuscationCheck,
    PromptInjectionCheck,
]

# Name -> class mapping for policy-driven enable/disable.
_CHECK_NAME_MAP: dict[str, type] = {cls.__name__: cls for cls in CHECKS}


class AgentScanner(BaseScanner):
    """Custom scanner that inspects course bundles for
    agent-specific security issues."""

    layer = SCANNER_AGENT

    def __init__(
        self,
        *,
        enabled_checks: list[str] | None = None,
        max_file_count: int = 500,
        max_file_size_mb: int = 10,
    ) -> None:
        """Initialize with optional check filtering and limits.

        Args:
            enabled_checks: Check class names to enable.
                None means all checks are enabled.
            max_file_count: Maximum number of files in a bundle.
            max_file_size_mb: Maximum file size in MB.
        """
        if enabled_checks is not None:
            unknown = set(enabled_checks) - set(_CHECK_NAME_MAP.keys())
            if unknown:
                raise ValueError(
                    f"Unknown check names: {sorted(unknown)}. "
                    f"Available: {sorted(_CHECK_NAME_MAP.keys())}"
                )
            self._check_classes = [_CHECK_NAME_MAP[n] for n in enabled_checks]
        else:
            self._check_classes = list(CHECKS)
        self._max_file_count = max_file_count
        self._max_file_size_mb = max_file_size_mb

    def scan(self, bundle_path: Path) -> ScannerResult:
        files: list[FileContent] = collect_text_files(bundle_path)

        all_findings = []

        for check_cls in self._check_classes:
            # FileStructureCheck accepts policy-driven limits
            if issubclass(check_cls, FileStructureCheck):
                inst: BaseCheck = FileStructureCheck(
                    max_file_count=self._max_file_count,
                    max_file_size_mb=self._max_file_size_mb,
                )
            else:
                inst = check_cls()  # type: ignore[assignment]
            findings = inst.run(bundle_path, files=files)
            all_findings.extend(findings)

        has_critical_or_high = any(
            f.severity in ("critical", "high") for f in all_findings
        )

        return ScannerResult(
            layer=SCANNER_AGENT,
            passed=not has_critical_or_high,
            findings=all_findings,
        )
