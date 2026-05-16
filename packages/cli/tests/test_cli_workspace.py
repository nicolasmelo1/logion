"""Tests for workspace commands — local bounty workspace."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli.commands.workspace import (
    UserError,
    has_dirty_files,
    write_json_atomic,
)

# ---------------------------------------------------------------------------
# Helper: invoke the CLI via main()
# ---------------------------------------------------------------------------
from cli.main import main


def _run(argv: list[str]) -> int:
    """Run the CLI with the given argv and return the exit code."""
    return main(argv)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    """Return a fresh workspace root path (not yet initialised)."""
    return tmp_path / "ws"


# ---------------------------------------------------------------------------
# has_dirty_files
# ---------------------------------------------------------------------------


class TestHasDirtyFiles:
    """Tests for ``has_dirty_files``."""

    def test_has_dirty_files_false_empty(self, tmp_path: Path) -> None:
        """An empty directory has no dirty files."""
        d = tmp_path / "empty"
        d.mkdir()
        assert has_dirty_files(d) is False

    def test_has_dirty_files_true_with_file(self, tmp_path: Path) -> None:
        """A directory containing a regular file is dirty."""
        d = tmp_path / "dirty"
        d.mkdir()
        (d / "hello.txt").write_text("hi")
        assert has_dirty_files(d) is True

    def test_has_dirty_files_false_subdirs_only(self, tmp_path: Path) -> None:
        """Directories (no regular files) are not counted as dirty."""
        d = tmp_path / "subdirs"
        d.mkdir()
        (d / "nested").mkdir()
        assert has_dirty_files(d) is False

    def test_has_dirty_files_true_nested(self, tmp_path: Path) -> None:
        """A file nested inside a subdirectory is still dirty."""
        d = tmp_path / "deep"
        d.mkdir()
        sub = d / "sub"
        sub.mkdir()
        (sub / "data.bin").write_bytes(b"\x00")
        assert has_dirty_files(d) is True


# ---------------------------------------------------------------------------
# write_json_atomic
# ---------------------------------------------------------------------------


class TestWriteJsonAtomic:
    """Tests for ``write_json_atomic``."""

    def test_writes_valid_json(self, tmp_path: Path) -> None:
        """Atomic write produces a parseable JSON file."""
        target = tmp_path / "out.json"
        data = {"key": "value", "num": 42}
        write_json_atomic(target, data)
        assert json.loads(target.read_text()) == data

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        """Atomic write replaces any previous content."""
        target = tmp_path / "out.json"
        write_json_atomic(target, {"v": 1})
        write_json_atomic(target, {"v": 2})
        assert json.loads(target.read_text()) == {"v": 2}

    def test_no_temp_left(self, tmp_path: Path) -> None:
        """No .tmp file is left behind after atomic write."""
        target = tmp_path / "out.json"
        write_json_atomic(target, {"x": 1})
        assert not any(p.suffix == ".tmp" for p in tmp_path.iterdir())


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


class TestWorkspaceInit:
    """Tests for ``workspace init``."""

    def test_init_creates_layout(self, ws: Path) -> None:
        """Init creates ``current/``, ``submissions/``, and ``state.json``."""
        rc = _run(["bounties", "workspace", "init", "--path", str(ws)])
        assert rc == 0

        assert (ws / "current").is_dir()
        assert (ws / "submissions").is_dir()
        assert (ws / "state.json").is_file()

        state = json.loads((ws / "state.json").read_text())
        assert state["active_bounty_id"] is None
        assert state["active_submission_id"] is None

    def test_init_refuses_overwrite_without_force(self, ws: Path) -> None:
        """Running init twice without --force returns exit code 2."""
        rc1 = _run(["bounties", "workspace", "init", "--path", str(ws)])
        assert rc1 == 0

        rc2 = _run(["bounties", "workspace", "init", "--path", str(ws)])
        assert rc2 == 2

    def test_init_force_overwrites(self, ws: Path) -> None:
        """Running init with --force succeeds even when state.json exists."""
        _run(["bounties", "workspace", "init", "--path", str(ws)])

        # Modify state so we can verify it was overwritten
        state_path = ws / "state.json"
        state = json.loads(state_path.read_text())
        state["active_bounty_id"] = "should-be-cleared"
        state_path.write_text(json.dumps(state))

        rc = _run(
            ["bounties", "workspace", "init", "--path", str(ws), "--force"],
        )
        assert rc == 0

        new_state = json.loads(state_path.read_text())
        assert new_state["active_bounty_id"] is None


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


class TestWorkspaceStatus:
    """Tests for ``workspace status``."""

    def test_status_shows_state(self, ws: Path) -> None:
        """After init, status prints the workspace state."""
        _run(["bounties", "workspace", "init", "--path", str(ws)])

        rc = _run(["bounties", "workspace", "status", "--workspace", str(ws)])
        assert rc == 0

    def test_status_fails_without_init(self, ws: Path) -> None:
        """Status on an uninitialised workspace returns exit code 2."""
        rc = _run(["bounties", "workspace", "status", "--workspace", str(ws)])
        assert rc == 2


# ---------------------------------------------------------------------------
# checkout
# ---------------------------------------------------------------------------


class TestWorkspaceCheckout:
    """Tests for ``workspace checkout``."""

    def _init_ws(self, ws: Path) -> None:
        """Initialise a workspace directory."""
        _run(["bounties", "workspace", "init", "--path", str(ws)])

    def test_checkout_creates_metadata(self, ws: Path) -> None:
        """Checkout writes metadata.json and updates state.json."""
        self._init_ws(ws)

        rc = _run([
            "bounties",
            "workspace",
            "checkout",
            "bounty-1",
            "sub-1",
            "--workspace",
            str(ws),
        ])
        assert rc == 0

        # Metadata file created
        meta_path = ws / "submissions" / "sub-1" / "metadata.json"
        assert meta_path.is_file()
        meta = json.loads(meta_path.read_text())
        assert meta["bounty_id"] == "bounty-1"
        assert meta["submission_id"] == "sub-1"
        assert meta["remote_status"] == "checked_out"

        # State updated
        state = json.loads((ws / "state.json").read_text())
        assert state["active_bounty_id"] == "bounty-1"
        assert state["active_submission_id"] == "sub-1"

    def test_checkout_refuses_dirty(self, ws: Path) -> None:
        """Checkout without --force fails when current/ has files."""
        self._init_ws(ws)

        # Place a file in current/
        (ws / "current" / "dirty.txt").write_text("oops")

        rc = _run([
            "bounties",
            "workspace",
            "checkout",
            "bounty-1",
            "sub-1",
            "--workspace",
            str(ws),
        ])
        assert rc == 2

    def test_checkout_force_overwrites_dirty(self, ws: Path) -> None:
        """Checkout with --force succeeds even when current/ has files."""
        self._init_ws(ws)

        # Place a file in current/
        (ws / "current" / "dirty.txt").write_text("oops")

        rc = _run([
            "bounties",
            "workspace",
            "checkout",
            "bounty-1",
            "sub-1",
            "--workspace",
            str(ws),
            "--force",
        ])
        assert rc == 0

        # Dirty file was archived (moved into submission)
        state = json.loads((ws / "state.json").read_text())
        assert state["active_bounty_id"] == "bounty-1"


# ---------------------------------------------------------------------------
# switch
# ---------------------------------------------------------------------------


class TestWorkspaceSwitch:
    """Tests for ``workspace switch``."""

    def _init_and_checkout(self, ws: Path) -> None:
        """Initialise workspace and checkout one submission."""
        _run(["bounties", "workspace", "init", "--path", str(ws)])
        _run([
            "bounties",
            "workspace",
            "checkout",
            "bounty-1",
            "sub-1",
            "--workspace",
            str(ws),
        ])

    def test_switch_blocks_dirty(self, ws: Path) -> None:
        """Switch without --force fails when current/ has files."""
        self._init_and_checkout(ws)

        # Add a file to current/ to make it dirty
        (ws / "current" / "work.py").write_text("print('hello')")

        rc = _run([
            "bounties",
            "workspace",
            "switch",
            "bounty-1",
            "sub-2",
            "--workspace",
            str(ws),
        ])
        assert rc == 2

    def test_switch_with_force(self, ws: Path) -> None:
        """Switch with --force clears current/ and
        checks out the new submission."""
        self._init_and_checkout(ws)

        # Add a file to current/ to make it dirty
        (ws / "current" / "work.py").write_text("print('hello')")

        rc = _run([
            "bounties",
            "workspace",
            "switch",
            "bounty-1",
            "sub-2",
            "--workspace",
            str(ws),
            "--force",
        ])
        assert rc == 0

        state = json.loads((ws / "state.json").read_text())
        assert state["active_submission_id"] == "sub-2"


# ---------------------------------------------------------------------------
# evidence
# ---------------------------------------------------------------------------


class TestWorkspaceEvidence:
    """Tests for ``workspace evidence``."""

    def _init_ws(self, ws: Path) -> None:
        """Initialise a workspace directory."""
        _run(["bounties", "workspace", "init", "--path", str(ws)])

    def test_evidence_generates_manifest(self, ws: Path) -> None:
        """Evidence creates evidence.json with a file listing."""
        self._init_ws(ws)
        # Create a file in current/
        (ws / "current" / "proof.txt").write_text("evidence here")

        rc = _run([
            "bounties",
            "workspace",
            "evidence",
            "--workspace",
            str(ws),
        ])
        assert rc == 0

        evidence_path = ws / "evidence.json"
        assert evidence_path.is_file()
        evidence = json.loads(evidence_path.read_text())
        assert "files" in evidence
        assert "generated_at" in evidence
        # Should list our file
        file_paths = [f["path"] for f in evidence["files"]]
        assert "proof.txt" in file_paths

    def test_evidence_custom_output(self, ws: Path) -> None:
        """Evidence --output writes to the specified path."""
        self._init_ws(ws)
        out = ws / "custom_evidence.json"

        rc = _run([
            "bounties",
            "workspace",
            "evidence",
            "--workspace",
            str(ws),
            "--output",
            str(out),
        ])
        assert rc == 0

        assert out.is_file()
        evidence = json.loads(out.read_text())
        assert "generated_at" in evidence

    def test_evidence_fails_without_init(self, ws: Path) -> None:
        """Evidence on an uninitialised workspace returns exit code 2."""
        rc = _run([
            "bounties",
            "workspace",
            "evidence",
            "--workspace",
            str(ws),
        ])
        assert rc == 2


# ---------------------------------------------------------------------------
# UserError
# ---------------------------------------------------------------------------


class TestUserError:
    """Tests for the UserError exception class."""

    def test_user_error_is_exception(self) -> None:
        """UserError is a proper Exception subclass."""
        err = UserError("something went wrong")
        assert isinstance(err, Exception)
        assert str(err) == "something went wrong"
