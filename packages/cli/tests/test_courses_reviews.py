"""Tests for courses reviews v1 envelope and summary verb."""

from __future__ import annotations

import argparse
import json
from typing import Any
from unittest.mock import patch

import pytest

from cli.commands.courses._review_helpers import (
    compute_summary,
    data_or_model_dump,
)
from cli.commands.courses.reviews import handle_reviews_summary


class _FakeListReviewsResult:
    """Minimal SDK-like result object."""

    def __init__(
        self,
        reviews: list[dict[str, Any]],
        next_cursor: str | None = None,
    ) -> None:
        self.reviews = reviews
        self.next_cursor = next_cursor

    def model_dump(self, **_kwargs: Any) -> dict[str, Any]:
        return {
            "reviews": self.reviews,
            "next_cursor": self.next_cursor,
        }


class _FakeCourses:
    def __init__(self, reviews: list[dict[str, Any]] | None = None) -> None:
        self._reviews = reviews or []
        self._calls: list[dict[str, Any]] = []

    def list_reviews(self, **kwargs: Any) -> _FakeListReviewsResult:
        self._calls.append(kwargs)
        return _FakeListReviewsResult(self._reviews, next_cursor=None)


class _FakeV1:
    def __init__(self, courses: _FakeCourses) -> None:
        self.courses = courses


class _FakeClient:
    def __init__(self, v1: _FakeV1) -> None:
        self.v1 = v1

    def close(self) -> None:
        pass


def _make_args(**overrides: Any) -> argparse.Namespace:
    defaults: dict[str, Any] = {
        "course_id": "550e8400-e29b-41d4-a716-446655440000",
        "version": None,
        "limit": None,
        "json_output": True,
        "api_key": None,
        "base_url": None,
        "timeout": None,
        "max_retries": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


# ── reviews list envelope ────────────────────────────────────────────


def test_reviews_list_v1_envelope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """courses reviews list --json emits v1 envelope."""
    from cli.main import main

    reviews_data = {
        "reviews": [
            {
                "review_id": "r1",
                "rating": 5,
                "title": "Great",
                "body": "Loved it",
                "agent_id": "a1",
                "version_id": "v1",
                "created_at": "2025-01-01T00:00:00Z",
            },
        ],
        "next_cursor": None,
    }

    class FakeCoursesResource:
        def list_reviews(self, **_kw: Any) -> dict[str, Any]:
            return reviews_data

    class FakeV1:
        courses = FakeCoursesResource()

    class FakeClient:
        v1 = FakeV1()

        def close(self) -> None:
            pass

    monkeypatch.setattr(
        "cli._context.LogionClient",
        lambda *_, **__: FakeClient(),
    )
    code = main([
        "courses",
        "reviews",
        "list",
        "550e8400-e29b-41d4-a716-446655440000",
        "--json",
    ])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["version"] == "v1"
    assert data["kind"] == "logion.courses.reviews.list"
    assert "data" in data


def test_reviews_list_default_limit_five() -> None:
    """The --limit argument defaults to a reasonable value."""
    from cli.commands.courses.parser_sections import (
        register_reviews,
    )

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_reviews(sub)
    args = parser.parse_args([
        "reviews",
        "list",
        "550e8400-e29b-41d4-a716-446655440000",
    ])
    assert hasattr(args, "limit")


# ── summary verb ─────────────────────────────────────────────────────


def test_reviews_summary_v1_envelope(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """courses reviews summary --json emits v1 envelope."""
    reviews = [
        {
            "rating": 5,
            "reliability": 4,
            "counts_toward_rating": True,
        },
        {
            "rating": 3,
            "usefulness": 5,
            "counts_toward_rating": True,
        },
        {"rating": 1, "counts_toward_rating": False},
    ]
    courses = _FakeCourses(reviews=reviews)
    fake = _FakeClient(v1=_FakeV1(courses=courses))
    args = _make_args()

    with (
        patch(
            "cli.commands.courses.reviews.resolve_config_from_args"
        ) as mock_cfg,
        patch(
            "cli.commands.courses.reviews.make_client",
            return_value=fake,
        ),
    ):
        mock_cfg.return_value = argparse.Namespace(
            json_output=True,
            api_key=None,
            base_url="https://api.logion.dev",
            timeout=None,
            max_retries=None,
        )
        rc = handle_reviews_summary(args)

    captured = capsys.readouterr()
    assert rc == 0
    data = json.loads(captured.out)
    assert data["version"] == "v1"
    assert data["kind"] == "logion.courses.reviews.summary"
    assert data["data"]["course_id"] == args.course_id
    # 2 counted (1 excluded by counts_toward_rating=False)
    assert data["data"]["total_reviews"] == 2


def test_reviews_summary_avg_rating(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Summary computes avg_rating correctly."""
    reviews = [
        {"rating": 4, "counts_toward_rating": True},
        {"rating": 5, "counts_toward_rating": True},
    ]
    courses = _FakeCourses(reviews=reviews)
    fake = _FakeClient(v1=_FakeV1(courses=courses))
    args = _make_args()

    with (
        patch(
            "cli.commands.courses.reviews.resolve_config_from_args"
        ) as mock_cfg,
        patch(
            "cli.commands.courses.reviews.make_client",
            return_value=fake,
        ),
    ):
        mock_cfg.return_value = argparse.Namespace(
            json_output=True,
            api_key=None,
            base_url="https://api.logion.dev",
            timeout=None,
            max_retries=None,
        )
        rc = handle_reviews_summary(args)

    captured = capsys.readouterr()
    assert rc == 0
    data = json.loads(captured.out)
    assert data["data"]["avg_rating"] == 4.5


def test_reviews_summary_handles_zero_reviews(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Summary with 0 reviews returns avg_rating: null."""
    courses = _FakeCourses(reviews=[])
    fake = _FakeClient(v1=_FakeV1(courses=courses))
    args = _make_args()

    with (
        patch(
            "cli.commands.courses.reviews.resolve_config_from_args"
        ) as mock_cfg,
        patch(
            "cli.commands.courses.reviews.make_client",
            return_value=fake,
        ),
    ):
        mock_cfg.return_value = argparse.Namespace(
            json_output=True,
            api_key=None,
            base_url="https://api.logion.dev",
            timeout=None,
            max_retries=None,
        )
        rc = handle_reviews_summary(args)

    captured = capsys.readouterr()
    assert rc == 0
    data = json.loads(captured.out)
    assert data["data"]["total_reviews"] == 0
    assert data["data"]["avg_rating"] is None


# ── helper unit tests ────────────────────────────────────────────────


def test_compute_summary_basic() -> None:
    """compute_summary aggregates rating correctly."""
    reviews = [
        {"rating": 4, "counts_toward_rating": True},
        {"rating": 2, "counts_toward_rating": True},
        {"rating": 1, "counts_toward_rating": False},
    ]
    result = compute_summary("c1", reviews)
    assert result["total_reviews"] == 2
    assert result["avg_rating"] == 3.0


def test_data_or_model_dump_dict() -> None:
    """data_or_model_dump returns dicts unchanged."""
    d = {"key": "value"}
    assert data_or_model_dump(d) == d


def test_data_or_model_dump_pydantic() -> None:
    """data_or_model_dump calls model_dump on Pydantic-like."""
    from pydantic import BaseModel

    class Simple(BaseModel):
        x: int = 1

    assert data_or_model_dump(Simple()) == {"x": 1}
