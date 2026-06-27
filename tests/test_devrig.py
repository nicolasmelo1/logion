# SPDX-License-Identifier: MIT
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "devrig.py"


def test_devrig_env_writes_mock_defaults(tmp_path: Path) -> None:
    env_file = tmp_path / "devrig.env"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "env",
            "--mode",
            "mock",
            "--write",
            str(env_file),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    text = env_file.read_text(encoding="utf-8")
    assert "LOGION_DEVRIG_MODE=mock" in text
    assert "LOGION_BASE_URL=http://127.0.0.1:4010" in text


def test_devrig_doctor_reports_missing_env(tmp_path: Path) -> None:
    env_file = tmp_path / "missing.env"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "doctor",
            "--env-file",
            str(env_file),
            "--agent",
            "codex",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "missing" in result.stdout
