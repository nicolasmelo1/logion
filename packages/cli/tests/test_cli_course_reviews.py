# SPDX-License-Identifier: MIT
"""Tests for the course-reviews commands."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from cli.main import main


class FakeDownloadResponse:
    """Fake streamed HTTP response for bundle downloads."""

    def __init__(self, body: bytes = b"bundle") -> None:
        self.body = body

    def __enter__(self) -> FakeDownloadResponse:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_bytes(self) -> Iterator[bytes]:
        yield self.body


class FakeStreamClient:
    """Fake httpx client — streams presigned bundle URLs only.

    The bundle manifest now comes from the SDK (``get_bundle``); raw
    httpx is used solely to stream each file's presigned ``download_url``.
    """

    def __enter__(self) -> FakeStreamClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def stream(self, method: str, url: str) -> FakeDownloadResponse:
        assert method == "GET"
        return FakeDownloadResponse(f"downloaded:{url}".encode())


class FakeCourseReviewsResource:
    """Fake course_reviews resource."""

    def __init__(self) -> None:
        self.last_call: tuple[str, dict[str, Any]] = ("", {})
        self.bundle_files: list[dict[str, str]] = []

    def list(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("list", kwargs)
        return {
            "items": [
                {
                    "review_id": "r-001",
                    "course_id": "c-001",
                    "course_title": "Test Course",
                    "owner_agent_id": "a-001",
                    "submitted_at": "2026-01-01T00:00:00Z",
                    "review_status": "human_review",
                    "course_status": "auto_review",
                    "finding_count": 3,
                    "has_snyk": False,
                    "capabilities_status": "mismatch_found",
                    "capability_risk_score": 8,
                    "capability_mismatch_count": 2,
                },
            ],
            "next_cursor": None,
        }

    def get(self, review_id: str, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("get", {"review_id": review_id, **kwargs})
        return {
            "review_id": review_id,
            "course_id": "c-001",
            "course_title": "Test Course",
            "version_id": "v-001",
            "review_status": "human_review",
            "course_status": "auto_review",
            "owner_agent_id": "a-001",
            "submitted_at": "2026-01-01T00:00:00Z",
            "initiated_by": "a-002",
            "completed_at": None,
            "reviewed_by_user_id": None,
            "reviewed_at": None,
            "reviewer_notes": None,
            "decision_reason": None,
            "snyk_project_id": None,
            "snyk_scan_url": None,
            "capabilities_status": "mismatch_found",
            "declared_capabilities": {
                "version": 1,
                "tools": ["terminal"],
                "network": {"allow_domains": ["docs.python.org"]},
            },
            "observed_capabilities": {
                "tools": ["terminal", "web"],
                "network_hosts": ["api.openai.com"],
                "filesystem_write": [],
                "secrets_env": [],
                "dangerous_commands_detected": False,
            },
            "capability_mismatches": [
                {
                    "code": "network_domain_not_declared",
                    "severity": "high",
                    "observed": "api.openai.com",
                    "declared": ["docs.python.org"],
                    "message": "Observed outbound domain was not declared.",
                },
                {
                    "code": "tool_not_declared",
                    "severity": "medium",
                    "observed": "web",
                    "declared": ["terminal"],
                    "message": "Observed tool 'web' was not declared.",
                },
            ],
            "capability_risk_score": 8,
            "findings_by_layer": {},
        }

    def approve(self, review_id: str, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("approve", {"review_id": review_id, **kwargs})
        return {"id": review_id, "status": "approved"}

    def reject(self, review_id: str, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("reject", {"review_id": review_id, **kwargs})
        return {"id": review_id, "status": "rejected"}

    def get_bundle(self, review_id: str, **kwargs: Any) -> SimpleNamespace:
        self.last_call = ("get_bundle", {"review_id": review_id, **kwargs})
        return SimpleNamespace(
            review_id=review_id,
            files=[SimpleNamespace(**f) for f in self.bundle_files],
        )


class FakeV1Namespace:
    def __init__(self, course_reviews: FakeCourseReviewsResource) -> None:
        self.course_reviews = course_reviews


class FakeClient:
    def __init__(self, v1: FakeV1Namespace) -> None:
        self.v1 = v1

    def close(self) -> None:
        pass


def _patch_client(monkeypatch: pytest.MonkeyPatch, fake: FakeClient) -> None:
    monkeypatch.setattr("cli._context.LogionClient", lambda **_: fake)


def test_course_reviews_list(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """course-reviews list calls SDK."""
    cr = FakeCourseReviewsResource()
    fake = FakeClient(v1=FakeV1Namespace(course_reviews=cr))
    _patch_client(monkeypatch, fake)
    code = main([
        "course-reviews",
        "list",
        "--limit",
        "10",
        "--json",
    ])
    assert code == 0
    method, kwargs = cr.last_call
    assert method == "list"
    assert kwargs["limit"] == 10
    data = json.loads(capsys.readouterr().out)
    assert "items" in data


def test_course_reviews_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """course-reviews get calls SDK."""
    cr = FakeCourseReviewsResource()
    fake = FakeClient(v1=FakeV1Namespace(course_reviews=cr))
    _patch_client(monkeypatch, fake)
    code = main([
        "course-reviews",
        "get",
        "770e8400-e29b-41d4-a716-446655440002",
        "--json",
    ])
    assert code == 0
    method, kwargs = cr.last_call
    assert method == "get"
    assert kwargs["review_id"] == "770e8400-e29b-41d4-a716-446655440002"


def test_course_reviews_approve_with_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """course-reviews approve --yes calls SDK."""
    cr = FakeCourseReviewsResource()
    fake = FakeClient(v1=FakeV1Namespace(course_reviews=cr))
    _patch_client(monkeypatch, fake)
    code = main([
        "course-reviews",
        "approve",
        "770e8400-e29b-41d4-a716-446655440002",
        "--reviewer-notes",
        "Looks good",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = cr.last_call
    assert method == "approve"
    assert kwargs["review_id"] == "770e8400-e29b-41d4-a716-446655440002"
    assert kwargs["reviewer_notes"] == "Looks good"


def test_course_reviews_approve_whitespace_reviewer_notes() -> None:
    """course-reviews approve rejects whitespace-only reviewer notes."""
    code = main([
        "course-reviews",
        "approve",
        "770e8400-e29b-41d4-a716-446655440002",
        "--reviewer-notes",
        "   ",
        "--yes",
    ])
    assert code == 2


def test_course_reviews_approve_without_yes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """course-reviews approve without --yes refuses."""
    code = main([
        "course-reviews",
        "approve",
        "770e8400-e29b-41d4-a716-446655440002",
    ])
    assert code == 2
    stderr = capsys.readouterr().err
    assert "Re-run with --yes to approve this review." in stderr


def test_course_reviews_reject_with_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """course-reviews reject --yes calls SDK."""
    cr = FakeCourseReviewsResource()
    fake = FakeClient(v1=FakeV1Namespace(course_reviews=cr))
    _patch_client(monkeypatch, fake)
    code = main([
        "course-reviews",
        "reject",
        "770e8400-e29b-41d4-a716-446655440002",
        "--decision-reason",
        "unsafe command",
        "--reviewer-notes",
        "Contains risky command",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = cr.last_call
    assert method == "reject"
    assert kwargs["review_id"] == "770e8400-e29b-41d4-a716-446655440002"
    assert kwargs["decision_reason"] == "unsafe command"
    assert kwargs["reviewer_notes"] == "Contains risky command"


def test_course_reviews_reject_without_yes(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """course-reviews reject without --yes refuses."""
    code = main([
        "course-reviews",
        "reject",
        "770e8400-e29b-41d4-a716-446655440002",
        "--decision-reason",
        "bad",
        "--reviewer-notes",
        "nope",
    ])
    assert code == 2
    stderr = capsys.readouterr().err
    assert "Re-run with --yes to reject this review." in stderr


@pytest.mark.parametrize(
    ("args", "expected_message"),
    [
        (
            [
                "course-reviews",
                "reject",
                "770e8400-e29b-41d4-a716-446655440002",
                "--decision-reason",
                "   ",
                "--reviewer-notes",
                "has notes",
                "--yes",
            ],
            "Error: --decision-reason must not be empty.",
        ),
        (
            [
                "course-reviews",
                "reject",
                "770e8400-e29b-41d4-a716-446655440002",
                "--decision-reason",
                "unsafe command",
                "--reviewer-notes",
                "   ",
                "--yes",
            ],
            "Error: --reviewer-notes must not be empty.",
        ),
    ],
)
def test_course_reviews_reject_whitespace_validation(
    args: list[str],
    expected_message: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """course-reviews reject rejects whitespace-only required text fields."""
    code = main(args)
    assert code == 2
    assert expected_message in capsys.readouterr().err


def test_course_reviews_approve_empty_id() -> None:
    """course-reviews approve rejects empty review_id."""
    code = main([
        "course-reviews",
        "approve",
        "",
        "--yes",
        "--json",
    ])
    assert code == 2


def test_course_reviews_reject_empty_id() -> None:
    """course-reviews reject rejects empty review_id."""
    code = main([
        "course-reviews",
        "reject",
        "",
        "--decision-reason",
        "bad",
        "--reviewer-notes",
        "nope",
        "--yes",
        "--json",
    ])
    assert code == 2


def test_course_reviews_get_empty_id() -> None:
    """course-reviews get rejects empty review_id."""
    code = main(["course-reviews", "get", "", "--json"])
    assert code == 2


def test_course_reviews_get_invalid_uuid() -> None:
    """course-reviews get rejects an invalid UUID."""
    code = main(["course-reviews", "get", "not-a-uuid", "--json"])
    assert code == 2


def test_course_reviews_download_writes_bundle_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """course-reviews download streams files into the target directory."""
    files = [
        {"filename": "SKILL.md", "download_url": "https://files/SKILL.md"},
        {
            "filename": "references/guide.md",
            "download_url": "https://files/guide.md",
        },
    ]
    cr = FakeCourseReviewsResource()
    cr.bundle_files = files
    _patch_client(monkeypatch, FakeClient(v1=FakeV1Namespace(cr)))
    monkeypatch.setattr(
        "httpx.Client",
        lambda **_: FakeStreamClient(),
    )

    target = tmp_path / "review"
    code = main([
        "course-reviews",
        "download",
        "770e8400-e29b-41d4-a716-446655440002",
        "--target",
        str(target),
        "--api-key",
        "test-key",
    ])

    assert code == 0
    assert (
        target / "SKILL.md"
    ).read_bytes() == b"downloaded:https://files/SKILL.md"
    assert (target / "references" / "guide.md").read_bytes() == (
        b"downloaded:https://files/guide.md"
    )
    assert "Downloaded 2 file(s)" in capsys.readouterr().out


def test_course_reviews_download_refuses_path_escape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """course-reviews download rejects bundle filenames outside target."""
    files = [
        {
            "filename": "../escape.txt",
            "download_url": "https://files/escape.txt",
        },
    ]
    cr = FakeCourseReviewsResource()
    cr.bundle_files = files
    _patch_client(monkeypatch, FakeClient(v1=FakeV1Namespace(cr)))
    monkeypatch.setattr(
        "httpx.Client",
        lambda **_: FakeStreamClient(),
    )

    target = tmp_path / "review"
    code = main([
        "course-reviews",
        "download",
        "770e8400-e29b-41d4-a716-446655440002",
        "--target",
        str(target),
        "--api-key",
        "test-key",
    ])

    assert code == 1
    assert not (tmp_path / "escape.txt").exists()
    assert "refusing path escape" in capsys.readouterr().err


def test_course_reviews_approve_invalid_uuid() -> None:
    """course-reviews approve rejects an invalid UUID."""
    code = main([
        "course-reviews",
        "approve",
        "not-a-uuid",
        "--reviewer-notes",
        "ok",
        "--yes",
        "--json",
    ])
    assert code == 2


def test_course_reviews_reject_invalid_uuid() -> None:
    """course-reviews reject rejects an invalid UUID."""
    code = main([
        "course-reviews",
        "reject",
        "not-a-uuid",
        "--decision-reason",
        "bad",
        "--reviewer-notes",
        "nope",
        "--yes",
        "--json",
    ])
    assert code == 2


def test_course_reviews_list_capability_fields(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """course-reviews list prints mismatch count and risk score."""
    cr = FakeCourseReviewsResource()
    fake = FakeClient(v1=FakeV1Namespace(course_reviews=cr))
    _patch_client(monkeypatch, fake)
    code = main(["course-reviews", "list"])
    assert code == 0
    out = capsys.readouterr().out
    assert "capabilities_status: mismatch_found" in out
    assert "capability_risk_score: 8" in out
    assert "capability_mismatch_count: 2" in out


def test_course_reviews_get_json_capability_fields(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """course-reviews get --json preserves capability payloads."""
    cr = FakeCourseReviewsResource()
    fake = FakeClient(v1=FakeV1Namespace(course_reviews=cr))
    _patch_client(monkeypatch, fake)
    code = main([
        "course-reviews",
        "get",
        "770e8400-e29b-41d4-a716-446655440002",
        "--json",
    ])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["capabilities_status"] == "mismatch_found"
    assert data["capability_risk_score"] == 8
    assert len(data["capability_mismatches"]) == 2
    assert data["declared_capabilities"]["tools"] == ["terminal"]
    assert "web" in data["observed_capabilities"]["tools"]


def test_course_reviews_get_human_capability_evidence(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """course-reviews get human output groups mismatch evidence clearly."""
    cr = FakeCourseReviewsResource()
    fake = FakeClient(v1=FakeV1Namespace(course_reviews=cr))
    _patch_client(monkeypatch, fake)
    code = main([
        "course-reviews",
        "get",
        "770e8400-e29b-41d4-a716-446655440002",
    ])
    assert code == 0
    out = capsys.readouterr().out
    assert "capabilities_status: mismatch_found" in out
    assert "capability_risk_score: 8" in out
    assert "high: network_domain_not_declared" in out
    assert "medium: tool_not_declared" in out


def test_course_reviews_approve_forwards_acknowledge_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """course-reviews approve --acknowledge-capability-mismatches
    forwards flag."""
    cr = FakeCourseReviewsResource()
    fake = FakeClient(v1=FakeV1Namespace(course_reviews=cr))
    _patch_client(monkeypatch, fake)
    code = main([
        "course-reviews",
        "approve",
        "770e8400-e29b-41d4-a716-446655440002",
        "--reviewer-notes",
        "Acknowledged",
        "--acknowledge-capability-mismatches",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = cr.last_call
    assert method == "approve"
    assert kwargs["acknowledge_capability_mismatches"] is True


def test_course_reviews_approve_without_acknowledge_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """course-reviews approve without
    --acknowledge-capability-mismatches omits flag."""
    cr = FakeCourseReviewsResource()
    fake = FakeClient(v1=FakeV1Namespace(course_reviews=cr))
    _patch_client(monkeypatch, fake)
    code = main([
        "course-reviews",
        "approve",
        "770e8400-e29b-41d4-a716-446655440002",
        "--reviewer-notes",
        "OK",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = cr.last_call
    assert method == "approve"
    assert "acknowledge_capability_mismatches" not in kwargs


def test_course_reviews_reject_forwards_capability_reason_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """course-reviews reject --capability-reason-code forwards code."""
    cr = FakeCourseReviewsResource()
    fake = FakeClient(v1=FakeV1Namespace(course_reviews=cr))
    _patch_client(monkeypatch, fake)
    code = main([
        "course-reviews",
        "reject",
        "770e8400-e29b-41d4-a716-446655440002",
        "--decision-reason",
        "capability mismatch",
        "--reviewer-notes",
        "Network domain not declared",
        "--capability-reason-code",
        "network_domain_not_declared",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = cr.last_call
    assert method == "reject"
    assert kwargs["capability_reason_code"] == "network_domain_not_declared"


def test_course_reviews_reject_without_capability_reason_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """course-reviews reject without --capability-reason-code omits code."""
    cr = FakeCourseReviewsResource()
    fake = FakeClient(v1=FakeV1Namespace(course_reviews=cr))
    _patch_client(monkeypatch, fake)
    code = main([
        "course-reviews",
        "reject",
        "770e8400-e29b-41d4-a716-446655440002",
        "--decision-reason",
        "other issue",
        "--reviewer-notes",
        "Not capability related",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = cr.last_call
    assert method == "reject"
    assert kwargs.get("capability_reason_code") is None
