# SPDX-License-Identifier: MIT
"""Unit tests for Phase 15.9.1 harness scope assertion types."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_proving_ground.api_adapters.mock import MockApiAdapter
from agent_proving_ground.assertions.base import AssertionContext
from agent_proving_ground.assertions.registry import AssertionRegistry
from agent_proving_ground.models import World
from agent_proving_ground.timeline import Timeline


@pytest.fixture
def registry() -> AssertionRegistry:
    return AssertionRegistry()


@pytest.fixture
def ctx(tmp_path: Path) -> AssertionContext:
    adapter = MockApiAdapter()
    world = World(
        run_id="test-run",
        base_url="mock://test",
        root_dir=tmp_path,
    )
    timeline = Timeline(tmp_path / "timeline.jsonl")
    return AssertionContext(
        scenario_name="test",
        phase_id="test-phase",
        world=world,
        api=adapter,
        artifacts_dir=tmp_path,
        timeline=timeline,
    )


class TestHarnessScopeTargetsResolved:
    @pytest.mark.asyncio
    async def test_passes_with_valid_harnesses_and_scopes(self, registry, ctx):
        outcome = await registry.evaluate(
            ctx,
            "api.harness_scope_targets_resolved",
            {
                "harnesses": ["codex", "claude-code", "hermes", "pi"],
                "scopes": [
                    "repo-current",
                    "repo-root",
                    "user",
                    "system",
                ],
            },
        )
        assert outcome.status == "passed"
        assert outcome.evidence.get("resolved") is True

    @pytest.mark.asyncio
    async def test_fails_with_unknown_harness(self, registry, ctx):
        outcome = await registry.evaluate(
            ctx,
            "api.harness_scope_targets_resolved",
            {
                "harnesses": ["unknown-harness"],
                "scopes": ["repo-root"],
            },
        )
        assert outcome.status == "failed"


class TestResourceAcquirePlanDryRun:
    @pytest.mark.asyncio
    async def test_passes_with_valid_plan(self, registry, ctx):
        outcome = await registry.evaluate(
            ctx,
            "api.resource_acquire_plan_dry_run",
            {
                "harness": "codex",
                "scope": "repo-root",
                "zero_write": True,
            },
        )
        assert outcome.status == "passed"
        assert outcome.evidence.get("zero_write") is True
        assert outcome.evidence.get("executable") is False

    @pytest.mark.asyncio
    async def test_unsupported_without_harness(self, registry, ctx):
        outcome = await registry.evaluate(
            ctx,
            "api.resource_acquire_plan_dry_run",
            {"scope": "repo-root"},
        )
        assert outcome.status == "unsupported"

    @pytest.mark.asyncio
    async def test_evidence_includes_executable_and_permissions(
        self, registry, ctx
    ):
        outcome = await registry.evaluate(
            ctx,
            "api.resource_acquire_plan_dry_run",
            {
                "harness": "codex",
                "scope": "repo-root",
                "zero_write": True,
            },
        )
        assert outcome.status == "passed"
        assert "executable" in outcome.evidence
        assert "permissions_required" in outcome.evidence


class TestHarnessScopeNestedRepo:
    @pytest.mark.asyncio
    async def test_passes_with_valid_nested_repo(self, registry, ctx):
        outcome = await registry.evaluate(
            ctx,
            "api.harness_scope_nested_repo",
            {
                "harnesses": ["codex", "claude-code", "pi"],
                "nested_repo": "xpto/nested",
            },
        )
        assert outcome.status == "passed"

    @pytest.mark.asyncio
    async def test_unsupported_without_nested_repo(self, registry, ctx):
        outcome = await registry.evaluate(
            ctx,
            "api.harness_scope_nested_repo",
            {"harnesses": ["codex"]},
        )
        assert outcome.status == "unsupported"


class TestHarnessInventoryDistinctScopes:
    @pytest.mark.asyncio
    async def test_passes_with_harnesses(self, registry, ctx):
        outcome = await registry.evaluate(
            ctx,
            "api.harness_inventory_distinct_scopes",
            {"harnesses": ["codex", "claude-code"]},
        )
        assert outcome.status == "passed"

    @pytest.mark.asyncio
    async def test_unsupported_without_harnesses(self, registry, ctx):
        outcome = await registry.evaluate(
            ctx,
            "api.harness_inventory_distinct_scopes",
            {},
        )
        assert outcome.status == "unsupported"


class TestObservationEnvelopeNoRawData:
    @pytest.mark.asyncio
    async def test_passes(self, registry, ctx):
        outcome = await registry.evaluate(
            ctx,
            "api.observation_envelope_no_raw_data",
            {},
        )
        assert outcome.status == "passed"
