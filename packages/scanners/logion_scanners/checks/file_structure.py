"""File structure validation — SKILL.md presence, file count,
oversized files."""

from __future__ import annotations

from pathlib import Path

from logion_scanners.checks.base import (
    BaseCheck,
    FileContent,
)
from logion_scanners.models import SCANNER_AGENT, ScannerFinding

# Default: 10 MB per file (overridden by ScanPolicy.max_file_size_mb)
_DEFAULT_MAX_FILE_BYTES = 10 * 1024 * 1024
# Default: 500 files (overridden by ScanPolicy.max_file_count)
_DEFAULT_MAX_FILE_COUNT = 500


class FileStructureCheck(BaseCheck):
    """Validate bundle file structure: SKILL.md, file count,
    and oversized files."""

    EXPECTED_RULE_IDS: frozenset[str] = frozenset({
        "AGENT-NO-SKILL-MD",
        "AGENT-EXCESSIVE-FILE-COUNT",
        "AGENT-OVERSIZED-FILE",
    })

    name = "file-structure"

    def __init__(
        self,
        *,
        max_file_count: int = _DEFAULT_MAX_FILE_COUNT,
        max_file_size_mb: int = 10,
    ) -> None:
        self._max_file_count = max_file_count
        self._max_file_bytes = max_file_size_mb * 1024 * 1024

    def run(
        self,
        bundle_path: Path,
        files: list[FileContent] | None = None,  # noqa: ARG002
    ) -> list[ScannerFinding]:
        findings: list[ScannerFinding] = []
        all_files = [p for p in bundle_path.rglob("*") if p.is_file()]

        has_skill_md = any(p.name.upper() == "SKILL.MD" for p in all_files)
        if not has_skill_md:
            findings.append(
                ScannerFinding(
                    layer=SCANNER_AGENT,
                    severity="medium",
                    rule_id="AGENT-NO-SKILL-MD",
                    description=(
                        "Course bundle does not contain a SKILL.md file"
                    ),
                )
            )

        if len(all_files) > self._max_file_count:
            findings.append(
                ScannerFinding(
                    layer=SCANNER_AGENT,
                    severity="high",
                    rule_id="AGENT-EXCESSIVE-FILE-COUNT",
                    description=(
                        f"Course bundle contains {len(all_files)} "
                        f"files, exceeding limit of "
                        f"{self._max_file_count}"
                    ),
                )
            )

        for f in all_files:
            size = f.stat().st_size
            if size > self._max_file_bytes:
                findings.append(
                    ScannerFinding(
                        layer=SCANNER_AGENT,
                        severity="medium",
                        rule_id="AGENT-OVERSIZED-FILE",
                        description=(
                            f"File {f.relative_to(bundle_path)} is "
                            f"{size} bytes, exceeding limit of "
                            f"{self._max_file_bytes} bytes"
                        ),
                        file_path=str(f.relative_to(bundle_path)),
                    )
                )

        return findings
