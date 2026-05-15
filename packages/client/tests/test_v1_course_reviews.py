"""Tests for CourseReviewsResource — human review queue management."""

from __future__ import annotations

from unittest.mock import MagicMock

from logion._http import HttpClient
from logion.v1._resources.course_reviews import CourseReviewsResource
from logion.v1._types.generated.v1 import (
    ApproveHumanReviewResponse,
    GetHumanReviewDetailResponse,
    ListHumanReviewQueueResponse,
    RejectHumanReviewResponse,
)


class TestCourseReviewsResource:
    """Tests for all 4 methods of CourseReviewsResource."""

    def test_list_calls_request_model_with_params(
        self,
    ) -> None:
        """list() sends GET /v1/course-reviews with limit+cursor."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=ListHumanReviewQueueResponse)
        http.request_model.return_value = mock_resp
        resource = CourseReviewsResource(http)
        resource.list(limit=10, cursor="abc123")
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1] == "/v1/course-reviews"
        assert call_args.args[2] == ListHumanReviewQueueResponse
        params = call_args.kwargs["params"]
        assert params["limit"] == 10
        assert params["cursor"] == "abc123"

    def test_list_without_params(self) -> None:
        """list() with no params sends empty params dict."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=ListHumanReviewQueueResponse)
        http.request_model.return_value = mock_resp
        resource = CourseReviewsResource(http)
        resource.list()
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        params = call_args.kwargs["params"]
        assert params == {}

    def test_get_calls_request_model(self) -> None:
        """get() sends GET /v1/course-reviews/{review_id}."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=GetHumanReviewDetailResponse)
        http.request_model.return_value = mock_resp
        resource = CourseReviewsResource(http)
        resource.get(review_id="review-1")
        http.request_model.assert_called_once_with(
            "GET",
            "/v1/course-reviews/review-1",
            GetHumanReviewDetailResponse,
        )

    def test_approve_sends_patch_with_body(self) -> None:
        """approve() sends PATCH .../approval with body."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=ApproveHumanReviewResponse)
        http.request_model.return_value = mock_resp
        resource = CourseReviewsResource(http)
        resource.approve(
            review_id="review-1",
            reviewer_notes="Looks good",
        )
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "PATCH"
        assert call_args.args[1] == "/v1/course-reviews/review-1/approval"
        assert call_args.args[2] == ApproveHumanReviewResponse
        json_body = call_args.kwargs["json"]
        assert json_body["reviewer_notes"] == "Looks good"

    def test_approve_without_notes(self) -> None:
        """approve() without notes omits reviewer_notes from
        body (exclude_none)."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=ApproveHumanReviewResponse)
        http.request_model.return_value = mock_resp
        resource = CourseReviewsResource(http)
        resource.approve(review_id="review-1")
        call_args = http.request_model.call_args
        json_body = call_args.kwargs["json"]
        assert "reviewer_notes" not in json_body

    def test_reject_sends_patch_with_body(self) -> None:
        """reject() sends PATCH .../rejection with required
        fields."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=RejectHumanReviewResponse)
        http.request_model.return_value = mock_resp
        resource = CourseReviewsResource(http)
        resource.reject(
            review_id="review-1",
            decision_reason="quality",
            reviewer_notes="Does not meet standards",
        )
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "PATCH"
        assert call_args.args[1] == "/v1/course-reviews/review-1/rejection"
        assert call_args.args[2] == RejectHumanReviewResponse
        json_body = call_args.kwargs["json"]
        assert json_body["decision_reason"] == "quality"
        assert json_body["reviewer_notes"] == ("Does not meet standards")
