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
