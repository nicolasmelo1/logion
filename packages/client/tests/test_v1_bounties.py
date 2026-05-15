"""Tests for BountiesResource — bounty creation and management."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from logion._http import HttpClient
from logion.v1._resources.bounties import BountiesResource
from logion.v1._types.generated.v1 import (
    AcceptBountySubmissionResponse,
    CancelBountyResponse,
    CreateBountyPayoutResponse,
    CreateBountyResponse,
    CreateBountySubmissionResponse,
    FundBountyResponse,
    GetBountyResponse,
    GetBountySubmissionResponse,
    OpenBountyResponse,
    RejectBountySubmissionResponse,
    WithdrawBountySubmissionResponse,
)


class TestBountiesResource:
    """Tests for all 13 methods of BountiesResource."""

    def test_create_sends_post_with_body(self) -> None:
        """create() sends POST /v1/bounties with required+optional fields."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=CreateBountyResponse)
        http.request_model.return_value = mock_resp
        resource = BountiesResource(http)
        resource.create(
            course_id="11111111-1111-1111-1111-111111111111",
            title="Test Bounty",
            description="A test bounty",
            reward_amount_cents=5000,
            currency="USD",
        )
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1] == "/v1/bounties"
        assert call_args.args[2] == CreateBountyResponse
        json_body = call_args.kwargs["json"]
        assert json_body["title"] == "Test Bounty"
        assert json_body["description"] == "A test bounty"
        assert json_body["reward_amount_cents"] == 5000

    def test_list_calls_request_with_params(self) -> None:
        """list() calls GET /v1/bounties with scope param."""
        http = MagicMock(spec=HttpClient)
        http.request.return_value = []
        resource = BountiesResource(http)
        resource.list(scope="mine")
        http.request.assert_called_once()
        call_args = http.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1] == "/v1/bounties"
        params = call_args.kwargs["params"]
        assert params["scope"] == "mine"

    def test_list_without_params(self) -> None:
        """list() with no params sends empty params dict."""
        http = MagicMock(spec=HttpClient)
        http.request.return_value = []
        resource = BountiesResource(http)
        resource.list()
        http.request.assert_called_once()
        call_args = http.request.call_args
        params = call_args.kwargs["params"]
        assert params == {}

    def test_list_invalid_scope_raises_value_error(self) -> None:
        """list() with invalid scope raises ValueError."""
        http = MagicMock(spec=HttpClient)
        resource = BountiesResource(http)
        with pytest.raises(ValueError, match="Invalid scope"):
            resource.list(scope="invalid")

    def test_get_calls_request_model(self) -> None:
        """get() sends GET /v1/bounties/{bounty_id}."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=GetBountyResponse)
        http.request_model.return_value = mock_resp
        resource = BountiesResource(http)
        resource.get(bounty_id="bounty-1")
        http.request_model.assert_called_once_with(
            "GET",
            "/v1/bounties/bounty-1",
            GetBountyResponse,
        )

    def test_update_status_calls_request_model(self) -> None:
        """update_status() sends PATCH /v1/bounties/{bounty_id}/status."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=OpenBountyResponse)
        http.request_model.return_value = mock_resp
        resource = BountiesResource(http)
        resource.update_status(bounty_id="bounty-1")
        http.request_model.assert_called_once_with(
            "PATCH",
            "/v1/bounties/bounty-1/status",
            OpenBountyResponse,
        )

    def test_update_funding_calls_request_model(self) -> None:
        """update_funding() sends PATCH /v1/bounties/{bounty_id}/funding."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=FundBountyResponse)
        http.request_model.return_value = mock_resp
        resource = BountiesResource(http)
        resource.update_funding(bounty_id="bounty-1")
        http.request_model.assert_called_once_with(
            "PATCH",
            "/v1/bounties/bounty-1/funding",
            FundBountyResponse,
        )

    def test_delete_calls_request_model(self) -> None:
        """delete() sends DELETE /v1/bounties/{bounty_id}."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=CancelBountyResponse)
        http.request_model.return_value = mock_resp
        resource = BountiesResource(http)
        resource.delete(bounty_id="bounty-1")
        http.request_model.assert_called_once_with(
            "DELETE",
            "/v1/bounties/bounty-1",
            CancelBountyResponse,
        )

    def test_create_payout_calls_request_model(self) -> None:
        """create_payout() sends POST /v1/bounties/{bounty_id}/payouts."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=CreateBountyPayoutResponse)
        http.request_model.return_value = mock_resp
        resource = BountiesResource(http)
        resource.create_payout(bounty_id="bounty-1")
        http.request_model.assert_called_once_with(
            "POST",
            "/v1/bounties/bounty-1/payouts",
            CreateBountyPayoutResponse,
        )

    def test_create_submission_sends_post_with_body(
        self,
    ) -> None:
        """create_submission() sends POST with title+description body."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=CreateBountySubmissionResponse)
        http.request_model.return_value = mock_resp
        resource = BountiesResource(http)
        resource.create_submission(
            bounty_id="bounty-1",
            title="My Submission",
            description="Submission details",
        )
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1] == "/v1/bounties/bounty-1/submissions"
        assert call_args.args[2] == CreateBountySubmissionResponse
        json_body = call_args.kwargs["json"]
        assert json_body["title"] == "My Submission"
        assert json_body["description"] == "Submission details"

    def test_create_submission_with_optional_fields(
        self,
    ) -> None:
        """create_submission() includes evidence and version_id."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=CreateBountySubmissionResponse)
        http.request_model.return_value = mock_resp
        resource = BountiesResource(http)
        resource.create_submission(
            bounty_id="bounty-1",
            title="Sub",
            description="Desc",
            evidence={"link": "https://example.com"},
            proposed_course_version_id=(
                "22222222-2222-2222-2222-222222222222"
            ),
        )
        call_args = http.request_model.call_args
        json_body = call_args.kwargs["json"]
        assert "evidence" in json_body
        assert "proposed_course_version_id" in json_body

    def test_list_submissions_calls_request(self) -> None:
        """list_submissions() calls GET via request (returns list)."""
        http = MagicMock(spec=HttpClient)
        http.request.return_value = []
        resource = BountiesResource(http)
        resource.list_submissions(bounty_id="bounty-1")
        http.request.assert_called_once()
        call_args = http.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1] == "/v1/bounties/bounty-1/submissions"

    def test_get_submission_calls_request_model(self) -> None:
        """get_submission() sends GET .../submissions/{submission_id}."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=GetBountySubmissionResponse)
        http.request_model.return_value = mock_resp
        resource = BountiesResource(http)
        resource.get_submission(
            bounty_id="bounty-1",
            submission_id="sub-1",
        )
        http.request_model.assert_called_once_with(
            "GET",
            "/v1/bounties/bounty-1/submissions/sub-1",
            GetBountySubmissionResponse,
        )

    def test_accept_submission_calls_request_model(self) -> None:
        """accept_submission() sends PATCH .../acceptance."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(
            spec=AcceptBountySubmissionResponse,
        )
        http.request_model.return_value = mock_resp
        resource = BountiesResource(http)
        resource.accept_submission(
            bounty_id="bounty-1",
            submission_id="sub-1",
        )
        http.request_model.assert_called_once_with(
            "PATCH",
            "/v1/bounties/bounty-1/submissions/sub-1/acceptance",
            AcceptBountySubmissionResponse,
        )

    def test_reject_submission_calls_request_model(self) -> None:
        """reject_submission() sends PATCH .../rejection."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(
            spec=RejectBountySubmissionResponse,
        )
        http.request_model.return_value = mock_resp
        resource = BountiesResource(http)
        resource.reject_submission(
            bounty_id="bounty-1",
            submission_id="sub-1",
        )
        http.request_model.assert_called_once_with(
            "PATCH",
            "/v1/bounties/bounty-1/submissions/sub-1/rejection",
            RejectBountySubmissionResponse,
        )

    def test_delete_submission_calls_request_model(self) -> None:
        """delete_submission() sends DELETE .../submissions/{id}."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(
            spec=WithdrawBountySubmissionResponse,
        )
        http.request_model.return_value = mock_resp
        resource = BountiesResource(http)
        resource.delete_submission(
            bounty_id="bounty-1",
            submission_id="sub-1",
        )
        http.request_model.assert_called_once_with(
            "DELETE",
            "/v1/bounties/bounty-1/submissions/sub-1",
            WithdrawBountySubmissionResponse,
        )
