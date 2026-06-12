"""File type validation — no binaries/executables, allowed
extensions only."""

from __future__ import annotations

from pathlib import Path

from logion_scanners.checks.base import (
    BaseCheck,
    FileContent,
)
from logion_scanners.models import SCANNER_AGENT, ScannerFinding

_BLOCKED_EXTENSIONS: frozenset[str] = frozenset({
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bat",
    ".cmd",
    ".ps1",
    ".vbs",
    ".msi",
    ".com",
    ".scr",
    ".app",
    ".deb",
    ".rpm",
    ".iso",
    ".dmg",
})

_SUSPICIOUS_EXTENSIONS: frozenset[str] = frozenset({
    ".bin",
    ".dat",
    ".db",
    ".sqlite",
    ".pkl",
    ".pickle",
    ".npy",
    ".npz",
    ".pt",
    ".pth",
    ".onnx",
    ".h5",
    ".model",
})


class FileTypeCheck(BaseCheck):
    """Scan for blocked and suspicious file types."""

    EXPECTED_RULE_IDS: frozenset[str] = frozenset({
        "AGENT-BLOCKED-FILE-TYPE",
        "AGENT-SUSPICIOUS-FILE-TYPE",
    })

    name = "file-type"

    def run(
        self,
        bundle_path: Path,
        files: list[FileContent] | None = None,  # noqa: ARG002
    ) -> list[ScannerFinding]:
        findings: list[ScannerFinding] = []
        for p in bundle_path.rglob("*"):
            if not p.is_file():
                continue
            suffix = p.suffix.lower()
            rel = str(p.relative_to(bundle_path))

            if suffix in _BLOCKED_EXTENSIONS:
                findings.append(
                    ScannerFinding(
                        layer=SCANNER_AGENT,
                        severity="critical",
                        rule_id="AGENT-BLOCKED-FILE-TYPE",
                        description=(
                            f"Executable/binary file type "
                            f"{suffix} is not allowed: {rel}"
                        ),
                        file_path=rel,
                    )
                )
            elif suffix in _SUSPICIOUS_EXTENSIONS:
                findings.append(
                    ScannerFinding(
                        layer=SCANNER_AGENT,
                        severity="medium",
                        rule_id="AGENT-SUSPICIOUS-FILE-TYPE",
                        description=(f"Suspicious file type {suffix}: {rel}"),
                        file_path=rel,
                    )
                )

        return findings
