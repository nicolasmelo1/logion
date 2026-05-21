"""Tests for local_state module: layout, manifest, index, recall, lock,
workflows, and update policy.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from logion_agent_companion.local_state import (
    RECALL_FILENAME,
    acquire_lock,
    append_workflow,
    build_index,
    build_recall_entries,
    ensure_layout,
    is_locked,
    list_installed,
    read_index,
    read_lock,
    read_manifest,
    read_recall,
    read_workflows,
    release_lock,
    search_recall,
    sha256_of_files,
    validate_manifest,
    write_index,
    write_manifest,
    write_recall,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def home(tmp_path: Path) -> Path:
    """Provide an isolated LOGION_HOME."""
    return ensure_layout(tmp_path / "logion-test")


def _make_manifest(
    course_id: str = "weather.basic",
    version_id: str = "2026.05.20",
    title: str = "Weather Check Skill",
) -> dict:
    return {
        "course_id": course_id,
        "version_id": version_id,
        "title": title,
        "source": "logion",
        "installed_at": "2026-05-20T00:00:00Z",
        "price_cents_at_install": 0,
        "currency": "USD",
        "entrypoint": "SKILL.md",
        "capabilities": ["weather.current", "weather.forecast"],
        "required_tools": ["web"],
        "content_sha256": "abc123",
        "review_status": "approved",
    }


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


class TestLayout:
    def test_ensure_layout_creates_installed_dir(self, home: Path) -> None:
        assert (home / "installed").is_dir()

    def test_ensure_layout_idempotent(self, home: Path) -> None:
        result = ensure_layout(home)
        assert result == home
        assert (home / "installed").is_dir()

    def test_logion_home_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        custom = tmp_path / "custom-logion"
        custom.mkdir()
        monkeypatch.setenv("LOGION_HOME", str(custom))
        from logion_agent_companion.local_state import get_home

        assert get_home() == custom

    def test_default_home_without_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("LOGION_HOME", raising=False)
        from logion_agent_companion.local_state import (
            DEFAULT_HOME,
            get_home,
        )

        assert get_home() == DEFAULT_HOME


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


class TestManifest:
    def test_write_and_read_manifest(self, home: Path) -> None:
        m = _make_manifest()
        path = write_manifest(m, "weather.basic", "2026.05.20", home)
        assert path.is_file()
        result = read_manifest("weather.basic", "2026.05.20", home)
        assert result is not None
        assert result["course_id"] == "weather.basic"
        assert result["version_id"] == "2026.05.20"

    def test_read_manifest_missing(self, home: Path) -> None:
        result = read_manifest("nonexistent", "1.0", home)
        assert result is None

    def test_validate_manifest_valid(self) -> None:
        m = _make_manifest()
        errors = validate_manifest(m)
        assert errors == []

    def test_validate_manifest_missing_keys(self) -> None:
        errors = validate_manifest({})
        assert len(errors) > 0
        key_names = [e.split(": ")[1] for e in errors]
        assert "course_id" in key_names
        assert "version_id" in key_names
        assert "capabilities" in key_names

    def test_validate_manifest_wrong_types(self) -> None:
        m = _make_manifest()
        m["capabilities"] = "not-a-list"
        m["required_tools"] = 42
        errors = validate_manifest(m)
        assert any("capabilities must be a list" in e for e in errors)
        assert any("required_tools must be a list" in e for e in errors)

    def test_list_installed_empty(self, home: Path) -> None:
        result = list_installed(home)
        assert result == []

    def test_list_installed_multiple(self, home: Path) -> None:
        m1 = _make_manifest("a", "1.0")
        m2 = _make_manifest("b", "2.0")
        write_manifest(m1, "a", "1.0", home)
        write_manifest(m2, "b", "2.0", home)
        result = list_installed(home)
        assert len(result) == 2
        ids = {r["course_id"] for r in result}
        assert ids == {"a", "b"}

    def test_sha256_of_files(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("hello")
        f2.write_text("world")
        digest = sha256_of_files([f1, f2])
        assert isinstance(digest, str)
        assert len(digest) == 64


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------


class TestIndex:
    def test_build_and_write_index(self, home: Path) -> None:
        m = _make_manifest()
        write_manifest(m, "weather.basic", "2026.05.20", home)
        index = build_index(home)
        assert len(index) == 1
        assert index[0]["course_id"] == "weather.basic"
        assert index[0]["version_id"] == "2026.05.20"
        assert "capabilities" in index[0]
        assert "required_tools" in index[0]
        # no full skill body
        assert "content_sha256" not in index[0]
        assert "installed_at" not in index[0]

    def test_write_and_read_index(self, home: Path) -> None:
        data = [{"course_id": "x", "version_id": "1"}]
        write_index(data, home)
        result = read_index(home)
        assert len(result) == 1
        assert result[0]["course_id"] == "x"

    def test_read_index_missing(self, home: Path) -> None:
        result = read_index(home)
        assert result == []

    def test_index_is_compact(self, home: Path) -> None:
        m = _make_manifest()
        write_manifest(m, "weather.basic", "2026.05.20", home)
        index = build_index(home)
        entry = index[0]
        # index entry must not include full skill body
        for forbidden in ("content_sha256", "installed_at"):
            assert forbidden not in entry


# ---------------------------------------------------------------------------
# Recall
# ---------------------------------------------------------------------------


class TestRecall:
    def test_build_recall_entries(self, home: Path) -> None:
        m = _make_manifest()
        write_manifest(m, "weather.basic", "2026.05.20", home)
        entries = build_recall_entries(list_installed(home))
        assert len(entries) == 1
        e = entries[0]
        assert e["type"] == "installed_capability"
        assert e["id"] == "weather.basic"
        assert e["source"] == "installed_index"
        assert e["danger_flags"] == []

    def test_recall_with_workflows(self, home: Path) -> None:
        m = _make_manifest()
        write_manifest(m, "weather.basic", "2026.05.20", home)
        wf = [
            {
                "id": "verify-companion",
                "title": "Verify companion package",
                "commands": ["make verify"],
                "success_count": 5,
                "last_success_at": "2026-05-21T00:00:00Z",
                "confidence": 0.88,
            }
        ]
        entries = build_recall_entries(list_installed(home), workflows=wf)
        types = {e["type"] for e in entries}
        assert "installed_capability" in types
        assert "workflow" in types

    def test_recall_danger_flags(self) -> None:
        wf = [
            {
                "id": "dangerous-workflow",
                "title": "Force delete temp files",
                "commands": ["rm -rf /tmp/old", "sudo chmod 777 /tmp"],
                "success_count": 1,
                "last_success_at": "",
                "confidence": 0.5,
            }
        ]
        entries = build_recall_entries([], workflows=wf)
        assert len(entries) == 1
        assert len(entries[0]["danger_flags"]) > 0

    def test_write_and_read_recall(self, home: Path) -> None:
        entries = [
            {
                "type": "installed_capability",
                "id": "test",
                "title": "Test",
                "summary": "A test capability.",
                "confidence": 0.9,
                "source": "installed_index",
                "entrypoint": "installed/test/1.0/SKILL.md",
                "danger_flags": [],
            }
        ]
        write_recall(entries, home)
        result = read_recall(home)
        assert len(result) == 1
        assert result[0]["id"] == "test"

    def test_search_recall(self, home: Path) -> None:
        m = _make_manifest(title="Weather Check Skill")
        write_manifest(m, "weather.basic", "2026.05.20", home)
        entries = build_recall_entries(list_installed(home))
        write_recall(entries, home)

        results = search_recall("weather", home, limit=5)
        assert len(results) >= 1
        assert results[0]["id"] == "weather.basic"

    def test_search_recall_no_results(self, home: Path) -> None:
        write_recall([], home)
        results = search_recall("nonexistent", home)
        assert results == []

    def test_recall_masks_secrets_in_entries(self, home: Path) -> None:
        """Recall entries must not contain full command outputs or
        secrets."""
        entries = [
            {
                "type": "installed_capability",
                "id": "safe.skill",
                "title": "Safe Skill",
                "summary": "Does safe things.",
                "confidence": 0.91,
                "source": "installed_index",
                "entrypoint": "installed/safe.skill/1.0/SKILL.md",
                "danger_flags": [],
            }
        ]
        write_recall(entries, home)
        data = json.loads((home / RECALL_FILENAME).read_text(encoding="utf-8"))
        for entry in data:
            # must not contain secrets or full skill bodies
            for forbidden in (
                "api_key",
                "bearer ",
                "password",
                "secret",
                "content_sha256",
            ):
                entry_str = json.dumps(entry).lower()
                assert forbidden not in entry_str, (
                    f"Recall entry contains forbidden term: {forbidden}"
                )


# ---------------------------------------------------------------------------
# Lockfile
# ---------------------------------------------------------------------------


class TestLock:
    def test_acquire_and_release(self, home: Path) -> None:
        path = acquire_lock("test", "1.0", home)
        assert path.is_file()
        assert is_locked(home)
        lock_data = read_lock(home)
        assert lock_data is not None
        assert lock_data["course_id"] == "test"
        release_lock(home)
        assert not is_locked(home)

    def test_read_lock_missing(self, home: Path) -> None:
        assert read_lock(home) is None
        assert not is_locked(home)

    def test_release_lock_when_none(self, home: Path) -> None:
        assert release_lock(home) is False


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------


class TestWorkflows:
    def test_read_workflows_empty(self, home: Path) -> None:
        result = read_workflows(home)
        assert result == []

    def test_append_workflow(self, home: Path) -> None:
        wf = {
            "id": "test-wf",
            "title": "Test Workflow",
            "commands": ["echo hello"],
            "success_count": 3,
            "last_success_at": "2026-05-20T00:00:00Z",
        }
        path = append_workflow(wf, home)
        assert path.is_file()
        result = read_workflows(home)
        assert len(result) == 1
        assert result[0]["id"] == "test-wf"

    def test_append_multiple_workflows(self, home: Path) -> None:
        for i in range(3):
            append_workflow(
                {"id": f"wf-{i}", "title": f"Workflow {i}"},
                home,
            )
        result = read_workflows(home)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# Update policy (from check_updates)
# ---------------------------------------------------------------------------


class TestUpdatePolicy:
    def test_no_approval_needed_when_unchanged(
        self,
    ) -> None:
        from scripts.check_updates import check_update_policy

        m = _make_manifest()
        result = check_update_policy(m, m)
        assert result["requires_approval"] is False
        assert result["reasons"] == []

    def test_approval_needed_when_content_changes(
        self,
    ) -> None:
        from scripts.check_updates import check_update_policy

        old = _make_manifest()
        new = {**old, "content_sha256": "different_hash"}
        result = check_update_policy(old, new)
        assert result["requires_approval"] is True
        assert any("content_sha256 changed" in r for r in result["reasons"])

    def test_approval_needed_when_price_changes(
        self,
    ) -> None:
        from scripts.check_updates import check_update_policy

        old = _make_manifest()
        new = {**old, "price_cents_at_install": 999}
        result = check_update_policy(old, new)
        assert result["requires_approval"] is True
        assert any("price changed" in r for r in result["reasons"])

    def test_approval_needed_for_permission_expansion(
        self,
    ) -> None:
        from scripts.check_updates import check_update_policy

        old = _make_manifest()
        new = {**old, "required_tools": ["terminal", "file", "network"]}
        result = check_update_policy(old, new)
        assert result["requires_approval"] is True
        assert any("required_tools" in r for r in result["reasons"])

    def test_mask_secrets(self) -> None:
        from scripts.check_updates import mask_secrets

        data = {
            "apikey": "sk-12345",  # pragma: allowlist secret
            "token": "ghp_abcdef",  # pragma: allowlist secret
            "safe_field": "hello",
        }
        masked = mask_secrets(data)
        assert masked["apikey"] == "***MASKED***"
        assert masked["token"] == "***MASKED***"
        assert masked["safe_field"] == "hello"

    def test_detect_permission_expansion(
        self,
    ) -> None:
        from scripts.check_updates import detect_permission_expansion

        old = _make_manifest()
        new = {
            **old,
            "capabilities": ["weather.current", "weather.forecast", "new.cap"],
            "required_tools": ["terminal", "file", "network"],
        }
        expansions = detect_permission_expansion(old, new)
        assert "capabilities" in expansions
        assert "required_tools" in expansions
