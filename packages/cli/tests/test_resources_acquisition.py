# SPDX-License-Identifier: MIT
"""Tests for acquisition receipts, channel adapters, and reconcile."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from cli import _receipts
from cli._local_state import UnsafeIdentifierError
from cli.commands.resources._channels.logion_bundle import LogionBundleAdapter
from cli.commands.resources._channels.npx_skills import NpxSkillsAdapter


class TestReceiptDigests:
    def test_canonical_digest_is_stable(self) -> None:
        evidence = {"b": 2, "a": 1}
        first = _receipts.native_receipt_digest(evidence)
        second = _receipts.native_receipt_digest({"a": 1, "b": 2})
        assert first == second
        assert len(first) == 64

    def test_receipt_rejects_digest_mismatch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LOGION_HOME", str(tmp_path))
        receipt = self._valid_receipt()
        receipt["native_receipt_digest"] = "0" * 64
        receipt["native_evidence"] = {"schema_version": 1, "x": 1}
        with pytest.raises(ValueError, match="mismatch"):
            _receipts.save_receipt(receipt)

    def _valid_receipt(self) -> dict:
        return {
            "schema_version": 1,
            "resource_id": "r",
            "version_id": "v",
            "distribution_id": "d",
            "resource_type": "agent_skill",
            "content_digest": "sha256:placeholder",
            "channel": "logion_bundle",
            "harness": "codex",
            "scope_kind": "repo-root",
            "scope_id": "a" * 64,
            "installation_id": "b" * 64,
            "native_evidence": {
                "schema_version": 1,
                "content_digest": "sha256:placeholder",
                "aggregate_components": [
                    {
                        "aggregate_key": "bundle/x",
                        "size_bytes": 1,
                        "digest": "a" * 64,
                    }
                ],
            },
            "target_path": "/tmp/x",
            "relative_target_path": ".agents/skills/x",
            "acquired_at": "2026-08-14T00:00:00Z",
            "verification": "exact",
        }

    def test_save_and_load_roundtrip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LOGION_HOME", str(tmp_path))
        receipt = self._valid_receipt()
        digest = _receipts.aggregate_content_digest(
            receipt["native_evidence"]["aggregate_components"]
        )
        receipt["content_digest"] = digest
        receipt["native_evidence"]["content_digest"] = digest
        receipt["native_receipt_digest"] = _receipts.native_receipt_digest(
            receipt["native_evidence"]
        )
        _receipts.save_receipt(receipt)
        loaded = _receipts.load_receipts()
        assert len(loaded) == 1
        assert loaded[0]["installation_id"] == receipt["installation_id"]

    def test_scope_and_installation_ids_do_not_leak_paths(
        self, tmp_path: Path
    ) -> None:
        scope_id = _receipts.scope_id_for_target("repo-root", tmp_path)
        assert len(scope_id) == 64
        assert str(tmp_path) not in scope_id
        install = _receipts.installation_id_for(scope_id, ".agents/skills/x")
        assert ".agents" not in install


class TestNpxSkillsAdapterValidation:
    def test_rejects_foreign_program(self) -> None:
        adapter = NpxSkillsAdapter()
        with pytest.raises(RuntimeError, match="unexpected native argv"):
            adapter._validate_argv(["bash", "-c", "rm -rf /"])

    def test_rejects_non_skills_npx(self) -> None:
        adapter = NpxSkillsAdapter()
        with pytest.raises(RuntimeError, match="skills"):
            adapter._validate_argv(["npx", "otherpkg@1", "add"])


class TestLogionBundleSafety:
    def test_rejects_non_http_download_urls(self, tmp_path: Path) -> None:
        adapter = LogionBundleAdapter(client=object())
        with pytest.raises(RuntimeError, match="http or https"):
            adapter._download("file:///etc/passwd", tmp_path / "x")

    def test_aggregate_mismatch_fails_before_install(
        self, tmp_path: Path
    ) -> None:
        class FakeResources:
            def create_download(self, **_: str) -> dict:
                return {
                    "files": [
                        {
                            "path": "SKILL.md",
                            "url": "https://example.invalid/skill",
                            "size_bytes": 4,
                            "digest": hashlib.sha256(b"data").hexdigest(),
                            "aggregate_key": "bundle/SKILL.md",
                        }
                    ]
                }

        class FakeClient:
            class V1:
                resources = FakeResources()

            v1 = V1()

        adapter = LogionBundleAdapter(client=FakeClient())
        adapter._download = lambda _url, path: path.write_bytes(b"data")
        with pytest.raises(RuntimeError, match="aggregate digest mismatch"):
            adapter.acquire(
                plan={
                    "resource_id": "r",
                    "version_id": "v",
                    "content_digest": "sha256:" + "0" * 64,
                },
                destination=tmp_path / "scope" / "skill",
                scope_root=tmp_path / "scope",
            )
        assert not (tmp_path / "scope" / "skill").exists()

    def test_traversal_rejected(self) -> None:
        adapter = LogionBundleAdapter(client=object())
        with pytest.raises(UnsafeIdentifierError, match="unsafe bundle path"):
            adapter._safe_relative("../evil")

    def test_absolute_rejected(self) -> None:
        adapter = LogionBundleAdapter(client=object())
        with pytest.raises(UnsafeIdentifierError, match="unsafe bundle path"):
            adapter._safe_relative("/etc/passwd")


class TestReconcileCommand:
    def test_reconcile_reports_receipts(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("LOGION_HOME", str(tmp_path))
        receipt = TestReceiptDigests()._valid_receipt()
        digest = _receipts.aggregate_content_digest(
            receipt["native_evidence"]["aggregate_components"]
        )
        receipt["content_digest"] = digest
        receipt["native_evidence"]["content_digest"] = digest
        receipt["native_receipt_digest"] = _receipts.native_receipt_digest(
            receipt["native_evidence"]
        )
        _receipts.save_receipt(receipt)

        import argparse

        from cli.commands.resources.handlers import handle_resources_reconcile
        from cli.commands.resources.parser import register

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        register(sub)
        args = parser.parse_args(["resources", "reconcile", "--json"])
        assert handle_resources_reconcile(args) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["kind"] == "logion.resources.reconcile"
        assert payload["data"]["matched"][0]["channel"] == "logion_bundle"


class _AcquireResources:
    """Fake resources surface backing an end-to-end acquire dry-run."""

    def __init__(self, plan: dict | None, *, fail: Exception | None = None):
        self._plan = plan
        self._fail = fail
        self.plan_calls: list[dict] = []

    def get(self, **_kwargs: object) -> dict:
        return {"resource": {"id": "res-1", "title": "Audit Skill"}}

    def versions(self, **_kwargs: object) -> dict:
        return {
            "items": [
                {
                    "id": "v1",
                    "digest_algorithm": "sha256",
                    "content_digest": "abc123",
                }
            ]
        }

    def acquisition_plan(self, **kwargs: object) -> dict:
        self.plan_calls.append(dict(kwargs))
        if self._fail is not None:
            raise self._fail
        assert self._plan is not None
        return self._plan


def _server_plan(channel: str = "npx_skills") -> dict:
    return {
        "resource_id": "res-1",
        "version_id": "v1",
        "distribution_id": "d1",
        "content_digest": "sha256:" + "a" * 64,
        "selected_channel": channel,
        "alternatives": ["logion_bundle"],
        "entitlement": {"required": False, "status": "not_applicable"},
        "license": {"spdx": "MIT", "redistribution_allowed": True},
        "expected": {"bytes": 1234, "files": 4},
        "native": {
            "tool": "skills",
            "tested_version": "1.4.2",
            "argv": ["npx", "skills@1.4.2", "add", "owner/repo"],
            "upstream_locator": "owner/repo",
            "revision": "c" * 40,
        },
        "integrity": {"algorithm": "sha256", "digest": "a" * 64},
        "permissions": {"network": True, "tools": [], "secrets": []},
        "warnings": [],
    }


def _acquire_args(tmp_path: Path, *extra: str):
    import argparse

    from cli.commands.resources.parser import register

    parser = argparse.ArgumentParser()
    register(parser.add_subparsers())
    return parser.parse_args([
        "resources",
        "acquire",
        "res-1",
        "--harness",
        "codex",
        "--cwd",
        str(tmp_path),
        "--scope",
        "repo-root",
        "--json",
        *extra,
    ])


class TestDryRunPreviewsExecution:
    """A dry-run must preview exactly what execution would do."""

    def _run(self, tmp_path, monkeypatch, capsys, resources, *extra: str):
        from cli.commands.resources._acquire_handler import (
            handle_resources_acquire,
        )

        (tmp_path / ".git").mkdir(exist_ok=True)
        client = _FakeAcquireClient(resources)
        monkeypatch.setattr(
            "cli.commands.resources._acquire_handler.make_client",
            lambda _config: client,
        )
        args = _acquire_args(tmp_path, *extra)
        code = handle_resources_acquire(args)
        return code, json.loads(capsys.readouterr().out)["data"]

    def test_dry_run_exposes_channel_argv_bytes_and_permissions(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        resources = _AcquireResources(_server_plan())
        code, plan = self._run(tmp_path, monkeypatch, capsys, resources)
        assert code == 0
        assert plan["dry_run"] is True
        distribution = plan["distribution"]
        assert distribution["resolved"] is True
        assert distribution["channel"] == "npx_skills"
        assert distribution["expected_bytes"] == 1234
        assert distribution["native"]["argv"] == [
            "npx",
            "skills@1.4.2",
            "add",
            "owner/repo",
        ]
        assert distribution["native"]["revision"] == "c" * 40
        assert plan["permissions_required"] == {
            "network": True,
            "tools": [],
            "secrets": [],
        }
        assert plan["verification"]["expected_level"] == "source_revision"
        assert plan["executable"] is True
        assert plan["targets"][0]["operation"]["kind"] == (
            "delegate-native-manager"
        )

    def test_dry_run_writes_nothing(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        (tmp_path / ".git").mkdir(exist_ok=True)
        before = sorted(p.name for p in tmp_path.rglob("*"))
        resources = _AcquireResources(_server_plan())
        self._run(tmp_path, monkeypatch, capsys, resources)
        assert sorted(p.name for p in tmp_path.rglob("*")) == before

    def test_hosted_bundle_expects_exact_verification(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        plan_payload = _server_plan("logion_bundle")
        _, plan = self._run(
            tmp_path,
            monkeypatch,
            capsys,
            _AcquireResources(plan_payload),
            "--channel",
            "logion_bundle",
        )
        assert plan["verification"]["expected_level"] == "exact"
        assert plan["targets"][0]["operation"]["kind"] == "download"

    def test_unresolved_distribution_is_not_executable(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        resources = _AcquireResources(None, fail=RuntimeError("no bundle"))
        _, plan = self._run(tmp_path, monkeypatch, capsys, resources)
        assert plan["distribution"]["resolved"] is False
        assert plan["executable"] is False
        assert any("no bundle" in r for r in plan["blocked_reasons"])
        assert plan["verification"]["expected_level"] == "unknown"


class _FakeAcquireClient:
    def __init__(self, resources: object) -> None:
        self.v1 = type("FakeV1", (), {"resources": resources})()

    def close(self) -> None:
        return None


class TestExecutionGuards:
    def _run(self, tmp_path, monkeypatch, capsys, resources, *extra: str):
        from cli.commands.resources._acquire_handler import (
            handle_resources_acquire,
        )

        (tmp_path / ".git").mkdir(exist_ok=True)
        client = _FakeAcquireClient(resources)
        monkeypatch.setattr(
            "cli.commands.resources._acquire_handler.make_client",
            lambda _config: client,
        )
        args = _acquire_args(tmp_path, "--no-dry-run", "--yes", *extra)
        code = handle_resources_acquire(args)
        return code, capsys.readouterr()

    def test_refuses_to_execute_a_plan_its_dry_run_calls_blocked(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        resources = _AcquireResources(None, fail=RuntimeError("no bundle"))
        code, captured = self._run(tmp_path, monkeypatch, capsys, resources)
        assert code == 2
        assert "not executable" in captured.err

    def test_refuses_a_channel_the_user_did_not_approve(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        resources = _AcquireResources(_server_plan("logion_bundle"))
        code, captured = self._run(
            tmp_path,
            monkeypatch,
            capsys,
            resources,
            "--channel",
            "npx_skills",
        )
        assert code == 2
        assert "logion_bundle" in captured.err


class TestSkillsLockParser:
    """The lockfile is name-keyed and must fail closed on unknown shapes."""

    def _lock(self, tmp_path: Path, payload: dict) -> Path:
        path = tmp_path / "skills-lock.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def _canonical(self) -> dict:
        return {
            "version": 1,
            "skills": {
                "find-skills": {
                    "source": "vercel-labs/skills",
                    "sourceType": "github",
                    "computedHash": "sha256:" + "b" * 64,
                }
            },
        }

    def test_skill_name_comes_from_the_mapping_key(
        self, tmp_path: Path
    ) -> None:
        from cli.commands.resources._channels._skills_lock import (
            parse_skills_lock,
        )

        entries = parse_skills_lock(self._lock(tmp_path, self._canonical()))
        assert [entry.name for entry in entries] == ["find-skills"]

    def test_computed_hash_is_never_double_prefixed(
        self, tmp_path: Path
    ) -> None:
        from cli.commands.resources._channels._skills_lock import (
            parse_skills_lock,
        )

        payload = self._canonical()
        entries = parse_skills_lock(self._lock(tmp_path, payload))
        assert entries[0].content_digest == "sha256:" + "b" * 64
        payload["skills"]["find-skills"]["computedHash"] = "c" * 64
        entries = parse_skills_lock(self._lock(tmp_path, payload))
        assert entries[0].content_digest == "sha256:" + "c" * 64

    def test_computed_hash_is_not_promoted_to_a_revision(
        self, tmp_path: Path
    ) -> None:
        from cli.commands.resources._channels._skills_lock import (
            parse_skills_lock,
        )

        entries = parse_skills_lock(self._lock(tmp_path, self._canonical()))
        assert entries[0].revision == ""

    def test_unknown_lock_version_fails_closed(self, tmp_path: Path) -> None:
        from cli.commands.resources._channels._skills_lock import (
            UnsupportedLockfileError,
            parse_skills_lock,
        )

        payload = self._canonical()
        payload["version"] = 99
        with pytest.raises(UnsupportedLockfileError, match="version"):
            parse_skills_lock(self._lock(tmp_path, payload))

    def test_unknown_source_type_fails_closed(self, tmp_path: Path) -> None:
        from cli.commands.resources._channels._skills_lock import (
            UnsupportedLockfileError,
            parse_skills_lock,
        )

        payload = self._canonical()
        payload["skills"]["find-skills"]["sourceType"] = "tarball"
        with pytest.raises(UnsupportedLockfileError, match="sourceType"):
            parse_skills_lock(self._lock(tmp_path, payload))

    def test_selection_is_exact_not_substring(self, tmp_path: Path) -> None:
        from cli.commands.resources._channels._skills_lock import (
            UnsupportedLockfileError,
            parse_skills_lock,
            select_entry,
        )

        payload = self._canonical()
        payload["skills"]["other"] = {
            "source": "vercel-labs/skills-extra",
            "sourceType": "github",
            "computedHash": "d" * 64,
        }
        entries = parse_skills_lock(self._lock(tmp_path, payload))
        chosen = select_entry(
            entries,
            expected_source="vercel-labs/skills",
            expected_name="find-skills",
        )
        assert chosen.name == "find-skills"
        with pytest.raises(UnsupportedLockfileError, match="expected exactly"):
            select_entry(
                entries, expected_source="vercel-labs", expected_name=""
            )

    def test_floating_manager_tag_is_refused(self) -> None:
        from cli.commands.resources._channels._skills_lock import (
            UnsupportedLockfileError,
            manager_version_from_argv,
        )

        assert (
            manager_version_from_argv(["npx", "skills@1.4.2", "add", "x"])
            == "1.4.2"
        )
        with pytest.raises(UnsupportedLockfileError, match="immutable"):
            manager_version_from_argv(["npx", "skills@latest", "add", "x"])


class TestExactLocatorMatching:
    def test_neighbouring_repository_never_matches(self) -> None:
        from cli.commands.resources._catalog_reconciliation import (
            normalize_locator,
        )

        assert normalize_locator("https://github.com/Owner/Repo.git") == (
            "owner/repo"
        )
        assert normalize_locator("gh:owner/repo") == "owner/repo"
        assert normalize_locator("owner/repo") != normalize_locator(
            "owner/repo-extra"
        )


class TestDriftDetection:
    def _install(self, tmp_path: Path) -> dict:
        scope_root = tmp_path / "repo"
        skill = scope_root / ".agents" / "skills" / "audit"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_bytes(b"# audit\n")
        relative = ".agents/skills/audit/SKILL.md"
        return {
            "target_path": str(skill),
            "relative_target_path": ".agents/skills/audit",
            "scope_root": scope_root,
            "verification": "exact",
            "native_evidence": {
                "file_digests": {
                    relative: hashlib.sha256(b"# audit\n").hexdigest()
                }
            },
        }

    def test_intact_installation_keeps_its_verification(
        self, tmp_path: Path
    ) -> None:
        from cli.commands.resources._reconciliation import receipt_status

        receipt = self._install(tmp_path)
        status, evidence = receipt_status(receipt, receipt["scope_root"])
        assert status == "exact"
        assert evidence == "validated-local-receipt"

    def test_edited_installation_reports_drift(self, tmp_path: Path) -> None:
        from cli.commands.resources._reconciliation import receipt_status

        receipt = self._install(tmp_path)
        target = receipt["scope_root"] / ".agents/skills/audit/SKILL.md"
        target.write_bytes(b"# tampered\n")
        status, evidence = receipt_status(receipt, receipt["scope_root"])
        assert status == "drifted"
        assert "digest-mismatch" in evidence

    def test_deleted_installation_reports_drift(self, tmp_path: Path) -> None:
        from cli.commands.resources._reconciliation import receipt_status

        receipt = self._install(tmp_path)
        (receipt["scope_root"] / ".agents/skills/audit/SKILL.md").unlink()
        status, evidence = receipt_status(receipt, receipt["scope_root"])
        assert status == "drifted"
        assert "missing-file" in evidence


class TestFailClosedLeavesNoReceipt:
    def test_digest_mismatch_writes_no_receipt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LOGION_HOME", str(tmp_path / "home"))

        class FakeResources:
            def create_download(self, **_: str) -> dict:
                return {
                    "files": [
                        {
                            "path": "SKILL.md",
                            "url": "https://example.invalid/skill",
                            "size_bytes": 4,
                            "digest": hashlib.sha256(b"data").hexdigest(),
                            "aggregate_key": "bundle/SKILL.md",
                        }
                    ]
                }

        client = type(
            "C", (), {"v1": type("V", (), {"resources": FakeResources()})()}
        )()
        adapter = LogionBundleAdapter(client=client)
        adapter._download = lambda _url, path: path.write_bytes(b"data")
        with pytest.raises(RuntimeError, match="aggregate digest mismatch"):
            adapter.acquire(
                plan={
                    "resource_id": "r",
                    "version_id": "v",
                    "content_digest": "sha256:" + "0" * 64,
                },
                destination=tmp_path / "scope" / "skill",
                scope_root=tmp_path / "scope",
            )
        assert _receipts.load_receipts() == []

    def test_failed_swap_restores_the_previous_installation(
        self, tmp_path: Path
    ) -> None:
        adapter = LogionBundleAdapter(client=object())
        destination = tmp_path / "skills" / "audit"
        destination.mkdir(parents=True)
        (destination / "SKILL.md").write_bytes(b"previous\n")
        stage = tmp_path / "stage"
        stage.mkdir()
        (stage / "SKILL.md").write_bytes(b"incoming\n")

        import os as _os

        real_replace = _os.replace
        calls = {"n": 0}

        def flaky(src, dst):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("swap failed")
            return real_replace(src, dst)

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                "cli.commands.resources._channels.logion_bundle.os.replace",
                flaky,
            )
            with pytest.raises(OSError, match="swap failed"):
                adapter._install(stage, destination)
        assert (destination / "SKILL.md").read_bytes() == b"previous\n"


class TestInventoryIsTheCanonicalLocalRecord:
    def _receipt(self, tmp_path: Path, resource_type: str, name: str) -> dict:
        scope_root = tmp_path / "repo"
        install = scope_root / ".agents" / "skills" / name
        install.mkdir(parents=True)
        (install / "manifest.json").write_bytes(b"{}\n")
        receipt = TestReceiptDigests()._valid_receipt()
        digest = _receipts.aggregate_content_digest(
            receipt["native_evidence"]["aggregate_components"]
        )
        receipt.update({
            "content_digest": digest,
            "resource_type": resource_type,
            "target_path": str(install),
            "relative_target_path": f".agents/skills/{name}",
            "installation_id": _receipts.installation_id_for(
                _receipts.scope_id_for_target("repo-root", scope_root),
                f".agents/skills/{name}",
            ),
        })
        receipt["native_evidence"]["content_digest"] = digest
        receipt["native_receipt_digest"] = _receipts.native_receipt_digest(
            receipt["native_evidence"]
        )
        _receipts.save_receipt(receipt)
        return receipt

    def test_receipt_surfaces_a_plugin_without_a_skill_md(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from cli._harness.scopes import ScopeTarget
        from cli.commands.resources._inventory_entries import (
            _receipts_by_path,
            _scan_dir,
        )

        monkeypatch.setenv("LOGION_HOME", str(tmp_path / "home"))
        receipt = self._receipt(tmp_path, "agent_plugin", "review-plugin")
        target = ScopeTarget(
            scope_kind="repo-root",
            scope_root=tmp_path / "repo",
            target_path=tmp_path / "repo" / ".agents" / "skills",
            native_manager=None,
            exists=True,
        )
        found = _scan_dir(target, 0, _receipts_by_path())
        assert [item["name"] for item in found] == ["review-plugin"]
        assert found[0]["resource_type"] == "agent_plugin"
        assert (
            found[0]["receipt"]["installation_id"]
            == (receipt["installation_id"])
        )

    def test_installs_without_a_receipt_stay_unlinked(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from cli._harness.scopes import ScopeTarget
        from cli.commands.resources._inventory_entries import (
            _receipts_by_path,
            _scan_dir,
        )

        monkeypatch.setenv("LOGION_HOME", str(tmp_path / "home"))
        skills = tmp_path / "repo" / ".agents" / "skills"
        (skills / "handwritten").mkdir(parents=True)
        (skills / "handwritten" / "SKILL.md").write_bytes(b"# hand\n")
        target = ScopeTarget(
            scope_kind="repo-root",
            scope_root=tmp_path / "repo",
            target_path=skills,
            native_manager=None,
            exists=True,
        )
        found = _scan_dir(target, 0, _receipts_by_path())
        assert found[0]["reconciliation"]["status"] == "unlinked"
