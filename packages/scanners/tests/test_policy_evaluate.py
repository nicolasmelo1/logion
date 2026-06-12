"""Tests for policy evaluation logic."""

from __future__ import annotations

from logion_scanners.models import (
    SCANNER_AGENT,
    SCANNER_OSV,
    SCANNER_TRIVY,
    ScannerFinding,
    ScannerResult,
    ScanPolicy,
)
from logion_scanners.policy import evaluate


def _policy(**overrides: object) -> ScanPolicy:
    defaults: dict[str, object] = {
        "policy_id": "test-v1",
        "policy_version": "1.0.0",
        "required_scanners": ("trivy", "osv_scanner", "agent_scanner"),
        "enabled_agent_checks": ("FileStructureCheck",),
        "blocking_severities": {
            "trivy": ("critical", "high"),
            "osv_scanner": ("critical", "high"),
            "agent_scanner": ("critical", "high"),
        },
        "max_bundle_size_mb": 100,
        "max_file_count": 500,
        "max_file_size_mb": 10,
        "scanner_timeout_seconds": 300,
        "block_on_scanner_unavailable": True,
    }
    defaults.update(overrides)
    return ScanPolicy(**defaults)  # type: ignore[arg-type]


class TestEvaluateBlockingSeverity:
    def test_critical_finding_blocks(self) -> None:
        results = [
            ScannerResult(
                layer=SCANNER_TRIVY,
                passed=False,
                findings=[
                    ScannerFinding(
                        layer=SCANNER_TRIVY,
                        severity="critical",
                        rule_id="TRIVY-CVE-2025-0001",
                        description="CVE in something",
                    )
                ],
            )
        ]
        decision = evaluate(_policy(), results)
        assert decision.allowed is False
        assert len(decision.blocking_findings) == 1

    def test_medium_finding_does_not_block(self) -> None:
        results = [
            ScannerResult(
                layer=SCANNER_TRIVY,
                passed=True,
                findings=[
                    ScannerFinding(
                        layer=SCANNER_TRIVY,
                        severity="medium",
                        rule_id="TRIVY-CVE-2025-0002",
                        description="Medium CVE",
                    )
                ],
            ),
            ScannerResult(
                layer=SCANNER_OSV,
                passed=True,
                findings=[],
            ),
            ScannerResult(
                layer=SCANNER_AGENT,
                passed=True,
                findings=[],
            ),
        ]
        decision = evaluate(_policy(), results)
        assert decision.allowed is True
        assert len(decision.blocking_findings) == 0

    def test_high_agent_finding_blocks(self) -> None:
        results = [
            ScannerResult(
                layer=SCANNER_AGENT,
                passed=False,
                findings=[
                    ScannerFinding(
                        layer=SCANNER_AGENT,
                        severity="high",
                        rule_id="AGENT-RUNTIME-INSTALL-NPM",
                        description="npm install",
                    )
                ],
            )
        ]
        decision = evaluate(_policy(), results)
        assert decision.allowed is False


class TestEvaluateMissingScanner:
    def test_missing_required_blocks(self) -> None:
        results = [
            ScannerResult(
                layer=SCANNER_AGENT,
                passed=True,
                findings=[],
            )
        ]
        # trivy and osv_scanner are missing
        decision = evaluate(_policy(), results)
        assert decision.allowed is False
        assert len(decision.reasons) >= 2

    def test_missing_required_no_block_when_configured(
        self,
    ) -> None:
        results = [
            ScannerResult(
                layer=SCANNER_AGENT,
                passed=True,
                findings=[],
            )
        ]
        decision = evaluate(
            _policy(block_on_scanner_unavailable=False), results
        )
        assert decision.allowed is True


class TestEvaluateEmptyResults:
    def test_empty_with_required_blocks(self) -> None:
        decision = evaluate(_policy(), [])
        assert decision.allowed is False

    def test_empty_no_required_allows(self) -> None:
        decision = evaluate(
            _policy(
                required_scanners=(),
                block_on_scanner_unavailable=False,
            ),
            [],
        )
        assert decision.allowed is True


class TestEvaluateErroredScanner:
    def test_errored_scanner_blocks(self) -> None:
        results = [
            ScannerResult(
                layer=SCANNER_TRIVY,
                passed=False,
                findings=[],
                error="Docker not available",
            ),
            ScannerResult(
                layer=SCANNER_AGENT,
                passed=True,
                findings=[],
            ),
        ]
        decision = evaluate(_policy(), results)
        assert decision.allowed is False
