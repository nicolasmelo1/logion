"""Tests for courses reviews v1 envelope and summary verb."""

from __future__ import annotations

import argparse
import json
from typing import Any
from unittest.mock import patch

import pytest

from cli.commands.courses._review_helpers import (
    compact_review,
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
        self.calls: list[dict[str, Any]] = []

    def list_reviews(self, **kwargs: Any) -> _FakeListReviewsResult:
        self.calls.append(kwargs)
        return _FakeListReviewsResult(self._reviews, next_cursor=None)


class _FakeV1:
    def __init__(self, courses: _FakeCourses) -> None:
        self.courses = courses


class _FakeClient:
    def __init__(self, v1: _FakeV1) -> None:
        self.v1 = v1

    def close(self) -> None:
        pass


def _make_review(body: str, **overrides: Any) -> dict[str, Any]:
    review = {
        "id": "r1",
        "rating": 5,
        "title": "Great",
        "body": body,
        "reviewer_agent_id": "a1",
        "course_version_id": "v1",
        "created_at": "2025-01-01T00:00:00Z",
        "counts_toward_rating": True,
    }
    review.update(overrides)
    return review


def _make_args(**overrides: Any) -> argparse.Namespace:
    defaults: dict[str, Any] = {
        "course_id": "550e8400-e29b-41d4-a716-446655440000",
        "version": None,
        "limit": 5,
        "json_output": True,
        "api_key": None,
        "base_url": None,
        "timeout": None,
        "max_retries": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_reviews_list_v1_envelope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from cli.main import main

    reviews_data = {
        "reviews": [_make_review("Loved it")],
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
    assert data["data"]["limit"] == 5
    assert data["data"]["items"] == [
        compact_review(reviews_data["reviews"][0])
    ]


def test_reviews_list_default_limit_five() -> None:
    from cli.commands.courses.parser_sections import register_reviews

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_reviews(sub)
    args = parser.parse_args([
        "reviews",
        "list",
        "550e8400-e29b-41d4-a716-446655440000",
    ])

    assert args.limit == 5


def test_reviews_list_truncates_body(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from cli.main import main

    body = "x" * 140

    class FakeCoursesResource:
        def list_reviews(self, **_kw: Any) -> dict[str, Any]:
            return {"reviews": [_make_review(body)], "next_cursor": None}

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
    excerpt = data["data"]["items"][0]["body_excerpt"]
    assert len(excerpt) == 120
    assert excerpt.endswith("…")


def test_reviews_summary_v1_envelope(
    capsys: pytest.CaptureFixture[str],
) -> None:
    reviews = [
        _make_review("one", rating=5),
        _make_review("two", rating=3, id="r2"),
        _make_review("ignored", rating=1, id="r3", counts_toward_rating=False),
    ]
    courses = _FakeCourses(reviews=reviews)
    fake = _FakeClient(v1=_FakeV1(courses=courses))
    args = _make_args()

    with (
        patch(
            "cli.commands.courses.reviews.resolve_config_from_args"
        ) as mock_cfg,
        patch("cli.commands.courses.reviews.make_client", return_value=fake),
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
    assert data["data"]["review_count"] == 2
    assert data["data"]["rating_avg"] == 4.0


def test_reviews_summary_histogram_keys_are_strings_one_to_five(
    capsys: pytest.CaptureFixture[str],
) -> None:
    courses = _FakeCourses(reviews=[_make_review("one", rating=4)])
    fake = _FakeClient(v1=_FakeV1(courses=courses))
    args = _make_args()

    with (
        patch(
            "cli.commands.courses.reviews.resolve_config_from_args"
        ) as mock_cfg,
        patch("cli.commands.courses.reviews.make_client", return_value=fake),
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
    histogram = json.loads(captured.out)["data"]["rating_histogram"]
    assert histogram == {"1": 0, "2": 0, "3": 0, "4": 1, "5": 0}


def test_reviews_summary_handles_zero_reviews(
    capsys: pytest.CaptureFixture[str],
) -> None:
    courses = _FakeCourses(reviews=[])
    fake = _FakeClient(v1=_FakeV1(courses=courses))
    args = _make_args()

    with (
        patch(
            "cli.commands.courses.reviews.resolve_config_from_args"
        ) as mock_cfg,
        patch("cli.commands.courses.reviews.make_client", return_value=fake),
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
    assert data["data"]["review_count"] == 0
    assert data["data"]["rating_avg"] is None
    assert data["data"]["rating_histogram"] == {
        "1": 0,
        "2": 0,
        "3": 0,
        "4": 0,
        "5": 0,
    }


def test_compute_summary_basic() -> None:
    reviews = [
        {"rating": 4, "counts_toward_rating": True},
        {"rating": 2, "counts_toward_rating": True},
        {"rating": 1, "counts_toward_rating": False},
    ]
    result = compute_summary("c1", reviews)
    assert result["review_count"] == 2
    assert result["rating_avg"] == 3.0
    assert result["rating_histogram"] == {
        "1": 0,
        "2": 1,
        "3": 0,
        "4": 1,
        "5": 0,
    }


def test_data_or_model_dump_dict() -> None:
    d = {"key": "value"}
    assert data_or_model_dump(d) == d


def test_data_or_model_dump_pydantic() -> None:
    from pydantic import BaseModel

    class Simple(BaseModel):
        x: int = 1

    assert data_or_model_dump(Simple()) == {"x": 1}
