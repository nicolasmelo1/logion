# SPDX-License-Identifier: MIT
"""Tests for ``logion courses uploads push``.

Covers the happy path, validation failures (missing files, session
mismatch, malformed JSON), retry/backoff on transient errors, and the
4xx-aborts-immediately contract.  HTTP is faked via a monkeypatch on
``httpx.request`` so no network calls are made.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from cli.commands.courses import _uploads_push
from cli.main import main


@pytest.fixture
def course_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def version_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def bundle(tmp_path: Path) -> dict[str, Path]:
    """Create a tiny on-disk bundle: SKILL.md and one reference."""
    skill = tmp_path / "SKILL.md"
    skill.write_text("body", encoding="utf-8")
    ref = tmp_path / "references"
    ref.mkdir()
    usage = ref / "usage.md"
    usage.write_text("how to use", encoding="utf-8")
    return {"SKILL.md": skill, "references/usage.md": usage}


def _make_session(
    course_id: str,
    version_id: str,
    files: dict[str, Path],
) -> dict[str, Any]:
    """Build a session-JSON payload shaped like create_upload_session."""
    return {
        "course_id": course_id,
        "version_id": version_id,
        "session_id": str(uuid.uuid4()),
        "expires_at": "2099-01-01T00:00:00Z",
        "version_number": 1,
        "uploads": [
            {
                "asset_id": str(uuid.uuid4()),
                "filename": upload_path,
                "method": "PUT",
                "put_url": f"https://example.invalid/{upload_path}",
                "required_headers": {"Content-Type": "text/plain"},
                "s3_key": f"s3-key/{upload_path}",
            }
            for upload_path in files
        ],
    }


class _FakeResponse:
    def __init__(self, status: int, text: str = "") -> None:
        self.status_code = status
        self.text = text


def _patch_httpx_seq(monkeypatch: pytest.MonkeyPatch, responses: list) -> list:
    """Patch httpx.request with a queued list of responses or exceptions.

    Returns a list of (url, method) tuples populated as calls happen so
    tests can assert what was sent.
    """
    import httpx

    seq = list(responses)
    calls: list[tuple[str, str]] = []

    def fake(method: str, url: str, **_kw: Any) -> _FakeResponse:
        calls.append((url, method))
        result = seq.pop(0)
        if isinstance(result, Exception):
            raise result
        return result  # type: ignore[return-value]

    monkeypatch.setattr(httpx, "request", fake)
    return calls


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_push_all_files_succeeds(
        self,
        tmp_path: Path,
        course_id: str,
        version_id: str,
        bundle: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        session = _make_session(course_id, version_id, bundle)
        session_path = tmp_path / "session.json"
        session_path.write_text(json.dumps(session), encoding="utf-8")

        _patch_httpx_seq(monkeypatch, [_FakeResponse(200), _FakeResponse(200)])

        rc = main([
            "courses",
            "uploads",
            "push",
            course_id,
            version_id,
            "--session-file",
            str(session_path),
            "--file",
            f"SKILL.md={bundle['SKILL.md']}",
            "--file",
            f"references/usage.md={bundle['references/usage.md']}",
        ])
        out = capsys.readouterr()
        assert rc == 0
        assert "Pushed 2/2 files" in out.out


# ---------------------------------------------------------------------------
# Validation failures
# ---------------------------------------------------------------------------


class TestValidation:
    def test_missing_local_file_for_session_entry(
        self,
        tmp_path: Path,
        course_id: str,
        version_id: str,
        bundle: dict[str, Path],
        capsys: pytest.CaptureFixture,
    ) -> None:
        session = _make_session(course_id, version_id, bundle)
        session_path = tmp_path / "session.json"
        session_path.write_text(json.dumps(session), encoding="utf-8")

        rc = main([
            "courses",
            "uploads",
            "push",
            course_id,
            version_id,
            "--session-file",
            str(session_path),
            # Only one of the two session entries is provided.
            "--file",
            f"SKILL.md={bundle['SKILL.md']}",
        ])
        captured = capsys.readouterr()
        assert rc == _uploads_push.EXIT_MISSING_FILES
        assert "references/usage.md" in captured.err

    def test_session_mismatch_course(
        self,
        tmp_path: Path,
        course_id: str,
        version_id: str,
        bundle: dict[str, Path],
        capsys: pytest.CaptureFixture,
    ) -> None:
        # Build session under a *different* course_id.
        other = str(uuid.uuid4())
        session = _make_session(other, version_id, bundle)
        session_path = tmp_path / "session.json"
        session_path.write_text(json.dumps(session), encoding="utf-8")

        rc = main([
            "courses",
            "uploads",
            "push",
            course_id,
            version_id,
            "--session-file",
            str(session_path),
            "--file",
            f"SKILL.md={bundle['SKILL.md']}",
        ])
        captured = capsys.readouterr()
        assert rc == _uploads_push.EXIT_SESSION_MISMATCH
        assert "session is for course" in captured.err

    def test_bad_session_json(
        self,
        tmp_path: Path,
        course_id: str,
        version_id: str,
        bundle: dict[str, Path],
        capsys: pytest.CaptureFixture,
    ) -> None:
        session_path = tmp_path / "session.json"
        session_path.write_text("{not json", encoding="utf-8")

        rc = main([
            "courses",
            "uploads",
            "push",
            course_id,
            version_id,
            "--session-file",
            str(session_path),
            "--file",
            f"SKILL.md={bundle['SKILL.md']}",
        ])
        captured = capsys.readouterr()
        assert rc == _uploads_push.EXIT_BAD_ARGS
        assert "not valid JSON" in captured.err


# ---------------------------------------------------------------------------
# Retry semantics
# ---------------------------------------------------------------------------


class TestRetries:
    def test_4xx_aborts_immediately(
        self,
        tmp_path: Path,
        course_id: str,
        version_id: str,
        bundle: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        session = _make_session(
            course_id, version_id, {"SKILL.md": bundle["SKILL.md"]}
        )
        session_path = tmp_path / "session.json"
        session_path.write_text(json.dumps(session), encoding="utf-8")

        # First call: 403.  Must NOT be retried.
        calls = _patch_httpx_seq(
            monkeypatch, [_FakeResponse(403, "access denied")]
        )

        rc = main([
            "courses",
            "uploads",
            "push",
            course_id,
            version_id,
            "--session-file",
            str(session_path),
            "--file",
            f"SKILL.md={bundle['SKILL.md']}",
        ])
        captured = capsys.readouterr()
        assert rc == _uploads_push.EXIT_UPLOAD_FAILED
        assert len(calls) == 1
        assert "HTTP 403" in captured.out

    def test_5xx_retries_then_succeeds(
        self,
        tmp_path: Path,
        course_id: str,
        version_id: str,
        bundle: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        session = _make_session(
            course_id, version_id, {"SKILL.md": bundle["SKILL.md"]}
        )
        session_path = tmp_path / "session.json"
        session_path.write_text(json.dumps(session), encoding="utf-8")

        # Two 503s then a 200.
        calls = _patch_httpx_seq(
            monkeypatch,
            [_FakeResponse(503), _FakeResponse(503), _FakeResponse(200)],
        )
        # Skip the linear-backoff sleep so the test stays fast.
        monkeypatch.setattr(_uploads_push.time, "sleep", lambda _s: None)

        rc = main([
            "courses",
            "uploads",
            "push",
            course_id,
            version_id,
            "--session-file",
            str(session_path),
            "--file",
            f"SKILL.md={bundle['SKILL.md']}",
            "--max-retries",
            "3",
        ])
        assert rc == 0
        assert len(calls) == 3
