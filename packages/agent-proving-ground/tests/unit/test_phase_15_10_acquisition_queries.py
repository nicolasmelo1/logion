"""Regression tests for the 15.10 acquisition query handlers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from agent_proving_ground.api_adapters._queries import LogionApiQueries
from agent_proving_ground.assertions.api import (
    AcquisitionIdempotentAssertion,
    InstalledArtifactDigestMatchesAssertion,
    InventoryReceiptMatchesAssertion,
    NativeInstallReconciledAssertion,
    ResourceAcquisitionExistsAssertion,
    ResourceDistributionSelectedAssertion,
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


@pytest.mark.asyncio
async def test_resource_acquisition_exists_passes(tmp_path: Path) -> None:
    artifact = _write_envelope(
        tmp_path / "a.json", "logion.resources.acquire", _receipt()
    )
    queries = LogionApiQueries("http://x", _DummyKeys())
    result = await queries.query(
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
    queries = LogionApiQueries("http://x", _DummyKeys())
    result = await queries.query(
        {
            "type": "resource_distribution_selected",
            "artifact": str(artifact),
            "allowed_channels": ["logion_bundle", "npx_skills"],
        },
        {},
    )
    assert result["selected"] is True
    bad = await queries.query(
        {
            "type": "resource_distribution_selected",
            "artifact": str(artifact),
            "allowed_channels": ["hf"],
        },
        {},
    )
    assert bad["selected"] is False


@pytest.mark.asyncio
async def test_installed_artifact_digest_matches(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / ".agents/skills/x").mkdir(parents=True)
    data = b"hello"
    (root / ".agents/skills/x/SKILL.md").write_bytes(data)
    rel = ".agents/skills/x/SKILL.md"
    digest = hashlib.sha256(rel.encode() + b"\0" + data).hexdigest()
    artifact = _write_envelope(
        tmp_path / "a.json",
        "logion.resources.acquire",
        _receipt(content_digest=f"sha256:{digest}", installed_paths=[rel]),
    )
    queries = LogionApiQueries("http://x", _DummyKeys())
    result = await queries.query(
        {
            "type": "installed_artifact_digest_matches",
            "artifact": str(artifact),
            "scope_root": str(root),
        },
        {},
    )
    assert result["digest_matches"] is True
    assert result["computed_digest"] == f"sha256:{digest}"


@pytest.mark.asyncio
async def test_installed_artifact_digest_mismatch_fails(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    (root / ".agents/skills/x").mkdir(parents=True)
    rel = ".agents/skills/x/SKILL.md"
    (root / rel).write_bytes(b"tampered")
    artifact = _write_envelope(
        tmp_path / "a.json",
        "logion.resources.acquire",
        _receipt(content_digest="sha256:" + "0" * 64, installed_paths=[rel]),
    )
    queries = LogionApiQueries("http://x", _DummyKeys())
    result = await queries.query(
        {
            "type": "installed_artifact_digest_matches",
            "artifact": str(artifact),
            "scope_root": str(root),
        },
        {},
    )
    assert result["digest_matches"] is False


@pytest.mark.asyncio
async def test_reconcile_and_idempotency_queries(tmp_path: Path) -> None:
    report = _write_envelope(
        tmp_path / "r.json",
        "logion.resources.reconcile",
        {
            "matched": [{"installation_id": "i1"}],
            "unresolved": [],
            "ambiguous": [],
        },
    )
    acquire = _write_envelope(
        tmp_path / "a.json", "logion.resources.acquire", _receipt()
    )
    second = _write_envelope(
        tmp_path / "b.json", "logion.resources.acquire", _receipt()
    )
    queries = LogionApiQueries("http://x", _DummyKeys())
    rec = await queries.query(
        {
            "type": "native_install_reconciled",
            "artifact": str(report),
            "scope_root": str(tmp_path),
        },
        {},
    )
    assert rec["reconciled"] is True
    match = await queries.query(
        {
            "type": "inventory_receipt_matches",
            "artifact": str(report),
            "acquire_artifact": str(acquire),
        },
        {},
    )
    assert match["matches"] is True
    idem = await queries.query(
        {
            "type": "acquisition_idempotent",
            "first_artifact": str(acquire),
            "second_artifact": str(second),
            "scope_root": str(tmp_path),
        },
        {},
    )
    assert idem["idempotent"] is True


def test_new_assertions_registered() -> None:
    registry = AssertionRegistry()
    for type_ in (
        "api.resource_acquisition_exists",
        "api.resource_distribution_selected",
        "api.native_install_reconciled",
        "files.inventory_receipt_matches",
        "files.installed_artifact_digest_matches",
        "api.acquisition_idempotent",
    ):
        instance = registry._assertions.get(type_)
        assert instance is not None, type_
    assert isinstance(
        registry._assertions["api.resource_acquisition_exists"],
        ResourceAcquisitionExistsAssertion,
    )
    assert isinstance(
        registry._assertions["api.resource_distribution_selected"],
        ResourceDistributionSelectedAssertion,
    )
    assert isinstance(
        registry._assertions["api.native_install_reconciled"],
        NativeInstallReconciledAssertion,
    )
    assert isinstance(
        registry._assertions["files.inventory_receipt_matches"],
        InventoryReceiptMatchesAssertion,
    )
    assert isinstance(
        registry._assertions["files.installed_artifact_digest_matches"],
        InstalledArtifactDigestMatchesAssertion,
    )
    assert isinstance(
        registry._assertions["api.acquisition_idempotent"],
        AcquisitionIdempotentAssertion,
    )


class _DummyKeys:
    configured = True
