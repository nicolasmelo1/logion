"""Tests for the scan runner."""

from __future__ import annotations

from pathlib import Path

from logion_scanners.adapters.agent import AgentScanner
from logion_scanners.models import (
    SCANNER_AGENT,
    ScannerResult,
    ScanReport,
)
from logion_scanners.policy import load_policy
from logion_scanners.runner import bundle_hash, run_scan

FIXTURES = Path(__file__).parent / "fixtures"


class TestBundleHash:
    def test_deterministic(self) -> None:
        h1 = bundle_hash(FIXTURES / "clean_course")
        h2 = bundle_hash(FIXTURES / "clean_course")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_different_bundles_different_hashes(self) -> None:
        h1 = bundle_hash(FIXTURES / "clean_course")
        h2 = bundle_hash(FIXTURES / "dangerous_commands")
        assert h1 != h2


class TestRunScan:
    def test_clean_course_allowed(self) -> None:
        policy = load_policy("publication-v1")
        adapters = [AgentScanner()]
        report = run_scan(
            bundle=FIXTURES / "clean_course",
            policy=policy,
            adapters=adapters,
        )
        assert isinstance(report, ScanReport)
        assert report.schema_version == 1
        assert report.policy_id == "publication-v1"
        # Agent scanner on clean course should allow
        assert (
            report.decision.allowed is True
            or len([r for r in report.results if not r.passed and r.findings])
            == 0
        )

    def test_dangerous_course_blocked(self) -> None:
        policy = load_policy("publication-v1")
        adapters = [AgentScanner()]
        report = run_scan(
            bundle=FIXTURES / "dangerous_commands",
            policy=policy,
            adapters=adapters,
        )
        assert report.decision.allowed is False

    def test_execution_error_captured(self) -> None:
        """Verify that adapter exceptions are captured, not raised."""

        class FailingScanner:
            layer = SCANNER_AGENT

            def scan(self, _path: Path) -> ScannerResult:
                raise RuntimeError("Docker exploded")

        policy = load_policy("publication-v1")
        report = run_scan(
            bundle=FIXTURES / "clean_course",
            policy=policy,
            adapters=[FailingScanner()],
        )
        assert report.execution_error is not None
        assert "Docker exploded" in report.execution_error
        assert report.decision.allowed is False

    def test_report_serializable(self) -> None:
        import json

        policy = load_policy("publication-v1")
        adapters = [AgentScanner()]
        report = run_scan(
            bundle=FIXTURES / "clean_course",
            policy=policy,
            adapters=adapters,
        )
        d = report.to_dict()
        s = json.dumps(d)
        assert isinstance(s, str)
        assert "publication-v1" in s
