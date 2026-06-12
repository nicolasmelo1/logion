"""Tests for logion_scanners.models — round-trip and serialization."""

from __future__ import annotations

import json

from logion_scanners.models import (
    PolicyDecision,
    ScannerFinding,
    ScannerResult,
    ScanPolicy,
    ScanReport,
)


def _sample_finding() -> ScannerFinding:
    return ScannerFinding(
        layer="agent_scanner",
        severity="high",
        rule_id="AGENT-RUNTIME-INSTALL-NPM",
        description="Course attempts to install an npm package",
        file_path="setup.sh",
        line_number=3,
        raw_output=None,
    )


def _sample_result() -> ScannerResult:
    return ScannerResult(
        layer="agent_scanner",
        passed=False,
        findings=[_sample_finding()],
        raw_output=None,
        error=None,
    )


def _sample_policy() -> ScanPolicy:
    return ScanPolicy(
        policy_id="publication-v1",
        policy_version="1.0.0",
        required_scanners=("trivy", "osv_scanner", "agent_scanner"),
        enabled_agent_checks=("FileStructureCheck",),
        blocking_severities={
            "trivy": ("critical", "high"),
            "osv_scanner": ("critical", "high"),
            "agent_scanner": ("critical", "high"),
        },
        max_bundle_size_mb=100,
        max_file_count=500,
        max_file_size_mb=10,
        scanner_timeout_seconds=300,
        block_on_scanner_unavailable=True,
    )


class TestScannerFinding:
    def test_to_dict_round_trip(self) -> None:
        f = _sample_finding()
        d = f.to_dict()
        f2 = ScannerFinding.from_dict(d)
        assert f2.layer == f.layer
        assert f2.severity == f.severity
        assert f2.rule_id == f.rule_id
        assert f2.description == f.description
        assert f2.file_path == f.file_path
        assert f2.line_number == f.line_number
        assert f2.raw_output == f.raw_output

    def test_from_dict_ignores_extra_keys(self) -> None:
        d = _sample_finding().to_dict()
        d["extra"] = "ignored"
        f = ScannerFinding.from_dict(d)
        assert f.rule_id == "AGENT-RUNTIME-INSTALL-NPM"


class TestScannerResult:
    def test_to_dict_round_trip(self) -> None:
        r = _sample_result()
        d = r.to_dict()
        r2 = ScannerResult.from_dict(d)
        assert r2.layer == r.layer
        assert r2.passed is False
        assert len(r2.findings) == 1
        assert r2.findings[0].rule_id == "AGENT-RUNTIME-INSTALL-NPM"

    def test_json_serializable(self) -> None:
        r = _sample_result()
        d = r.to_dict()
        s = json.dumps(d)
        assert "agent_scanner" in s


class TestScanPolicy:
    def test_to_dict_round_trip(self) -> None:
        p = _sample_policy()
        d = p.to_dict()
        p2 = ScanPolicy.from_dict(d)
        assert p2.policy_id == p.policy_id
        assert p2.blocking_severities == p.blocking_severities
        assert p2.max_file_count == 500
        assert p2.block_on_scanner_unavailable is True

    def test_frozen(self) -> None:
        p = _sample_policy()
        try:
            p.policy_id = "mutated"  # type: ignore[misc]
            raise AssertionError("Should raise FrozenInstanceError")
        except AttributeError:
            pass


class TestPolicyDecision:
    def test_to_dict_round_trip(self) -> None:
        d = PolicyDecision(
            allowed=False,
            blocking_findings=(_sample_finding(),),
            reasons=("AGENT-RUNTIME-INSTALL-NPM: ...",),
        )
        j = d.to_dict()
        d2 = PolicyDecision.from_dict(j)
        assert d2.allowed is False
        assert len(d2.blocking_findings) == 1
        assert d2.reasons == ("AGENT-RUNTIME-INSTALL-NPM: ...",)


class TestScanReport:
    def test_to_dict_round_trip(self) -> None:
        report = ScanReport(
            schema_version=1,
            bundle_hash="abc123",
            policy_id="publication-v1",
            policy_version="1.0.0",
            policy_hash="def456",
            results=[_sample_result()],
            execution_error=None,
            decision=PolicyDecision(
                allowed=False,
                blocking_findings=(_sample_finding(),),
                reasons=("test reason",),
            ),
        )
        d = report.to_dict()
        r2 = ScanReport.from_dict(d)
        assert r2.schema_version == 1
        assert r2.bundle_hash == "abc123"
        assert r2.policy_id == "publication-v1"
        assert r2.decision.allowed is False
        assert len(r2.results) == 1

    def test_json_round_trip(self) -> None:
        report = ScanReport(
            schema_version=1,
            bundle_hash="abc123",
            policy_id="publication-v1",
            policy_version="1.0.0",
            policy_hash="def456",
            results=[],
            execution_error=None,
            decision=PolicyDecision(
                allowed=True,
                blocking_findings=(),
                reasons=(),
            ),
        )
        s = json.dumps(report.to_dict())
        d = json.loads(s)
        r2 = ScanReport.from_dict(d)
        assert r2.decision.allowed is True
