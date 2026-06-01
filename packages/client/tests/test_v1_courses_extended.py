# SPDX-License-Identifier: MIT
"""Tests for extended CoursesResource methods — reviews and publication."""

from __future__ import annotations

from unittest.mock import MagicMock

from logion._http import HttpClient
from logion.v1._resources.courses import CoursesResource
from logion.v1._types.generated.v1 import (
    CompleteCourseVersionUploadSessionResponse,
    GetCourseReviewFeedbackResponse,
    GetMyCourseReviewResponse,
    GetReviewStatusResponse,
    ListCourseReviewsResponse,
    RequestPublicationResponse,
    UpsertCourseReviewResponse,
)


class TestCoursesResourceExtended:
    """Tests for new review/publication methods of CoursesResource."""

    def test_review_version_sends_put_with_body(self) -> None:
        """review_version() sends PUT .../review with rating+optional
        fields."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=UpsertCourseReviewResponse)
        http.request_model.return_value = mock_resp
        resource = CoursesResource(http)
        resource.review_version(
            course_id="course-1",
            version_id="version-1",
            rating=4,
            body="Great course",
            reliability=4.5,
            usefulness=3.8,
        )
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "PUT"
        assert (
            call_args.args[1]
            == "/v1/courses/course-1/versions/version-1/review"
        )
        assert call_args.args[2] == UpsertCourseReviewResponse
        json_body = call_args.kwargs["json"]
        assert json_body["rating"] == 4
        assert json_body["body"] == "Great course"
        assert json_body["reliability"] == 4.5
        assert json_body["usefulness"] == 3.8

    def test_review_version_minimal(self) -> None:
        """review_version() with only required rating omits
        optional fields."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=UpsertCourseReviewResponse)
        http.request_model.return_value = mock_resp
        resource = CoursesResource(http)
        resource.review_version(
            course_id="course-1",
            version_id="version-1",
            rating=5,
        )
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        json_body = call_args.kwargs["json"]
        assert json_body["rating"] == 5
        assert "body" not in json_body
        assert "reliability" not in json_body
        assert "usefulness" not in json_body

    def test_complete_upload_session_calls_request_model(
        self,
    ) -> None:
        """complete_upload_session() sends PATCH .../upload-session."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(
            spec=CompleteCourseVersionUploadSessionResponse,
        )
        http.request_model.return_value = mock_resp
        resource = CoursesResource(http)
        resource.complete_upload_session(
            course_id="course-1",
            version_id="version-1",
        )
        http.request_model.assert_called_once_with(
            "PATCH",
            "/v1/courses/course-1/versions/version-1/upload-session",
            CompleteCourseVersionUploadSessionResponse,
        )

    def test_get_review_feedback_calls_request_model(
        self,
    ) -> None:
        """get_review_feedback() sends GET .../review-feedback."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(
            spec=GetCourseReviewFeedbackResponse,
        )
        http.request_model.return_value = mock_resp
        resource = CoursesResource(http)
        resource.get_review_feedback(course_id="course-1")
        http.request_model.assert_called_once_with(
            "GET",
            "/v1/courses/course-1/review-feedback",
            GetCourseReviewFeedbackResponse,
        )

    def test_list_reviews_with_params(self) -> None:
        """list_reviews() sends GET .../reviews with params."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=ListCourseReviewsResponse)
        http.request_model.return_value = mock_resp
        resource = CoursesResource(http)
        resource.list_reviews(
            course_id="course-1",
            version="latest",
            limit=10,
            cursor="next-page",
        )
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1] == "/v1/courses/course-1/reviews"
        assert call_args.args[2] == ListCourseReviewsResponse
        params = call_args.kwargs["params"]
        assert params["version"] == "latest"
        assert params["limit"] == 10
        assert params["cursor"] == "next-page"

    def test_list_reviews_without_params(self) -> None:
        """list_reviews() with no optional params sends empty
        params dict."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=ListCourseReviewsResponse)
        http.request_model.return_value = mock_resp
        resource = CoursesResource(http)
        resource.list_reviews(course_id="course-1")
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        params = call_args.kwargs["params"]
        assert params == {}

    def test_get_my_review_with_version_id(self) -> None:
        """get_my_review() sends GET .../my-review with
        version_id param."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=GetMyCourseReviewResponse)
        http.request_model.return_value = mock_resp
        resource = CoursesResource(http)
        resource.get_my_review(
            course_id="course-1",
            version_id="version-1",
        )
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1] == "/v1/courses/course-1/my-review"
        assert call_args.args[2] == GetMyCourseReviewResponse
        params = call_args.kwargs["params"]
        assert params["version_id"] == "version-1"

    def test_get_my_review_without_version_id(self) -> None:
        """get_my_review() without version_id sends empty params."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=GetMyCourseReviewResponse)
        http.request_model.return_value = mock_resp
        resource = CoursesResource(http)
        resource.get_my_review(course_id="course-1")
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        params = call_args.kwargs["params"]
        assert params == {}

    def test_request_publication_review_calls_request_model(
        self,
    ) -> None:
        """request_publication_review() sends POST
        .../publication-reviews."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=RequestPublicationResponse)
        http.request_model.return_value = mock_resp
        resource = CoursesResource(http)
        resource.request_publication_review(
            course_id="course-1",
        )
        http.request_model.assert_called_once_with(
            "POST",
            "/v1/courses/course-1/publication-reviews",
            RequestPublicationResponse,
        )

    def test_get_latest_publication_review_with_params(
        self,
    ) -> None:
        """get_latest_publication_review() sends GET
        .../publication-reviews/latest with params."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=GetReviewStatusResponse)
        http.request_model.return_value = mock_resp
        resource = CoursesResource(http)
        resource.get_latest_publication_review(
            course_id="course-1",
            include_pass=True,
        )
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "GET"
        assert (
            call_args.args[1]
            == "/v1/courses/course-1/publication-reviews/latest"
        )
        assert call_args.args[2] == GetReviewStatusResponse
        params = call_args.kwargs["params"]
        assert params["include_pass"] is True

    def test_get_latest_publication_review_without_params(
        self,
    ) -> None:
        """get_latest_publication_review() without include_pass
        sends empty params."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=GetReviewStatusResponse)
        http.request_model.return_value = mock_resp
        resource = CoursesResource(http)
        resource.get_latest_publication_review(
            course_id="course-1",
        )
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        params = call_args.kwargs["params"]
        assert params == {}
