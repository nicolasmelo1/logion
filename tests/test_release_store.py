# SPDX-License-Identifier: MIT
"""Tests for release_store.py CompanionStorePublisher."""

from __future__ import annotations

import io
import json
import tarfile
from collections.abc import Sequence
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from scripts.release_store import (
    BUNDLE_TARBALL_NAME,
    CompanionStorePublisher,
    SubprocessRunner,
)

COMPANION_UUID = "5ddf32c6-e139-4056-ac94-c4a231bfd932"
VERSION = "0.1.6"


class _RecordingRunner:
    """CommandRunner that records every call without executing."""

    def __init__(self, outputs: list[str] | None = None) -> None:
        self.calls: list[list[str]] = []
        self._outputs = outputs or []

    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Path | None = None,  # noqa: ARG002
    ) -> CompletedProcess[str]:
        self.calls.append(list(args))
        stdout = self._outputs.pop(0) if self._outputs else ""
        return CompletedProcess(
            args=list(args),
            returncode=0,
            stdout=stdout,
            stderr="",
        )


def _make_tarball(path: Path, files: dict[str, str]) -> None:
    """Create a tar.gz with the given file contents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w:gz") as tar:
        for name, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    return root


@pytest.fixture
def tarball(repo_root: Path) -> Path:
    """Create a companion tarball in dist/."""
    dist = repo_root / "dist"
    tarball_path = dist / BUNDLE_TARBALL_NAME.format(version=VERSION)
    _make_tarball(
        tarball_path,
        {"SKILL.md": "# Companion\n", "course/intro.md": "intro\n"},
    )
    return tarball_path


def test_store_publish_plan_preserves_bundle_paths(
    repo_root: Path, tarball: Path
) -> None:
    """Plan has correct tarball and extracted-dir paths."""
    publisher = CompanionStorePublisher(
        repo_root=repo_root, runner=_RecordingRunner()
    )
    plan = publisher.build_plan(VERSION, COMPANION_UUID)
    assert plan.bundle_tarball == tarball
    # extracted_dir uses the tarball name (minus .tar.gz suffixes),
    # not the bare version string.
    expected_extract_name = tarball.name
    for _suffix in tarball.suffixes:
        expected_extract_name = expected_extract_name.rsplit(".", 1)[0]
    assert plan.extracted_dir == (
        repo_root / "dist" / f"companion-extract-{expected_extract_name}"
    )
    assert plan.version == VERSION
    assert plan.course_id == COMPANION_UUID
    names = [s.upload_path for s in plan.upload_files]
    assert "SKILL.md" in names
    assert "course/intro.md" in names


def test_store_publish_plan_strips_tarball_root_for_upload(
    repo_root: Path,
) -> None:
    """Upload paths are rooted at the course bundle, not the tar prefix."""
    dist = repo_root / "dist"
    tarball_path = dist / BUNDLE_TARBALL_NAME.format(version=VERSION)
    bundle_root = f"logion-marketplace-companion-{VERSION}"
    _make_tarball(
        tarball_path,
        {
            f"{bundle_root}/SKILL.md": "---\nlicense: MIT\n---\n",
            f"{bundle_root}/LICENSE": "MIT License\n",
            f"{bundle_root}/course/capabilities.yaml": "version: 1\n",
            f"{bundle_root}/references/troubleshooting.md": "ref\n",
        },
    )

    publisher = CompanionStorePublisher(
        repo_root=repo_root, runner=_RecordingRunner()
    )
    plan = publisher.build_plan(VERSION, COMPANION_UUID)

    specs = {spec.upload_path: spec.local_path for spec in plan.upload_files}
    assert "SKILL.md" in specs
    assert "LICENSE" in specs
    assert "course/capabilities.yaml" in specs
    assert "references/troubleshooting.md" in specs
    assert all(not path.startswith(f"{bundle_root}/") for path in specs)
    assert specs["LICENSE"] == (plan.extracted_dir / bundle_root / "LICENSE")


def test_store_publish_requires_existing_tarball(
    repo_root: Path,
) -> None:
    """Missing tarball raises FileNotFoundError."""
    publisher = CompanionStorePublisher(
        repo_root=repo_root, runner=_RecordingRunner()
    )
    with pytest.raises(FileNotFoundError, match="Bundle tarball"):
        publisher.build_plan(VERSION, COMPANION_UUID)


def test_store_publish_uses_course_uuid(
    repo_root: Path,
    tarball: Path,  # noqa: ARG001
) -> None:
    """course_id in the plan is the companion UUID."""
    publisher = CompanionStorePublisher(
        repo_root=repo_root, runner=_RecordingRunner()
    )
    plan = publisher.build_plan(VERSION, COMPANION_UUID)
    assert plan.course_id == COMPANION_UUID


def test_store_publish_rejects_non_uuid_course_id(
    repo_root: Path,
    tarball: Path,  # noqa: ARG001
) -> None:
    """Non-UUID course_id raises ValueError."""
    publisher = CompanionStorePublisher(
        repo_root=repo_root, runner=_RecordingRunner()
    )
    with pytest.raises(ValueError, match="UUID"):
        publisher.build_plan(VERSION, "not-a-uuid")


def test_store_publish_requests_publication_after_upload(
    repo_root: Path,
    tarball: Path,  # noqa: ARG001
) -> None:
    """Publication request is in the command flow."""
    runner = _RecordingRunner(
        outputs=[
            "",
            json.dumps(
                {
                    "version": "v1",
                    "kind": "logion.courses.uploads.create",
                    "data": {
                        "course_id": COMPANION_UUID,
                        "version_id": ("11111111-2222-3333-4444-555555555555"),
                        "uploads": [],
                    },
                },
            ),
            "",
            "",
            "",
            "",
        ]
    )
    publisher = CompanionStorePublisher(repo_root=repo_root, runner=runner)
    result = publisher.publish(VERSION, COMPANION_UUID)
    assert result["dry_run"] is False
    last_call = runner.calls[-1]
    assert "publication" in last_call
    assert "request" in last_call
    assert COMPANION_UUID in last_call
    session_file = (
        repo_root
        / "dist"
        / "upload-session-11111111-2222-3333-4444-555555555555.json"
    )
    assert (
        json.loads(session_file.read_text(encoding="utf-8"))["version_id"]
        == "11111111-2222-3333-4444-555555555555"
    )


def test_store_publish_extracts_text_version_id_not_course_id(
    repo_root: Path,
    tarball: Path,  # noqa: ARG001
) -> None:
    """Human output parser must not confuse course_id with version_id."""
    version_id = "11111111-2222-3333-4444-555555555555"
    runner = _RecordingRunner(
        outputs=[
            "",
            f"course_id: {COMPANION_UUID}\nversion_id: {version_id}\n",
            "",
            "",
            "",
            "",
        ]
    )
    publisher = CompanionStorePublisher(repo_root=repo_root, runner=runner)
    publisher.publish(VERSION, COMPANION_UUID)
    push_call = next(call for call in runner.calls if "push" in call)
    assert version_id in push_call
    assert (
        str(repo_root / "dist" / f"upload-session-{version_id}.json")
        in push_call
    )


def test_store_publish_dry_run_prints_commands_only(
    repo_root: Path,
    tarball: Path,  # noqa: ARG001
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Dry run doesn't execute commands."""
    runner = _RecordingRunner()
    publisher = CompanionStorePublisher(repo_root=repo_root, runner=runner)
    result = publisher.publish(VERSION, COMPANION_UUID, dry_run=True)
    assert result["dry_run"] is True
    assert isinstance(result["commands"], list)
    assert len(runner.calls) == 0, "dry run must not call runner"
    captured = capsys.readouterr()
    assert len(captured.out) > 0


def test_store_publish_dry_run_includes_publication_command(
    repo_root: Path,
    tarball: Path,  # noqa: ARG001
) -> None:
    """Dry run command list includes the publication request."""
    runner = _RecordingRunner()
    publisher = CompanionStorePublisher(repo_root=repo_root, runner=runner)
    result = publisher.publish(VERSION, COMPANION_UUID, dry_run=True)
    commands: list[str] = list(
        result["commands"]  # type: ignore[arg-type]
    )
    pub_cmds = [c for c in commands if "publication" in c]
    assert len(pub_cmds) == 1
    assert "request" in pub_cmds[0]
    assert COMPANION_UUID in pub_cmds[0]


def test_subprocess_runner_is_command_runner() -> None:
    """SubprocessRunner satisfies the CommandRunner protocol."""
    runner = SubprocessRunner()
    assert hasattr(runner, "run")
