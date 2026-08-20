"""Tests for the local hook that reconciles the agent's native install.

The hook exists because this step was flaky when an agent owned it, so it
is now on the path of a gate. A broken hook fails the phase every time
instead of one run in four, which is better and still worth catching here
rather than after a real run has been spent.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(
    "packages/agent-proving-ground/scripts/reconcile_native_inventory.py"
).resolve()

ENVELOPE = {
    "version": "v1",
    "kind": "logion.resources.reconcile",
    "data": {
        "matched": [
            {
                "channel": "npx_skills",
                "relative_target_path": ".claude/skills/find-skills",
            }
        ],
        "ambiguous": [],
        "unresolved": [],
        "drifted": [],
    },
}


def _fake_cli(tmp_path: Path, *, stdout: str, exit_code: int = 0) -> Path:
    """A stand-in ``logion`` that records the argv it was given."""
    cli = tmp_path / "logion"
    cli.write_text(
        "#!/bin/sh\n"
        f"printf \"%s\" '{stdout}' \n"
        f'env > "{tmp_path}/cli.env"\n'
        f'printf "%s\\n" "$@" > "{tmp_path}/cli.argv"\n'
        f"exit {exit_code}\n",
        encoding="utf-8",
    )
    cli.chmod(0o755)
    return cli


def _run(
    tmp_path: Path, cli: Path, **overrides: str
) -> subprocess.CompletedProcess[str]:
    keys = tmp_path / "role-keys.json"
    keys.write_text(json.dumps({"buyer": {"api_key": "k-buyer"}}))
    root = tmp_path / "repo"
    root.mkdir(exist_ok=True)
    evidence = tmp_path / "evidence"
    home = tmp_path / "logion-home"
    home.mkdir(exist_ok=True)
    args = {
        "--cli": str(cli),
        "--cwd": str(root),
        "--evidence-dir": str(evidence),
        "--logion-home": str(home),
        "--harness": "claude-code",
        "--base-url": "http://localhost:8000",
        **overrides,
    }
    argv = [sys.executable, str(HOOK)]
    for flag, value in args.items():
        argv += [flag, value]
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "LOGION_PROVING_GROUND_ROLE_KEYS_FILE": str(keys),
        },
    )


def test_writes_the_cli_output_untouched_and_captures_its_path(
    tmp_path: Path,
) -> None:
    cli = _fake_cli(tmp_path, stdout=json.dumps(ENVELOPE))
    proc = _run(tmp_path, cli)

    assert proc.returncode == 0, proc.stderr
    captured = json.loads(proc.stdout.strip().splitlines()[-1])
    artifact = Path(captured["reconcile_artifact"])
    # Byte-identical: the assertion downstream reads a v1 envelope, and a
    # reformat here would be the same class of defect the hook removes.
    assert artifact.read_text(encoding="utf-8") == json.dumps(ENVELOPE)


def test_runs_the_reconcile_the_scenario_asks_for(tmp_path: Path) -> None:
    cli = _fake_cli(tmp_path, stdout=json.dumps(ENVELOPE))
    _run(tmp_path, cli, **{"--scope": "repo-root", "--from": "skills"})

    argv = (tmp_path / "cli.argv").read_text(encoding="utf-8").split("\n")
    assert argv[:2] == ["resources", "reconcile"]
    for flag, value in (
        ("--from", "skills"),
        ("--harness", "claude-code"),
        ("--scope", "repo-root"),
    ):
        assert argv[argv.index(flag) + 1] == value
    # Not --dry-run: the receipt this creates is what links the observation
    # to a resource in the phases that follow.
    assert "--dry-run" not in argv
    assert "--json" in argv


def test_passes_the_role_key_and_home_to_the_cli(tmp_path: Path) -> None:
    cli = _fake_cli(tmp_path, stdout=json.dumps(ENVELOPE))
    _run(tmp_path, cli)

    env = dict(
        line.split("=", 1)
        for line in (tmp_path / "cli.env")
        .read_text(encoding="utf-8")
        .splitlines()
        if "=" in line
    )
    assert env["LOGION_API_KEY"] == "k-buyer"
    assert env["LOGION_HOME"] == str(tmp_path / "logion-home")
    assert env["LOGION_BASE_URL"] == "http://localhost:8000"


def test_keeps_the_evidence_when_the_reconcile_fails(tmp_path: Path) -> None:
    cli = _fake_cli(tmp_path, stdout='{"partial": true}', exit_code=3)
    proc = _run(tmp_path, cli)

    assert proc.returncode != 0
    assert "exited 3" in proc.stderr
    artifact = tmp_path / "evidence" / "reconcile-xpto.json"
    assert artifact.read_text(encoding="utf-8") == '{"partial": true}'


def test_names_a_missing_cli_instead_of_blaming_the_reconcile(
    tmp_path: Path,
) -> None:
    proc = _run(tmp_path, tmp_path / "absent-logion")

    assert proc.returncode != 0
    assert "no installed CLI" in proc.stderr


def test_requires_a_role_key_store(tmp_path: Path) -> None:
    cli = _fake_cli(tmp_path, stdout=json.dumps(ENVELOPE))
    argv = [
        sys.executable,
        str(HOOK),
        "--cli",
        str(cli),
        "--cwd",
        str(tmp_path),
        "--evidence-dir",
        str(tmp_path / "evidence"),
        "--logion-home",
        str(tmp_path),
        "--harness",
        "claude-code",
        "--base-url",
        "http://localhost:8000",
    ]
    env = {
        key: value
        for key, value in os.environ.items()
        if key != "LOGION_PROVING_GROUND_ROLE_KEYS_FILE"
    }
    proc = subprocess.run(argv, capture_output=True, text=True, env=env)

    assert proc.returncode != 0
    assert "ROLE_KEYS_FILE" in proc.stderr
