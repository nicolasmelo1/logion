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


def test_devrig_clean_removes_copied_companion_directory(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    copied_skill = home / ".codex" / "skills" / "logion"
    copied_skill.mkdir(parents=True)
    (copied_skill / "SKILL.md").write_text(
        "---\nname: logion\n---\n",
        encoding="utf-8",
    )
    symlink_parent = home / ".claude" / "skills"
    symlink_parent.mkdir(parents=True)
    symlink = symlink_parent / "logion"
    symlink.symlink_to(copied_skill, target_is_directory=True)

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "clean"],
        cwd=str(ROOT),
        env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert not copied_skill.exists()
    assert not symlink.exists()
    assert "Removed 2 companion skill paths" in result.stdout
