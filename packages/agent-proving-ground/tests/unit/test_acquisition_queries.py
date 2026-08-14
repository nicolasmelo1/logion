"""Regression tests for the native-acquisition query handlers.

These queries are the proving ground's only independent check on what the
CLI claims it installed, so each one is tested for the case it is meant to
catch — not just its happy path.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from agent_proving_ground.api_adapters._queries import LogionApiQueries
from agent_proving_ground.assertions.api import (
    AcquisitionIdempotentAssertion,
    InstallDriftReportedAssertion,
    InstalledArtifactDigestMatchesAssertion,
    InventoryReceiptMatchesAssertion,
    NativeInstallReconciledAssertion,
    ResourceAcquisitionExistsAssertion,
    ResourceDistributionSelectedAssertion,
    ScopeIsolationPreservedAssertion,
)
from agent_proving_ground.assertions.registry import AssertionRegistry


def _write_envelope(path: Path, kind: str, data: dict) -> Path:
    path.write_text(
        json.dumps({"version": "v1", "kind": kind, "data": data}),
        encoding="utf-8",
    )
    return path


def _receipt(**overrides) -> dict:
    base = {
        "resource_id": "r1",
        "version_id": "v1",
        "distribution_id": "d1",
        "installation_id": "i1",
        "content_digest": "",
        "channel": "logion_bundle",
        "verification": "exact",
        "installed_paths": [],
    }
    base.update(overrides)
    return base


def _queries() -> LogionApiQueries:
    return LogionApiQueries("http://x", _DummyKeys())


def _installed(
    tmp_path: Path, body: bytes = b"hello"
) -> tuple[Path, str, str]:
    root = tmp_path / "repo"
    (root / ".agents/skills/x").mkdir(parents=True)
    (root / ".agents/skills/x/SKILL.md").write_bytes(body)
    relative = ".agents/skills/x/SKILL.md"
    return root, relative, hashlib.sha256(body).hexdigest()


@pytest.mark.asyncio
async def test_resource_acquisition_exists_passes(tmp_path: Path) -> None:
    artifact = _write_envelope(
        tmp_path / "a.json", "logion.resources.acquire", _receipt()
    )
    result = await _queries().query(
        {"type": "resource_acquisition_exists", "artifact": str(artifact)},
        {},
    )
    assert result["acquired"] is True
    assert result["installation_id"] == "i1"


@pytest.mark.asyncio
async def test_distribution_selected_allows_channels(tmp_path: Path) -> None:
    artifact = _write_envelope(
        tmp_path / "a.json",
        "logion.resources.acquire",
        _receipt(channel="npx_skills"),
    )
    result = await _queries().query(
        {
            "type": "resource_distribution_selected",
            "artifact": str(artifact),
            "allowed_channels": ["logion_bundle", "npx_skills"],
        },
        {},
    )
    assert result["selected"] is True
    bad = await _queries().query(
        {
            "type": "resource_distribution_selected",
            "artifact": str(artifact),
            "allowed_channels": ["hf"],
        },
        {},
    )
    assert bad["selected"] is False


class TestInstalledArtifactDigest:
    async def _run(self, artifact: Path, root: Path) -> dict:
        return await _queries().query(
            {
                "type": "installed_artifact_digest_matches",
                "artifact": str(artifact),
                "scope_root": str(root),
            },
            {},
        )

    @pytest.mark.asyncio
    async def test_passes_when_bytes_and_evidence_agree(
        self, tmp_path: Path
    ) -> None:
        root, relative, digest = _installed(tmp_path)
        artifact = _write_envelope(
            tmp_path / "a.json",
            "logion.resources.acquire",
            _receipt(
                content_digest="sha256:aggregate",
                installed_paths=[relative],
                native_evidence={
                    "content_digest": "sha256:aggregate",
                    "file_digests": {relative: digest},
                },
            ),
        )
        assert (await self._run(artifact, root))["digest_matches"] is True

    @pytest.mark.asyncio
    async def test_fails_when_bytes_were_tampered(
        self, tmp_path: Path
    ) -> None:
        root, relative, _ = _installed(tmp_path)
        (root / relative).write_bytes(b"tampered")
        artifact = _write_envelope(
            tmp_path / "a.json",
            "logion.resources.acquire",
            _receipt(
                content_digest="sha256:aggregate",
                installed_paths=[relative],
                native_evidence={
                    "content_digest": "sha256:aggregate",
                    "file_digests": {relative: "1" * 64},
                },
            ),
        )
        assert (await self._run(artifact, root))["digest_matches"] is False

    @pytest.mark.asyncio
    async def test_fails_when_receipt_carries_no_file_digests(
        self, tmp_path: Path
    ) -> None:
        root, relative, _ = _installed(tmp_path)
        artifact = _write_envelope(
            tmp_path / "a.json",
            "logion.resources.acquire",
            _receipt(
                content_digest="sha256:aggregate",
                installed_paths=[relative],
                native_evidence={"content_digest": "sha256:aggregate"},
            ),
        )
        result = await self._run(artifact, root)
        assert result["digest_matches"] is False
        assert "file_digests" in result["reason"]

    @pytest.mark.asyncio
    async def test_fails_when_an_installed_path_is_unpinned(
        self, tmp_path: Path
    ) -> None:
        root, relative, digest = _installed(tmp_path)
        (root / ".agents/skills/x/EXTRA.md").write_bytes(b"extra")
        artifact = _write_envelope(
            tmp_path / "a.json",
            "logion.resources.acquire",
            _receipt(
                content_digest="sha256:aggregate",
                installed_paths=[relative, ".agents/skills/x/EXTRA.md"],
                native_evidence={
                    "content_digest": "sha256:aggregate",
                    "file_digests": {relative: digest},
                },
            ),
        )
        result = await self._run(artifact, root)
        assert result["digest_matches"] is False
        assert "without a recorded digest" in result["reason"]

    @pytest.mark.asyncio
    async def test_fails_when_content_digest_is_an_unrelated_claim(
        self, tmp_path: Path
    ) -> None:
        root, relative, digest = _installed(tmp_path)
        artifact = _write_envelope(
            tmp_path / "a.json",
            "logion.resources.acquire",
            _receipt(
                content_digest="sha256:something-else",
                installed_paths=[relative],
                native_evidence={
                    "content_digest": "sha256:aggregate",
                    "file_digests": {relative: digest},
                },
            ),
        )
        result = await self._run(artifact, root)
        assert result["digest_matches"] is False
        assert "native evidence" in result["reason"]


class TestNativeInstallReconciled:
    async def _run(self, artifact: Path, root: Path, **extra) -> dict:
        return await _queries().query(
            {
                "type": "native_install_reconciled",
                "artifact": str(artifact),
                "scope_root": str(root),
                **extra,
            },
            {},
        )

    def _report(self, tmp_path: Path, **overrides) -> Path:
        data = {
            "matched": [
                {
                    "installation_id": "i1",
                    "channel": "npx_skills",
                    "relative_target_path": ".agents/skills/x",
                }
            ],
            "unresolved": [],
            "ambiguous": [],
            "drifted": [],
        }
        data.update(overrides)
        return _write_envelope(
            tmp_path / "r.json", "logion.resources.reconcile", data
        )

    @pytest.mark.asyncio
    async def test_passes_when_matched_install_is_on_disk(
        self, tmp_path: Path
    ) -> None:
        root, _, _ = _installed(tmp_path)
        result = await self._run(
            self._report(tmp_path), root, expected_channel="npx_skills"
        )
        assert result["reconciled"] is True

    @pytest.mark.asyncio
    async def test_fails_when_matched_install_is_absent(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "repo"
        root.mkdir()
        result = await self._run(self._report(tmp_path), root)
        assert result["reconciled"] is False
        assert "absent from disk" in result["reason"]

    @pytest.mark.asyncio
    async def test_fails_when_the_expected_channel_is_missing(
        self, tmp_path: Path
    ) -> None:
        root, _, _ = _installed(tmp_path)
        result = await self._run(
            self._report(tmp_path), root, expected_channel="logion_bundle"
        )
        assert result["reconciled"] is False
        assert "logion_bundle" in result["reason"]

    @pytest.mark.asyncio
    async def test_fails_when_an_installation_drifted(
        self, tmp_path: Path
    ) -> None:
        root, _, _ = _installed(tmp_path)
        report = self._report(tmp_path, drifted=[{"installation_id": "i2"}])
        result = await self._run(report, root)
        assert result["reconciled"] is False


@pytest.mark.asyncio
async def test_inventory_receipt_matches(tmp_path: Path) -> None:
    report = _write_envelope(
        tmp_path / "r.json",
        "logion.resources.reconcile",
        {
            "matched": [{"installation_id": "i1"}],
            "unresolved": [],
            "ambiguous": [],
            "drifted": [],
        },
    )
    acquire = _write_envelope(
        tmp_path / "a.json", "logion.resources.acquire", _receipt()
    )
    result = await _queries().query(
        {
            "type": "inventory_receipt_matches",
            "artifact": str(report),
            "acquire_artifact": str(acquire),
        },
        {},
    )
    assert result["matches"] is True


class TestAcquisitionIdempotent:
    async def _run(self, first: Path, second: Path, root: Path) -> dict:
        return await _queries().query(
            {
                "type": "acquisition_idempotent",
                "first_artifact": str(first),
                "second_artifact": str(second),
                "scope_root": str(root),
            },
            {},
        )

    @pytest.mark.asyncio
    async def test_passes_for_an_identical_reinstall(
        self, tmp_path: Path
    ) -> None:
        root, relative, _ = _installed(tmp_path)
        payload = _receipt(installed_paths=[relative])
        first = _write_envelope(
            tmp_path / "a.json", "logion.resources.acquire", payload
        )
        second = _write_envelope(
            tmp_path / "b.json", "logion.resources.acquire", payload
        )
        assert (await self._run(first, second, root))["idempotent"] is True

    @pytest.mark.asyncio
    async def test_fails_when_a_second_copy_was_left_behind(
        self, tmp_path: Path
    ) -> None:
        root, relative, _ = _installed(tmp_path)
        (root / ".agents/skills/x.logion-backup").mkdir()
        payload = _receipt(installed_paths=[relative])
        first = _write_envelope(
            tmp_path / "a.json", "logion.resources.acquire", payload
        )
        second = _write_envelope(
            tmp_path / "b.json", "logion.resources.acquire", payload
        )
        result = await self._run(first, second, root)
        assert result["idempotent"] is False
        assert "duplicate install state" in result["reason"]

    @pytest.mark.asyncio
    async def test_fails_when_the_path_set_changed(
        self, tmp_path: Path
    ) -> None:
        root, relative, _ = _installed(tmp_path)
        first = _write_envelope(
            tmp_path / "a.json",
            "logion.resources.acquire",
            _receipt(installed_paths=[relative]),
        )
        second = _write_envelope(
            tmp_path / "b.json",
            "logion.resources.acquire",
            _receipt(installed_paths=[relative, "other"]),
        )
        result = await self._run(first, second, root)
        assert result["idempotent"] is False


class TestInstallDriftReported:
    @pytest.mark.asyncio
    async def test_reports_a_tampered_installation(
        self, tmp_path: Path
    ) -> None:
        report = _write_envelope(
            tmp_path / "r.json",
            "logion.resources.reconcile",
            {
                "matched": [],
                "drifted": [{"installation_id": "i1"}],
                "unresolved": [],
                "ambiguous": [],
            },
        )
        acquire = _write_envelope(
            tmp_path / "a.json", "logion.resources.acquire", _receipt()
        )
        result = await _queries().query(
            {
                "type": "install_drift_reported",
                "artifact": str(report),
                "acquire_artifact": str(acquire),
            },
            {},
        )
        assert result["drift_reported"] is True

    @pytest.mark.asyncio
    async def test_fails_when_a_tampered_install_stays_matched(
        self, tmp_path: Path
    ) -> None:
        report = _write_envelope(
            tmp_path / "r.json",
            "logion.resources.reconcile",
            {
                "matched": [{"installation_id": "i1"}],
                "drifted": [],
                "unresolved": [],
                "ambiguous": [],
            },
        )
        acquire = _write_envelope(
            tmp_path / "a.json", "logion.resources.acquire", _receipt()
        )
        result = await _queries().query(
            {
                "type": "install_drift_reported",
                "artifact": str(report),
                "acquire_artifact": str(acquire),
            },
            {},
        )
        assert result["drift_reported"] is False
        assert "still reported as matched" in result["reason"]


class TestScopeIsolationPreserved:
    def _snapshot(self, tmp_path: Path, roots: list[Path]) -> Path:
        data = {
            str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest()
            for root in roots
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }
        path = tmp_path / "before.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    async def _run(self, snapshot: Path, roots: list[Path]) -> dict:
        return await _queries().query(
            {
                "type": "scope_isolation_preserved",
                "before_snapshot": str(snapshot),
                "protected_roots": [str(root) for root in roots],
            },
            {},
        )

    @pytest.mark.asyncio
    async def test_passes_when_protected_roots_are_untouched(
        self, tmp_path: Path
    ) -> None:
        home = tmp_path / "home"
        (home / ".agents/skills/acme").mkdir(parents=True)
        (home / ".agents/skills/acme/SKILL.md").write_bytes(b"# acme\n")
        snapshot = self._snapshot(tmp_path, [home])
        assert (await self._run(snapshot, [home]))["isolated"] is True

    @pytest.mark.asyncio
    async def test_fails_when_user_scope_gained_a_file(
        self, tmp_path: Path
    ) -> None:
        home = tmp_path / "home"
        (home / ".agents/skills/acme").mkdir(parents=True)
        (home / ".agents/skills/acme/SKILL.md").write_bytes(b"# acme\n")
        snapshot = self._snapshot(tmp_path, [home])
        (home / ".agents/skills/leaked").mkdir()
        (home / ".agents/skills/leaked/SKILL.md").write_bytes(b"# leak\n")
        result = await self._run(snapshot, [home])
        assert result["isolated"] is False
        assert any("leaked" in path for path in result["added"])

    @pytest.mark.asyncio
    async def test_fails_when_a_protected_file_changed(
        self, tmp_path: Path
    ) -> None:
        home = tmp_path / "home"
        (home / ".agents/skills/acme").mkdir(parents=True)
        target = home / ".agents/skills/acme/SKILL.md"
        target.write_bytes(b"# acme\n")
        snapshot = self._snapshot(tmp_path, [home])
        target.write_bytes(b"# overwritten\n")
        result = await self._run(snapshot, [home])
        assert result["isolated"] is False
        assert result["changed"]


def test_acquisition_assertions_are_registered() -> None:
    registry = AssertionRegistry()
    expected = {
        "api.resource_acquisition_exists": ResourceAcquisitionExistsAssertion,
        "api.resource_distribution_selected": (
            ResourceDistributionSelectedAssertion
        ),
        "api.native_install_reconciled": NativeInstallReconciledAssertion,
        "files.inventory_receipt_matches": InventoryReceiptMatchesAssertion,
        "files.installed_artifact_digest_matches": (
            InstalledArtifactDigestMatchesAssertion
        ),
        "api.acquisition_idempotent": AcquisitionIdempotentAssertion,
        "files.install_drift_reported": InstallDriftReportedAssertion,
        "files.scope_isolation_preserved": ScopeIsolationPreservedAssertion,
    }
    for type_, cls in expected.items():
        instance = registry._assertions.get(type_)
        assert instance is not None, type_
        assert isinstance(instance, cls), type_


class _DummyKeys:
    configured = True
