"""The factory gate must not inherit an unrelated sf from the shell."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "pinned_sf", ROOT / "scripts" / "sf.py"
)
assert SPEC is not None
assert SPEC.loader is not None
sf = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sf)


def installation(path: Path, revision: str = sf.REVISION) -> Path:
    binary = path / "bin" / "sf"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\nexit 23\n")
    binary.chmod(0o755)
    (path / ".crates.toml").write_text(
        f'[v1]\n"sf 0.2.0 '
        f'(git+{sf.SOURCE}?rev={revision}#{revision})" = ["sf"]\n'
    )
    (path / "verified.json").write_text(
        json.dumps({"revision": revision, "sha256": sf.digest(binary)})
    )
    return binary


def test_path_sf_cannot_override_pinned_binary(tmp_path, monkeypatch):
    impostor = tmp_path / "sf"
    marker = tmp_path / "path-sf-ran"
    impostor.write_text(f"#!/bin/sh\ntouch '{marker}'\nexit 0\n")
    impostor.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    install = tmp_path / "pinned"
    installation(install)
    monkeypatch.setattr(sf, "INSTALL", install)
    monkeypatch.setattr(sys, "argv", ["sf.py", "check", "--allow-commands"])
    assert sf.main() == 23
    assert not marker.exists()


@pytest.mark.parametrize(
    "damage", ["revision", "binary", "receipt", "metadata", "symlink"]
)
def test_unverifiable_installation_fails_closed(tmp_path, monkeypatch, damage):
    install = tmp_path / "pinned"
    binary = installation(
        install, "0" * 40 if damage == "revision" else sf.REVISION
    )
    if damage == "binary":
        binary.write_text("#!/bin/sh\nexit 0\n")
    elif damage == "receipt":
        (install / "verified.json").unlink()
    elif damage == "metadata":
        (install / ".crates.toml").write_text("not valid TOML")
    elif damage == "symlink":
        target = tmp_path / "replacement"
        binary.rename(target)
        binary.symlink_to(target)
    monkeypatch.setattr(sf, "INSTALL", install)

    def forbidden_run(*_args, **_kwargs):
        pytest.fail("unverified sf must never execute or silently reinstall")

    monkeypatch.setattr(subprocess, "run", forbidden_run)
    assert sf.main() == 1


def test_install_uses_exact_revision_and_isolated_root(tmp_path, monkeypatch):
    install = tmp_path / "pinned"
    calls = []

    def cargo_run(command, **kwargs):
        calls.append(command)
        assert kwargs == {"check": True}
        installation(install)
        (install / "verified.json").unlink()

    monkeypatch.setattr(subprocess, "run", cargo_run)
    assert sf.ensure_installed(install) == install / "bin" / "sf"
    assert calls == [
        [
            "cargo",
            "install",
            "--git",
            sf.SOURCE,
            "--rev",
            sf.REVISION,
            "--locked",
            "--root",
            str(install),
            "--bin",
            "sf",
        ]
    ]
    sf.ensure_installed(install)
    assert len(calls) == 1


def test_failed_install_never_falls_back_to_path(tmp_path, monkeypatch):
    monkeypatch.setattr(sf, "INSTALL", tmp_path / "pinned")
    calls = []

    def failing_cargo(command, **_kwargs):
        calls.append(command)
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(subprocess, "run", failing_cargo)
    assert sf.main() == 1
    assert len(calls) == 1
    assert calls[0][0] == "cargo"


def test_ci_and_make_share_launcher_and_command_permission():
    makefile = (ROOT / "Makefile").read_text()
    assert "python3 scripts/sf.py verify --allow-commands" in makefile
    assert "python3 scripts/sf.py check --allow-commands" in makefile
    workflow = (ROOT / ".github/workflows/pr-safety.yml").read_text()
    assert "run: make factory-check" in workflow
    assert "run: sf " not in workflow
    assert "cargo install" not in workflow


def test_actor_goal_requirement_keeps_its_documented_reason():
    docs = (ROOT / "docs/factory-rules.md").read_text()
    section = docs.split("### L3.EVERY_ACTOR_HAS_A_GOAL\n", 1)[1].split(
        "\n## ", 1
    )[0]
    assert "each agent that declares a `driver`" in section
    assert "whose `goal` is non-empty" in section
    assert "**Why.**" in section
    assert "**Fix.**" in section
    assert "scripts/allowed_mute_actors.txt" in section
