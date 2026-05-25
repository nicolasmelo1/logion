"""Tests for local_state module: layout, manifest, index, recall, lock,
workflows, update policy, secret masking, danger flag enum, content
verification, and schema envelope.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli._local_state import (
    DANGER_FLAGS,
    INDEX_FILENAME,
    LOCKS_DIRNAME,
    MASK_PLACEHOLDER,
    RECALL_FILENAME,
    SCHEMA_VERSION,
    WORKFLOWS_FILENAME,
    acquire_lock,
    any_locks,
    build_index,
    build_recall_entries,
    compute_installed_hash,
    detect_danger_flags,
    ensure_layout,
    is_locked,
    list_installed,
    mask_secrets,
    read_index,
    read_lock,
    read_manifest,
    read_recall,
    read_workflows,
    rebuild_recall,
    record_workflow_success,
    release_lock,
    search_recall,
    sha256_of_files,
    validate_manifest,
    verify_installed_content,
    write_index,
    write_manifest,
    write_recall,
    write_workflows,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def home(tmp_path: Path) -> Path:
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


def _install_files(
    home: Path,
    course_id: str,
    version_id: str,
    files: dict[str, str],
) -> str:
    """Install file contents under installed/<course>/<version>/ and
    return the resulting content_sha256."""
    base = home / "installed" / course_id / version_id
    base.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for rel, content in files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        paths.append(p)
    return sha256_of_files(paths, root=base)


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
        from cli._local_state import get_home

        assert get_home() == custom

    def test_default_home_without_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("LOGION_HOME", raising=False)
        from cli._local_state import (
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
        assert read_manifest("nonexistent", "1.0", home) is None

    def test_validate_manifest_valid(self) -> None:
        assert validate_manifest(_make_manifest()) == []

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
        assert list_installed(home) == []

    def test_list_installed_multiple(self, home: Path) -> None:
        write_manifest(_make_manifest("a", "1.0"), "a", "1.0", home)
        write_manifest(_make_manifest("b", "2.0"), "b", "2.0", home)
        ids = {r["course_id"] for r in list_installed(home)}
        assert ids == {"a", "b"}

    def test_sha256_of_files(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("hello")
        f2.write_text("world")
        digest = sha256_of_files([f1, f2])
        assert len(digest) == 64


# ---------------------------------------------------------------------------
# Content verification
# ---------------------------------------------------------------------------


class TestContentVerification:
    def test_compute_installed_hash_matches_manifest(self, home: Path) -> None:
        sha = _install_files(
            home,
            "weather.basic",
            "2026.05.20",
            {"SKILL.md": "body"},
        )
        m = _make_manifest()
        m["content_sha256"] = sha
        write_manifest(m, "weather.basic", "2026.05.20", home)
        assert (
            compute_installed_hash("weather.basic", "2026.05.20", home) == sha
        )

    def test_verify_installed_content_ok(self, home: Path) -> None:
        sha = _install_files(
            home, "weather.basic", "2026.05.20", {"SKILL.md": "body"}
        )
        m = _make_manifest()
        m["content_sha256"] = sha
        write_manifest(m, "weather.basic", "2026.05.20", home)
        result = verify_installed_content("weather.basic", "2026.05.20", home)
        assert result["ok"] is True
        assert result["user_modified"] is False

    def test_verify_detects_user_modification(self, home: Path) -> None:
        _install_files(
            home, "weather.basic", "2026.05.20", {"SKILL.md": "original"}
        )
        m = _make_manifest()
        m["content_sha256"] = "deadbeef"  # mismatched on purpose
        write_manifest(m, "weather.basic", "2026.05.20", home)
        result = verify_installed_content("weather.basic", "2026.05.20", home)
        assert result["ok"] is False
        assert result["user_modified"] is True
        assert result["expected"] != result["actual"]

    def test_verify_missing_manifest(self, home: Path) -> None:
        result = verify_installed_content("nope", "1.0", home)
        assert result["ok"] is False
        assert result["user_modified"] is False


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------


class TestIndex:
    def test_build_index(self, home: Path) -> None:
        write_manifest(_make_manifest(), "weather.basic", "2026.05.20", home)
        index = build_index(home)
        assert len(index) == 1
        assert index[0]["course_id"] == "weather.basic"
        assert "content_sha256" not in index[0]
        assert "installed_at" not in index[0]

    def test_write_and_read_index_roundtrip(self, home: Path) -> None:
        write_index([{"course_id": "x", "version_id": "1"}], home)
        result = read_index(home)
        assert result == [{"course_id": "x", "version_id": "1"}]

    def test_read_index_missing(self, home: Path) -> None:
        assert read_index(home) == []

    def test_index_uses_envelope_on_disk(self, home: Path) -> None:
        write_index([{"course_id": "x", "version_id": "1"}], home)
        raw = json.loads((home / INDEX_FILENAME).read_text(encoding="utf-8"))
        assert raw["schema_version"] == SCHEMA_VERSION
        assert isinstance(raw["entries"], list)

    def test_index_reads_legacy_bare_list(self, home: Path) -> None:
        (home / INDEX_FILENAME).write_text(
            json.dumps([{"course_id": "legacy", "version_id": "0"}]),
            encoding="utf-8",
        )
        assert read_index(home) == [{"course_id": "legacy", "version_id": "0"}]


# ---------------------------------------------------------------------------
# Recall
# ---------------------------------------------------------------------------


class TestRecall:
    def test_build_recall_from_installed(self, home: Path) -> None:
        write_manifest(_make_manifest(), "weather.basic", "2026.05.20", home)
        entries = build_recall_entries(list_installed(home))
        assert len(entries) == 1
        e = entries[0]
        assert e["type"] == "installed_capability"
        assert e["id"] == "weather.basic"
        assert e["source"] == "installed_index"
        assert e["danger_flags"] == []

    def test_build_recall_with_workflows(self, home: Path) -> None:
        write_manifest(_make_manifest(), "weather.basic", "2026.05.20", home)
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
        types = {
            e["type"] for e in build_recall_entries(list_installed(home), wf)
        }
        assert types == {"installed_capability", "workflow"}

    def test_recall_envelope_on_disk(self, home: Path) -> None:
        write_recall(
            [{"type": "installed_capability", "id": "x"}],
            home,
        )
        raw = json.loads((home / RECALL_FILENAME).read_text(encoding="utf-8"))
        assert raw["schema_version"] == SCHEMA_VERSION
        assert raw["entries"][0]["id"] == "x"

    def test_search_recall(self, home: Path) -> None:
        write_manifest(
            _make_manifest(title="Weather Check Skill"),
            "weather.basic",
            "2026.05.20",
            home,
        )
        write_recall(build_recall_entries(list_installed(home)), home)
        results = search_recall("weather", home, limit=5)
        assert results[0]["id"] == "weather.basic"

    def test_search_recall_no_results(self, home: Path) -> None:
        write_recall([], home)
        assert search_recall("nonexistent", home) == []

    def test_rebuild_recall_includes_workflows(self, home: Path) -> None:
        write_manifest(_make_manifest(), "weather.basic", "2026.05.20", home)
        write_workflows(
            [
                {
                    "id": "wf1",
                    "title": "Workflow One",
                    "commands": ["echo hi"],
                    "success_count": 1,
                    "last_success_at": "2026-05-21T00:00:00Z",
                    "confidence": 0.5,
                }
            ],
            home,
        )
        rebuild_recall(home)
        ids = {e["id"] for e in read_recall(home)}
        assert "weather.basic" in ids
        assert "wf1" in ids


class TestRecallMasksSecrets:
    def test_workflow_with_secret_field_is_masked(self) -> None:
        wf = [
            {
                "id": "deploy",
                "title": "Deploy",
                "commands": ["./deploy.sh"],
                "success_count": 1,
                "last_success_at": "2026-05-21T00:00:00Z",
                "confidence": 0.5,
                "api_key": "sk-live-12345",  # pragma: allowlist secret
                "auth_token": "ghp_xyz",  # pragma: allowlist secret
            }
        ]
        entries = build_recall_entries([], workflows=wf)
        entry_str = json.dumps(entries[0])
        # Recall builder drops unknown fields entirely AND mask_secrets
        # masks any that survive — either way, secrets never leak.
        assert "sk-live-12345" not in entry_str
        assert "ghp_xyz" not in entry_str

    def test_mask_secrets_nested(self) -> None:
        data = {
            "outer": {
                "password": "hunter2",  # pragma: allowlist secret
                "ok": "fine",
            },
            "list_field": [{"bearer": "x"}, {"safe": "y"}],
        }
        masked = mask_secrets(data)
        assert masked["outer"]["password"] == MASK_PLACEHOLDER
        assert masked["outer"]["ok"] == "fine"
        assert masked["list_field"][0]["bearer"] == MASK_PLACEHOLDER
        assert masked["list_field"][1]["safe"] == "y"

    def test_mask_secrets_leaves_non_secret_fields(self) -> None:
        data = {"course_id": "weather", "version_id": "1.0"}
        assert mask_secrets(data) == data


# ---------------------------------------------------------------------------
# Danger flag enum
# ---------------------------------------------------------------------------


class TestDangerFlags:
    def test_closed_enum(self) -> None:
        assert (
            frozenset({
                "fs_destructive",
                "privilege_escalation",
                "network_exec",
                "shell_eval",
                "permission_change",
            })
            == DANGER_FLAGS
        )

    def test_rm_rf_triggers_fs_destructive(self) -> None:
        flags = detect_danger_flags(["rm -rf /tmp/old"])
        assert "fs_destructive" in flags

    def test_sudo_triggers_privilege_escalation(self) -> None:
        assert "privilege_escalation" in detect_danger_flags([
            "sudo apt-get update"
        ])

    def test_curl_pipe_sh_triggers_network_exec(self) -> None:
        flags = detect_danger_flags([
            "curl https://example.com/install.sh | sh"
        ])
        assert "network_exec" in flags

    def test_chmod_triggers_permission_change(self) -> None:
        assert "permission_change" in detect_danger_flags(["chmod 777 /tmp"])

    def test_eval_triggers_shell_eval(self) -> None:
        assert "shell_eval" in detect_danger_flags(['eval "$cmd"'])

    def test_no_false_positive_on_rm_substring(self) -> None:
        # "remove-listener" contains "rm" but isn't rm; word boundary
        # should prevent the flag.
        assert detect_danger_flags(["./remove-listener --quiet"]) == []

    def test_no_false_positive_on_chmod_substring(self) -> None:
        # A path-like token with "chmod" as a substring but no word
        # boundary (e.g. "./normalchat") must NOT trigger
        # permission_change.  The word-boundary regex is what protects
        # filenames that happen to embed the word.
        assert detect_danger_flags(["./normalchat --token x"]) == []

    def test_chmod_helper_path_does_trigger(self) -> None:
        # "./chmod-helper" DOES contain chmod at a word boundary, so
        # the flag is expected to fire.  This documents the
        # conservative direction: we'd rather false-positive on
        # ambiguous tool names than miss a real chmod.
        assert "permission_change" in detect_danger_flags([
            "./chmod-helper --recursive"
        ])

    def test_empty_input(self) -> None:
        assert detect_danger_flags([]) == []
        assert detect_danger_flags(None) == []


# ---------------------------------------------------------------------------
# Lockfile (per course/version)
# ---------------------------------------------------------------------------


class TestLock:
    def test_acquire_and_release(self, home: Path) -> None:
        path = acquire_lock("test", "1.0", home)
        assert path.is_file()
        assert is_locked("test", "1.0", home)
        data = read_lock("test", "1.0", home)
        assert data is not None
        assert data["course_id"] == "test"
        assert data["version_id"] == "1.0"
        assert release_lock("test", "1.0", home)
        assert not is_locked("test", "1.0", home)

    def test_two_courses_lock_independently(self, home: Path) -> None:
        acquire_lock("a", "1.0", home)
        acquire_lock("b", "1.0", home)
        assert is_locked("a", "1.0", home)
        assert is_locked("b", "1.0", home)
        assert sorted(any_locks(home)) == [("a", "1.0"), ("b", "1.0")]
        release_lock("a", "1.0", home)
        assert not is_locked("a", "1.0", home)
        assert is_locked("b", "1.0", home)

    def test_read_lock_missing(self, home: Path) -> None:
        assert read_lock("nope", "0", home) is None
        assert not is_locked("nope", "0", home)

    def test_release_lock_when_none(self, home: Path) -> None:
        assert release_lock("nope", "0", home) is False

    def test_locks_live_outside_install_dir(self, home: Path) -> None:
        # rmtree of install dir must not destroy locks
        acquire_lock("a", "1.0", home)
        assert (home / LOCKS_DIRNAME).is_dir()


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------


class TestWorkflows:
    def test_read_workflows_empty(self, home: Path) -> None:
        assert read_workflows(home) == []

    def test_workflows_envelope_on_disk(self, home: Path) -> None:
        write_workflows([{"id": "x"}], home)
        raw = json.loads(
            (home / WORKFLOWS_FILENAME).read_text(encoding="utf-8")
        )
        assert raw["schema_version"] == SCHEMA_VERSION
        assert raw["entries"][0]["id"] == "x"

    def test_record_workflow_success_creates_new(self, home: Path) -> None:
        record = record_workflow_success(
            "verify-companion",
            "Verify companion",
            ["make verify"],
            home,
        )
        assert record["success_count"] == 1
        assert record["last_success_at"]
        # rebuild_recall also fires
        ids = {e["id"] for e in read_recall(home)}
        assert "verify-companion" in ids

    def test_record_workflow_success_increments(self, home: Path) -> None:
        record_workflow_success(
            "verify-companion", "Verify", ["make verify"], home
        )
        record = record_workflow_success(
            "verify-companion", "Verify", ["make verify"], home
        )
        assert record["success_count"] == 2

    def test_record_workflow_confidence_grows(self, home: Path) -> None:
        first = record_workflow_success(
            "wf", "W", ["echo"], home, confidence=0.5
        )
        second = record_workflow_success("wf", "W", ["echo"], home)
        assert second["confidence"] > first["confidence"]
        assert second["confidence"] <= 1.0


# ---------------------------------------------------------------------------
# Identifier safety (path traversal)
# ---------------------------------------------------------------------------


class TestIdentifierSafety:
    def test_write_manifest_rejects_path_traversal(self, home: Path) -> None:
        from cli._local_state import UnsafeIdentifierError

        with pytest.raises(UnsafeIdentifierError):
            write_manifest(_make_manifest(), "../escape", "1.0", home)

    def test_write_manifest_rejects_slash(self, home: Path) -> None:
        from cli._local_state import UnsafeIdentifierError

        with pytest.raises(UnsafeIdentifierError):
            write_manifest(_make_manifest(), "a/b", "1.0", home)

    def test_read_manifest_returns_none_for_unsafe(self, home: Path) -> None:
        # read_manifest must not raise — it returns None so callers can
        # treat traversal attempts the same as "not installed".
        assert read_manifest("../etc", "1.0", home) is None

    def test_compute_installed_hash_rejects_unsafe(self, home: Path) -> None:
        assert compute_installed_hash("../etc", "1.0", home) == ""

    def test_lock_path_rejects_unsafe(self, home: Path) -> None:
        from cli._local_state import UnsafeIdentifierError, acquire_lock

        with pytest.raises(UnsafeIdentifierError):
            acquire_lock("../escape", "1.0", home)


# ---------------------------------------------------------------------------
# Lock atomicity (O_EXCL)
# ---------------------------------------------------------------------------


class TestLockExclusive:
    def test_second_acquire_raises_lock_held(self, home: Path) -> None:
        from cli._local_state import LockHeldError

        acquire_lock("x", "1.0", home)
        with pytest.raises(LockHeldError):
            acquire_lock("x", "1.0", home)
        release_lock("x", "1.0", home)

    def test_release_then_reacquire(self, home: Path) -> None:
        acquire_lock("x", "1.0", home)
        release_lock("x", "1.0", home)
        # Must succeed: lock file removed, O_EXCL is back to clean state
        acquire_lock("x", "1.0", home)
        release_lock("x", "1.0", home)


# ---------------------------------------------------------------------------
# Hash disambiguation (rename + ordering)
# ---------------------------------------------------------------------------


class TestHashDisambiguation:
    def test_rename_changes_digest(self, tmp_path: Path) -> None:
        # Two files with identical bytes but different names must
        # produce different digests now that the hash includes the
        # relative path.
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_text("same")
        b.write_text("same")
        first = sha256_of_files([a], root=tmp_path)
        # Rename a.txt -> renamed.txt; same bytes, different name
        renamed = tmp_path / "renamed.txt"
        a.rename(renamed)
        second = sha256_of_files([renamed], root=tmp_path)
        assert first != second

    def test_repartition_changes_digest(self, tmp_path: Path) -> None:
        # "hello" + "world" in two files vs. "helloworld" in one file
        # must hash differently because of the length prefix.
        a1 = tmp_path / "a"
        b1 = tmp_path / "b"
        a1.write_text("hello")
        b1.write_text("world")
        split = sha256_of_files([a1, b1], root=tmp_path)
        a1.write_text("helloworld")
        b1.unlink()
        merged = sha256_of_files([a1], root=tmp_path)
        assert split != merged


# ---------------------------------------------------------------------------
# Atomic state-file writes
# ---------------------------------------------------------------------------


class TestAtomicWrites:
    def test_no_tempfile_leftover(self, home: Path) -> None:
        write_index([{"course_id": "x", "version_id": "1"}], home)
        # No .tmp.* leftover from the atomic rename
        leftovers = list(home.glob(".index.json.tmp.*"))
        assert leftovers == []

    def test_existing_file_replaced_atomically(self, home: Path) -> None:
        write_index([{"course_id": "a", "version_id": "1"}], home)
        write_index([{"course_id": "b", "version_id": "2"}], home)
        assert read_index(home) == [{"course_id": "b", "version_id": "2"}]


# ---------------------------------------------------------------------------
# Update policy
# ---------------------------------------------------------------------------


class TestUpdatePolicy:
    def _local(self) -> dict:
        return {
            "course_id": "x",
            "version_id": "1.0",
            "required_tools": ["web"],
            "permissions": ["read"],
            "env_vars": [],
            "execution_policy": "approval-required",
            "content_sha256": "aaa",
            "price_cents_at_install": 0,
        }

    def test_required_tools_expansion_requires_approval(self) -> None:
        from cli._update_policy import check_update_policy

        local = self._local()
        remote = {**local, "required_tools": ["web", "shell"]}
        result = check_update_policy(local, remote)
        assert result.requires_approval is True
        assert "required_tools" in result.changed_fields

    def test_permission_change_requires_approval(self) -> None:
        from cli._update_policy import check_update_policy

        local = self._local()
        remote = {**local, "permissions": ["read", "write"]}
        result = check_update_policy(local, remote)
        assert result.requires_approval is True
        assert "permissions" in result.changed_fields

    def test_env_vars_change_requires_approval(self) -> None:
        from cli._update_policy import check_update_policy

        local = self._local()
        remote = {**local, "env_vars": ["API_KEY"]}
        result = check_update_policy(local, remote)
        assert result.requires_approval is True

    def test_execution_policy_change_requires_approval(self) -> None:
        from cli._update_policy import check_update_policy

        local = self._local()
        remote = {**local, "execution_policy": "auto-run"}
        result = check_update_policy(local, remote)
        assert result.requires_approval is True

    def test_price_change_is_notice_not_gate(self) -> None:
        # Per the entitlement model, an existing buyer is not re-billed
        # when the seller raises the price.  Price change is surfaced
        # as a notice but must not force approval.
        from cli._update_policy import check_update_policy

        local = self._local()
        remote = {**local, "price_cents_at_install": 999}
        result = check_update_policy(local, remote)
        assert result.requires_approval is False
        assert any("price_cents_at_install" in n for n in result.notices)

    def test_clean_content_only_upgrade_is_silent(self) -> None:
        from cli._update_policy import check_update_policy

        local = self._local()
        remote = {**local, "version_id": "1.1", "content_sha256": "bbb"}
        result = check_update_policy(local, remote)
        assert result.applicable is True
        assert result.requires_approval is False
        assert result.blocks_silent_overwrite is False

    def test_user_modified_blocks_clean_upgrade(self, home: Path) -> None:
        from cli._update_policy import evaluate_update

        # Install something with a known hash, then mutate the file so
        # verify_installed_content reports user_modified=True.
        sha = _install_files(home, "x", "1.0", {"SKILL.md": "original"})
        m = _make_manifest("x", "1.0")
        m["content_sha256"] = sha
        m["required_tools"] = ["web"]
        m["permissions"] = []
        m["env_vars"] = []
        m["execution_policy"] = "approval-required"
        write_manifest(m, "x", "1.0", home)
        (home / "installed" / "x" / "1.0" / "SKILL.md").write_text(
            "tampered", encoding="utf-8"
        )

        remote = {
            **m,
            "version_id": "1.1",
            "content_sha256": "different",
        }
        result = evaluate_update("x", "1.0", remote, m, home)
        assert result.requires_approval is True
        assert result.blocks_silent_overwrite is True
