"""Scanner data models and constants."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCANNER_TRIVY = "trivy"
SCANNER_OSV = "osv_scanner"
SCANNER_AGENT = "agent_scanner"


@dataclass
class ScannerFinding:
    """A single finding from a scanner layer."""

    layer: str  # "trivy" | "osv_scanner" | "agent_scanner"
    severity: str  # "critical" | "high" | "medium" | "low"
    rule_id: str
    description: str
    file_path: str | None = None
    line_number: int | None = None
    raw_output: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer": self.layer,
            "severity": self.severity,
            "rule_id": self.rule_id,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "raw_output": self.raw_output,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ScannerFinding:
        return cls(
            layer=d["layer"],
            severity=d["severity"],
            rule_id=d["rule_id"],
            description=d["description"],
            file_path=d.get("file_path"),
            line_number=d.get("line_number"),
            raw_output=d.get("raw_output"),
        )


@dataclass
class ScannerResult:
    """Aggregated result from a single scanner layer."""

    layer: str
    passed: bool
    findings: list[ScannerFinding] = field(default_factory=list)
    raw_output: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer": self.layer,
            "passed": self.passed,
            "findings": [f.to_dict() for f in self.findings],
            "raw_output": self.raw_output,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ScannerResult:
        return cls(
            layer=d["layer"],
            passed=d["passed"],
            findings=[
                ScannerFinding.from_dict(f) for f in d.get("findings", [])
            ],
            raw_output=d.get("raw_output"),
            error=d.get("error"),
        )


@dataclass(frozen=True)
class ScanPolicy:
    """Immutable policy controlling which scanners run and what blocks."""

    policy_id: str  # e.g. "publication-v1"
    policy_version: str  # e.g. "1.0.0"
    required_scanners: tuple[str, ...]
    enabled_agent_checks: tuple[str, ...]
    blocking_severities: dict[str, tuple[str, ...]]
    max_bundle_size_mb: int
    max_file_count: int
    max_file_size_mb: int
    scanner_timeout_seconds: int
    block_on_scanner_unavailable: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "required_scanners": list(self.required_scanners),
            "enabled_agent_checks": list(self.enabled_agent_checks),
            "blocking_severities": {
                k: list(v) for k, v in self.blocking_severities.items()
            },
            "max_bundle_size_mb": self.max_bundle_size_mb,
            "max_file_count": self.max_file_count,
            "max_file_size_mb": self.max_file_size_mb,
            "scanner_timeout_seconds": self.scanner_timeout_seconds,
            "block_on_scanner_unavailable": (
                self.block_on_scanner_unavailable
            ),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ScanPolicy:
        return cls(
            policy_id=d["policy_id"],
            policy_version=d["policy_version"],
            required_scanners=tuple(d["required_scanners"]),
            enabled_agent_checks=tuple(d["enabled_agent_checks"]),
            blocking_severities={
                k: tuple(v) for k, v in d["blocking_severities"].items()
            },
            max_bundle_size_mb=d["max_bundle_size_mb"],
            max_file_count=d["max_file_count"],
            max_file_size_mb=d["max_file_size_mb"],
            scanner_timeout_seconds=d["scanner_timeout_seconds"],
            block_on_scanner_unavailable=d["block_on_scanner_unavailable"],
        )


@dataclass(frozen=True)
class PolicyDecision:
    """Whether a scan result is allowed, with reasons if blocked."""

    allowed: bool
    blocking_findings: tuple[ScannerFinding, ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "blocking_findings": [f.to_dict() for f in self.blocking_findings],
            "reasons": list(self.reasons),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PolicyDecision:
        return cls(
            allowed=d["allowed"],
            blocking_findings=tuple(
                ScannerFinding.from_dict(f)
                for f in d.get("blocking_findings", [])
            ),
            reasons=tuple(d.get("reasons", [])),
        )


@dataclass
class ScanReport:
    """Full output of a scan run, suitable for JSON serialization."""

    schema_version: int  # 1
    bundle_hash: str
    policy_id: str
    policy_version: str
    policy_hash: str
    results: list[ScannerResult]
    execution_error: str | None
    decision: PolicyDecision

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "bundle_hash": self.bundle_hash,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_hash": self.policy_hash,
            "results": [r.to_dict() for r in self.results],
            "execution_error": self.execution_error,
            "decision": self.decision.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ScanReport:
        return cls(
            schema_version=d["schema_version"],
            bundle_hash=d["bundle_hash"],
            policy_id=d["policy_id"],
            policy_version=d["policy_version"],
            policy_hash=d["policy_hash"],
            results=[ScannerResult.from_dict(r) for r in d.get("results", [])],
            execution_error=d.get("execution_error"),
            decision=PolicyDecision.from_dict(d["decision"]),
        )
