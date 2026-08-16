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

from cli.commands.courses import _uploads_push, _uploads_transfer
from cli.main import main


@pytest.fixture
def course_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def version_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def bundle(tmp_path: Path) -> dict[str, Path]:
    """Create a tiny valid on-disk course bundle."""
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\nname: demo\nlicense: MIT\n---\n# Demo\n",
        encoding="utf-8",
    )
    license_file = tmp_path / "LICENSE"
    license_file.write_text("MIT test license\n", encoding="utf-8")
    course_dir = tmp_path / "course"
    course_dir.mkdir()
    capabilities = course_dir / "capabilities.yaml"
    capabilities.write_text(
        "version: 1\nsummary: demo\ntools:\n  - file\n",
        encoding="utf-8",
    )
    return {
        "SKILL.md": skill,
        "LICENSE": license_file,
        "course/capabilities.yaml": capabilities,
    }


class _FakeCoursesResource:
    def __init__(self, price_cents: int = 0) -> None:
        self.price_cents = price_cents

    def get(self, **_kwargs: Any) -> dict[str, Any]:
        return {"price_cents": self.price_cents}


class _FakeClient:
    def __init__(self, price_cents: int = 0) -> None:
        self.v1 = type(
            "_V1",
            (),
            {"courses": _FakeCoursesResource(price_cents=price_cents)},
        )()

    def close(self) -> None:
        pass


def _patch_client(
    monkeypatch: pytest.MonkeyPatch, *, price_cents: int = 0
) -> None:
    monkeypatch.setattr(
        "cli.commands.courses._uploads_push.make_client",
        lambda _config: _FakeClient(price_cents=price_cents),
    )


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
        _patch_client(monkeypatch)
        _patch_httpx_seq(
            monkeypatch,
            [_FakeResponse(200), _FakeResponse(200), _FakeResponse(200)],
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
            "--file",
            f"LICENSE={bundle['LICENSE']}",
            "--file",
            f"course/capabilities.yaml={bundle['course/capabilities.yaml']}",
        ])
        out = capsys.readouterr()
        assert rc == 0
        assert "Pushed 3/3 files" in out.out

    def test_push_unwraps_v1_envelope(
        self,
        tmp_path: Path,
        course_id: str,
        version_id: str,
        bundle: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """Session JSON from ``uploads create --json`` is wrapped in a
        ``{"version": "v1", "kind": "...", "data": {...}}`` envelope.
        The push command must unwrap it to reach the ``uploads`` list."""
        inner = _make_session(course_id, version_id, bundle)
        envelope = {
            "version": "v1",
            "kind": "logion.courses.uploads.create",
            "data": inner,
        }
        session_path = tmp_path / "session.json"
        session_path.write_text(json.dumps(envelope), encoding="utf-8")
        _patch_client(monkeypatch)
        _patch_httpx_seq(
            monkeypatch,
            [_FakeResponse(200), _FakeResponse(200), _FakeResponse(200)],
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
            "--file",
            f"LICENSE={bundle['LICENSE']}",
            "--file",
            f"course/capabilities.yaml={bundle['course/capabilities.yaml']}",
        ])
        out = capsys.readouterr()
        assert rc == 0
        assert "Pushed 3/3 files" in out.out


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
        assert "LICENSE" in captured.err

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

    def test_paid_course_requires_logion_license(
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
        _patch_client(monkeypatch, price_cents=2500)

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
            f"LICENSE={bundle['LICENSE']}",
            "--file",
            (f"course/capabilities.yaml={bundle['course/capabilities.yaml']}"),
        ])
        captured = capsys.readouterr()
        assert rc == _uploads_push.EXIT_BAD_ARGS
        assert "paid courses must ship" in captured.err


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
        _patch_client(monkeypatch)
        monkeypatch.setattr(
            _uploads_push,
            "validate_bundle_files_for_upload",
            lambda **_kwargs: (True, None),
        )

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
        _patch_client(monkeypatch)
        monkeypatch.setattr(
            _uploads_push,
            "validate_bundle_files_for_upload",
            lambda **_kwargs: (True, None),
        )

        # Two 503s then a 200.
        calls = _patch_httpx_seq(
            monkeypatch,
            [_FakeResponse(503), _FakeResponse(503), _FakeResponse(200)],
        )
        # Skip the linear-backoff sleep so the test stays fast.
        monkeypatch.setattr(_uploads_transfer.time, "sleep", lambda _s: None)

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
