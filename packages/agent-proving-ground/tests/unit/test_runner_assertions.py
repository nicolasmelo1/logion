from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from agent_proving_ground.api_adapters.base import ApiAdapter
from agent_proving_ground.assertions.base import AssertionContext
from agent_proving_ground.assertions.runner import (
    CanaryNotExfiltratedAssertion,
    RunnerEnrolledAssertion,
)
from agent_proving_ground.models import World
from agent_proving_ground.timeline import Timeline


def _ctx(tmp_path: Path) -> AssertionContext:
    class Api:
        name = "test"

    return AssertionContext(
        "runner",
        "collect",
        cast(World, object()),
        cast(ApiAdapter, Api()),
        tmp_path,
        cast(Timeline, None),
    )


def test_runner_enrollment_requires_published_runner_and_credential(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "runner.json"
    manifest.write_text(
        json.dumps({
            "facts": {
                "runner_id": {"ok": True, "value": "r-1"},
                "runner_key_fingerprint": {"ok": True, "value": "abc"},
                "runner_import_root": {"ok": True, "value": "site-packages"},
                "runner_credential_kind": {"ok": True, "value": "runner"},
                "runner_package_version": {"ok": True, "value": "0.2.0"},
            }
        })
    )
    outcome = __import__("asyncio").run(
        RunnerEnrolledAssertion().evaluate(
            _ctx(tmp_path), {"manifest": "runner.json"}
        )
    )
    assert outcome.status == "passed"


def test_canary_assertion_rejects_missing_role(tmp_path: Path) -> None:
    manifest = tmp_path / "runner.json"
    roles = {
        name: {"host_home": False}
        for name in (
            "canary_readable",
            "canary_in_artifacts",
            "canary_in_receipt",
            "canary_in_logs",
        )
    }
    manifest.write_text(
        json.dumps({
            "facts": {
                name: {"ok": True, "value": value}
                for name, value in roles.items()
            }
        })
    )
    outcome = __import__("asyncio").run(
        CanaryNotExfiltratedAssertion().evaluate(
            _ctx(tmp_path), {"manifest": "runner.json"}
        )
    )
    assert outcome.status == "failed"
