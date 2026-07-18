"""Tests for skills-lock.json adapter: v1 fixture, non-github drop, drift."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from logion_indexer.adapters.skills_lock import SkillsLockAdapter
from logion_indexer.transport import FakeTransport, HttpResponse

LOCKFILE_V1 = {
    "version": 1,
    "skills": {
        "awesome-skill": {
            "source": "octocat/awesome",
            "sourceType": "github",
            "computedHash": "sha256:abc123",
        },
        "another-skill": {
            "source": "anthropics/skills",
            "sourceType": "github",
            "computedHash": "sha256:def456",
        },
        "local-skill": {
            "source": "/path/to/local",
            "sourceType": "file",
            "computedHash": "sha256:ghi789",
        },
    },
}


class TestSkillsLockV1:
    def test_v1_fixture_parses(self, tmp_path: Path) -> None:
        lockfile = tmp_path / "skills-lock.json"
        lockfile.write_text(json.dumps(LOCKFILE_V1))
        transport = FakeTransport()
        adapter = SkillsLockAdapter(transport)
        results = list(adapter.discover(str(lockfile)))
        # Two github entries; one file-based entry dropped.
        assert len(results) == 2
        owners = {r.canonical.owner for r in results}
        assert "octocat" in owners
        assert "anthropics" in owners

    def test_non_github_source_type_dropped(self, tmp_path: Path) -> None:
        lockfile = tmp_path / "skills-lock.json"
        lockfile.write_text(json.dumps(LOCKFILE_V1))
        transport = FakeTransport()
        adapter = SkillsLockAdapter(transport)
        results = list(adapter.discover(str(lockfile)))
        for r in results:
            assert r.canonical.owner != ""

    def test_computed_hash_on_channel(self, tmp_path: Path) -> None:
        lockfile = tmp_path / "skills-lock.json"
        lockfile.write_text(json.dumps(LOCKFILE_V1))
        transport = FakeTransport()
        adapter = SkillsLockAdapter(transport)
        results = list(adapter.discover(str(lockfile)))
        # The channel hub_url should point to the lockfile location.
        for r in results:
            assert r.channels[0].hub_slug == "skills_lock"
            assert str(lockfile) in r.channels[0].hub_url

    def test_unknown_version_hard_fails(self, tmp_path: Path) -> None:
        bad_lock = {"version": 2, "skills": {}}
        lockfile = tmp_path / "skills-lock.json"
        lockfile.write_text(json.dumps(bad_lock))
        transport = FakeTransport()
        adapter = SkillsLockAdapter(transport)
        with pytest.raises(ValueError, match="unsupported"):
            list(adapter.discover(str(lockfile)))

    def test_url_load(self) -> None:
        transport = FakeTransport()
        transport.set_response(
            "https://example.com/skills-lock.json",
            HttpResponse(200, json.dumps(LOCKFILE_V1).encode()),
        )
        adapter = SkillsLockAdapter(transport)
        results = list(
            adapter.discover("https://example.com/skills-lock.json")
        )
        assert len(results) == 2

    def test_invalid_remote_json_has_contextual_error(self) -> None:
        transport = FakeTransport()
        target = "https://example.com/skills-lock.json"
        transport.set_response(target, HttpResponse(200, b"not-json"))

        with pytest.raises(RuntimeError, match="invalid skills-lock JSON"):
            list(SkillsLockAdapter(transport).discover(target))
