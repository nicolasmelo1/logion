from __future__ import annotations

from logion_agent_proving_ground.cli import main


def test_validate_builtin_skill_report_contract() -> None:
    assert main(["validate", "builtin:skill_report_contract"]) == 0


def test_run_writes_report_and_assertions(tmp_path) -> None:
    out = tmp_path / "run"
    main([
        "run",
        "builtin:skill_report_contract",
        "--api-adapter",
        "mock",
        "--agent-driver",
        "scripted",
        "--out",
        str(out),
    ])
    assert out.exists()
    assert (out / "run.json").exists()
    assert (out / "timeline.jsonl").exists()
