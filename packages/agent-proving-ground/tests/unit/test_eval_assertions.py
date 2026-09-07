"""Regression tests for phase-16.1 evidence checks."""

import json
from pathlib import Path

from agent_proving_ground.api_adapters.mock import MockApiAdapter
from agent_proving_ground.assertions.base import AssertionContext
from agent_proving_ground.assertions.evals import _check, _manifest
from agent_proving_ground.models import World
from agent_proving_ground.timeline import Timeline


def _fact(value: object) -> dict[str, object]:
    return {"ok": True, "value": value}


def _context(root: Path) -> AssertionContext:
    return AssertionContext(
        scenario_name="eval-contract-reference-runner",
        phase_id="collect-evidence",
        world=World(run_id="r1", base_url="http://mock", root_dir=root),
        api=MockApiAdapter(),
        artifacts_dir=root,
        timeline=Timeline(root / "timeline.jsonl"),
    )


def test_manifest_normalizes_an_absolute_symlinked_artifact_path(
    tmp_path: Path,
) -> None:
    real_root = tmp_path / "real"
    real_root.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real_root, target_is_directory=True)
    manifest = real_root / "evidence.json"
    manifest.write_text(json.dumps({"files.eval_contract_valid": {}}))

    loaded = _manifest(
        _context(real_root), {"manifest": str(alias / manifest.name)}
    )

    assert loaded == {"files.eval_contract_valid": {}}


def test_role_scoped_expected_value_is_checked_per_role() -> None:
    facts: dict[str, object] = {
        "terminal_status": _fact({
            "run_one": "succeeded",
            "run_two": "succeeded",
        })
    }

    passed, _, errors = _check(
        facts,
        ("terminal_status",),
        {"terminal_status": "succeeded"},
        ("run_one", "run_two"),
    )

    assert passed is True
    assert errors == ""


def test_role_scoped_expected_value_rejects_one_bad_role() -> None:
    facts: dict[str, object] = {"http_status": _fact({"one": 422, "two": 500})}

    passed, _, errors = _check(
        facts, ("http_status",), {"http_status": 422}, ("one", "two")
    )

    assert passed is False
    assert errors == "http_status"
