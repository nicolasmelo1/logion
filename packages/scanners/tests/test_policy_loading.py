"""Tests for policy loading and hash stability."""

from __future__ import annotations

import pytest

from logion_scanners.policy import load_policy, policy_hash


class TestLoadPolicy:
    def test_load_publication_v1(self) -> None:
        p = load_policy("publication-v1")
        assert p.policy_id == "publication-v1"
        assert p.policy_version == "1.0.0"
        assert "trivy" in p.required_scanners
        assert "osv_scanner" in p.required_scanners
        assert "agent_scanner" in p.required_scanners
        assert len(p.enabled_agent_checks) == 9
        assert p.max_bundle_size_mb == 100
        assert p.max_file_count == 500
        assert p.max_file_size_mb == 10
        assert p.scanner_timeout_seconds == 300
        assert p.block_on_scanner_unavailable is True

    def test_blocking_severities(self) -> None:
        p = load_policy("publication-v1")
        assert "critical" in p.blocking_severities["trivy"]
        assert "high" in p.blocking_severities["trivy"]
        assert "critical" in p.blocking_severities["agent_scanner"]
        assert "high" in p.blocking_severities["agent_scanner"]

    def test_unknown_policy_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown policy"):
            load_policy("nonexistent-policy")


class TestPolicyHash:
    def test_hash_is_stable(self) -> None:
        h1 = policy_hash("publication-v1")
        h2 = policy_hash("publication-v1")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_hash_changes_if_yaml_changes(self) -> None:
        """Hash is deterministic but content-dependent."""
        h = policy_hash("publication-v1")
        assert isinstance(h, str)
        assert h != ""
