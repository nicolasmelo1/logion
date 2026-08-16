"""Scanner data models and constants."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict

from logion_scanners._json import (
    JsonObject,
    opt_int,
    opt_object_array,
    opt_str,
    opt_str_array,
    require_bool,
    require_int,
    require_object,
    require_str,
    require_str_array,
)

SCANNER_TRIVY = "trivy"
SCANNER_OSV = "osv_scanner"
SCANNER_AGENT = "agent_scanner"


class ScannerFindingDict(TypedDict):
    """Serialized :class:`ScannerFinding`."""

    layer: str
    severity: str
    rule_id: str
    description: str
    file_path: str | None
    line_number: int | None
    raw_output: str | None


class ScannerResultDict(TypedDict):
    """Serialized :class:`ScannerResult`."""

    layer: str
    passed: bool
    findings: list[ScannerFindingDict]
    raw_output: str | None
    error: str | None


class ScanPolicyDict(TypedDict):
    """Serialized :class:`ScanPolicy`."""

    policy_id: str
    policy_version: str
    required_scanners: list[str]
    enabled_agent_checks: list[str]
    blocking_severities: dict[str, list[str]]
    max_bundle_size_mb: int
    max_file_count: int
    max_file_size_mb: int
    scanner_timeout_seconds: int
    block_on_scanner_unavailable: bool


class PolicyDecisionDict(TypedDict):
    """Serialized :class:`PolicyDecision`."""

    allowed: bool
    blocking_findings: list[ScannerFindingDict]
    reasons: list[str]


class ScanReportDict(TypedDict):
    """Serialized :class:`ScanReport`."""

    schema_version: int
    bundle_hash: str
    policy_id: str
    policy_version: str
    policy_hash: str
    results: list[ScannerResultDict]
    execution_error: str | None
    decision: PolicyDecisionDict


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

    def to_dict(self) -> ScannerFindingDict:
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
    def from_dict(cls, d: JsonObject) -> ScannerFinding:
        return cls(
            layer=require_str(d, "layer"),
            severity=require_str(d, "severity"),
            rule_id=require_str(d, "rule_id"),
            description=require_str(d, "description"),
            file_path=opt_str(d, "file_path"),
            line_number=opt_int(d, "line_number"),
            raw_output=opt_str(d, "raw_output"),
        )


@dataclass
class ScannerResult:
    """Aggregated result from a single scanner layer."""

    layer: str
    passed: bool
    findings: list[ScannerFinding] = field(default_factory=list)
    raw_output: str | None = None
    error: str | None = None

    def to_dict(self) -> ScannerResultDict:
        return {
            "layer": self.layer,
            "passed": self.passed,
            "findings": [f.to_dict() for f in self.findings],
            "raw_output": self.raw_output,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, d: JsonObject) -> ScannerResult:
        return cls(
            layer=require_str(d, "layer"),
            passed=require_bool(d, "passed"),
            findings=[
                ScannerFinding.from_dict(f)
                for f in opt_object_array(d, "findings")
            ],
            raw_output=opt_str(d, "raw_output"),
            error=opt_str(d, "error"),
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

    def to_dict(self) -> ScanPolicyDict:
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
    def from_dict(cls, d: JsonObject) -> ScanPolicy:
        severities = require_object(d, "blocking_severities")
        return cls(
            policy_id=require_str(d, "policy_id"),
            policy_version=require_str(d, "policy_version"),
            required_scanners=tuple(require_str_array(d, "required_scanners")),
            enabled_agent_checks=tuple(
                require_str_array(d, "enabled_agent_checks")
            ),
            blocking_severities={
                key: tuple(require_str_array(severities, key))
                for key in severities
            },
            max_bundle_size_mb=require_int(d, "max_bundle_size_mb"),
            max_file_count=require_int(d, "max_file_count"),
            max_file_size_mb=require_int(d, "max_file_size_mb"),
            scanner_timeout_seconds=require_int(d, "scanner_timeout_seconds"),
            block_on_scanner_unavailable=require_bool(
                d, "block_on_scanner_unavailable"
            ),
        )


@dataclass(frozen=True)
class PolicyDecision:
    """Whether a scan result is allowed, with reasons if blocked."""

    allowed: bool
    blocking_findings: tuple[ScannerFinding, ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> PolicyDecisionDict:
        return {
            "allowed": self.allowed,
            "blocking_findings": [f.to_dict() for f in self.blocking_findings],
            "reasons": list(self.reasons),
        }

    @classmethod
    def from_dict(cls, d: JsonObject) -> PolicyDecision:
        return cls(
            allowed=require_bool(d, "allowed"),
            blocking_findings=tuple(
                ScannerFinding.from_dict(f)
                for f in opt_object_array(d, "blocking_findings")
            ),
            reasons=tuple(opt_str_array(d, "reasons")),
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

    def to_dict(self) -> ScanReportDict:
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
    def from_dict(cls, d: JsonObject) -> ScanReport:
        return cls(
            schema_version=require_int(d, "schema_version"),
            bundle_hash=require_str(d, "bundle_hash"),
            policy_id=require_str(d, "policy_id"),
            policy_version=require_str(d, "policy_version"),
            policy_hash=require_str(d, "policy_hash"),
            results=[
                ScannerResult.from_dict(r)
                for r in opt_object_array(d, "results")
            ],
            execution_error=opt_str(d, "execution_error"),
            decision=PolicyDecision.from_dict(require_object(d, "decision")),
        )
