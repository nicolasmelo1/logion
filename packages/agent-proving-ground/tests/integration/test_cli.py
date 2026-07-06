from __future__ import annotations

import json

from agent_proving_ground import cli
from agent_proving_ground.cli import main


def test_validate_builtin_skill_report_contract() -> None:
    assert main(["validate", "builtin:skill_report_contract"]) == 0


def test_run_writes_report_and_assertions(tmp_path) -> None:
    out = tmp_path / "run"
    exit_code = main([
        "run",
        "builtin:skill_report_contract",
        "--api-adapter",
        "mock",
        "--agent-driver",
        "scripted",
        "--out",
        str(out),
    ])
    assert exit_code == 1
    assert out.exists()
    assert (out / "run.json").exists()
    assert (out / "timeline.jsonl").exists()


def test_run_id_matches_auto_created_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cli, "DEFAULT_RUNS_ROOT", tmp_path)
    exit_code = main([
        "run",
        "builtin:skill_report_contract",
        "--api-adapter",
        "mock",
        "--agent-driver",
        "scripted",
    ])
    assert exit_code == 1
    run_dirs = [path for path in tmp_path.iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    run_json = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    report_json = json.loads(
        (run_dir / "report.json").read_text(encoding="utf-8")
    )
    assert run_json["run_id"] == run_dir.name
    assert report_json["run_id"] == run_dir.name
