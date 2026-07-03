# SPDX-License-Identifier: MIT
"""Tests for v1 resource methods."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from logion._http import HttpClient
from logion.v1._resources.courses import CoursesResource
from logion.v1._resources.credits import CreditsResource
from logion.v1._resources.health import HealthResource
from logion.v1._resources.identity import IdentityResource
from logion.v1._resources.listings import ListingsResource
from logion.v1._resources.payments import PaymentsResource
from logion.v1._types.generated.v1 import (
    AddAgentToUserResponse,
    AuthorizeResponse,
    CreateCourseResponse,
    CreateCourseVersionUploadSessionResponse,
    CreateCreditTopUpResponse,
    CreateUserWithAgentResponse,
    DeviceBeginResponse,
    DevicePollGrantedResponse,
    DevicePollPendingResponse,
    GetCourseResponse,
    GetCourseVersionResponse,
    GetCreatorEarningsResponse,
    GetCreditBalanceResponse,
    GetCreditTopUpResponse,
    GithubIdentityResponse,
    OnboardingLinkResponse,
    OrderResponse,
    PurchaseCourseResponse,
    RequestCashOutResponse,
    RotateAgentApiKeyResponse,
    SearchListingsResponse,
    SellerReadinessResponse,
    UpdateCourseResponse,
)

# ---- CreditsResource ----


class TestCreditsResource:
    def test_get_balance_calls_request_model(self) -> None:
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=GetCreditBalanceResponse)
        http.request_model.return_value = mock_resp
        resource = CreditsResource(http)

        result = resource.get_balance()

        assert result == mock_resp
        http.request_model.assert_called_once_with(
            "GET", "/v1/credits/balance", GetCreditBalanceResponse
        )

    def test_create_top_up_builds_request(self) -> None:
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=CreateCreditTopUpResponse)
        http.request_model.return_value = mock_resp
        resource = CreditsResource(http)

        result = resource.create_top_up(amount_cents=1000)

        assert result == mock_resp
        call_args = http.request_model.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1] == "/v1/credits/top-ups"
        assert call_args.args[2] == CreateCreditTopUpResponse
        assert call_args.kwargs["json"]["amount_cents"] == 1000

    def test_create_top_up_default_includes_usd_currency(self) -> None:
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=CreateCreditTopUpResponse)
        http.request_model.return_value = mock_resp
        resource = CreditsResource(http)

        resource.create_top_up(amount_cents=1000)

        call_args = http.request_model.call_args
        assert call_args.kwargs["json"]["currency"] == "usd"

    def test_create_top_up_forwards_non_default_currency(self) -> None:
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=CreateCreditTopUpResponse)
        http.request_model.return_value = mock_resp
        resource = CreditsResource(http)

        resource.create_top_up(amount_cents=1000, currency="brl")

        call_args = http.request_model.call_args
        assert call_args.kwargs["json"]["currency"] == "brl"

    def test_get_top_up_accepts_uuid_string(self) -> None:
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=GetCreditTopUpResponse)
        http.request_model.return_value = mock_resp
        resource = CreditsResource(http)

        result = resource.get_top_up(
            top_up_id="11111111-1111-1111-1111-111111111111"
        )

        assert result == mock_resp
        http.request_model.assert_called_once_with(
            "GET",
            "/v1/credits/top-ups/11111111-1111-1111-1111-111111111111",
            GetCreditTopUpResponse,
        )

    def test_list_ledger_calls_request_list(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request_list.return_value = []
        resource = CreditsResource(http)

        assert resource.list_ledger() == []
        http.request_list.assert_called_once_with("GET", "/v1/credits/ledger")


# ---- HealthResource ----


class TestHealthResource:
    def test_check_calls_request(self) -> None:
        """HealthResource.check() calls GET /health."""
        http = MagicMock(spec=HttpClient)
        http.request.return_value = {"status": "ok"}
        resource = HealthResource(http)
        result = resource.check()
        http.request.assert_called_once_with("GET", "/health")
        assert result == {"status": "ok"}


# ---- ListingsResource ----


class TestListingsResource:
    def test_search_calls_request_model(self) -> None:
        """search() with valid params calls
        request_model."""
        http = MagicMock(spec=HttpClient)
        mock_response = MagicMock(spec=SearchListingsResponse)
        http.request_model.return_value = mock_response
        resource = ListingsResource(http)
        resource.search(query="rag", sort="relevance")
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1] == "/v1/listings"
        assert call_args.args[2] == SearchListingsResponse
        params = call_args.kwargs["params"]
        assert params["query"] == "rag"
        assert params["sort"] == "relevance"

    def test_search_invalid_sort_raises_value_error(
        self,
    ) -> None:
        """search() with invalid sort raises ValueError."""
        http = MagicMock(spec=HttpClient)
        resource = ListingsResource(http)
        with pytest.raises(ValueError, match="Invalid sort"):
            resource.search(sort="invalid_sort")

    def test_search_with_no_params(self) -> None:
        """search() with all optional params omitted."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=SearchListingsResponse)
        http.request_model.return_value = mock_resp
        resource = ListingsResource(http)
        resource.search()
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        params = call_args.kwargs["params"]
        assert params == {}


# ---- CoursesResource ----


class TestCoursesResource:
    def test_create_with_required_and_optional(
        self,
    ) -> None:
        """create() builds request with required+optional
        fields."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=CreateCourseResponse)
        http.request_model.return_value = mock_resp
        resource = CoursesResource(http)
        resource.create(
            title="My Course",
            slug="my-course",
            description="A great course",
            price_cents=1999,
        )
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1] == "/v1/courses"
        assert call_args.args[2] == CreateCourseResponse
        json_body = call_args.kwargs["json"]
        assert json_body["title"] == "My Course"
        assert json_body["slug"] == "my-course"
        assert json_body["description"] == "A great course"
        assert json_body["price_cents"] == 1999

    def test_get_calls_get_with_course_id(
        self,
    ) -> None:
        """get() calls GET with course_id in URL."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=GetCourseResponse)
        http.request_model.return_value = mock_resp
        resource = CoursesResource(http)
        resource.get(course_id="abc-123")
        http.request_model.assert_called_once_with(
            "GET",
            "/v1/courses/abc-123",
            GetCourseResponse,
        )

    def test_update_uses_sentinel_pattern(
        self,
    ) -> None:
        """update() only includes fields that were explicitly
        provided — omitted fields are absent from the payload."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=UpdateCourseResponse)
        http.request_model.return_value = mock_resp
        resource = CoursesResource(http)
        resource.update(
            course_id="course-1",
            title="New Title",
        )
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "PATCH"
        assert "/v1/courses/course-1" in call_args.args[1]
        json_body = call_args.kwargs["json"]
        # Only 'title' should be present (exclude_unset)
        assert "title" in json_body
        assert json_body["title"] == "New Title"
        # Omitted fields must NOT appear in the payload
        assert "description" not in json_body
        assert "price_cents" not in json_body
        assert "tags" not in json_body
        assert "currency" not in json_body
        assert "language" not in json_body
        assert "short_summary" not in json_body
        assert "visibility" not in json_body

    def test_update_with_null_value(self) -> None:
        """update() with None sends null (not omitted)."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=UpdateCourseResponse)
        http.request_model.return_value = mock_resp
        resource = CoursesResource(http)
        resource.update(
            course_id="course-1",
            description=None,
        )
        call_args = http.request_model.call_args
        json_body = call_args.kwargs["json"]
        assert "description" in json_body

    def test_create_upload_session(self) -> None:
        """create_upload_session() sends files param."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(
            spec=CreateCourseVersionUploadSessionResponse,
        )
        http.request_model.return_value = mock_resp
        resource = CoursesResource(http)
        files = [
            {
                "filename": "test.pdf",
                "content_type": "application/pdf",
                "size_bytes": 1024,
            }
        ]
        resource.create_upload_session(
            course_id="course-1",
            files=files,
        )
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "POST"
        assert "/v1/courses/course-1/versions" in call_args.args[1]
        json_body = call_args.kwargs["json"]
        assert "files" in json_body

    def test_get_version(self) -> None:
        """get_version() calls GET with course_id and
        version_id."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=GetCourseVersionResponse)
        http.request_model.return_value = mock_resp
        resource = CoursesResource(http)
        resource.get_version(
            course_id="c1",
            version_id="v1",
        )
        http.request_model.assert_called_once_with(
            "GET",
            "/v1/courses/c1/versions/v1",
            GetCourseVersionResponse,
        )

    def test_purchase(self) -> None:
        """purchase() calls POST with course_id and body."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=PurchaseCourseResponse)
        http.request_model.return_value = mock_resp
        resource = CoursesResource(http)
        resource.purchase(course_id="course-1")
        call_args = http.request_model.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1] == "/v1/courses/course-1/purchase"
        assert call_args.args[2] == PurchaseCourseResponse
        json_body = call_args.kwargs["json"]
        assert "expected_price_cents" not in json_body

    def test_purchase_with_price_guard(self) -> None:
        """purchase() forwards expected_price_cents."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=PurchaseCourseResponse)
        http.request_model.return_value = mock_resp
        resource = CoursesResource(http)
        resource.purchase(
            course_id="course-1",
            expected_price_cents=500,
        )
        call_args = http.request_model.call_args
        json_body = call_args.kwargs["json"]
        assert json_body["expected_price_cents"] == 500


# ---- IdentityResource ----


class TestIdentityResource:
    def test_create_user_with_agent(self) -> None:
        """create_user_with_agent() requires email,
        user_password, agent_name."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=CreateUserWithAgentResponse)
        http.request_model.return_value = mock_resp
        resource = IdentityResource(http)
        resource.create_user_with_agent(
            email="test@example.com",
            user_password="secret123",
            agent_name="My Agent",
        )
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1] == "/v1/identity/users"
        assert call_args.args[2] == CreateUserWithAgentResponse
        json_body = call_args.kwargs["json"]
        assert json_body["email"] == "test@example.com"
        assert json_body["user_password"] == "secret123"
        assert json_body["agent_name"] == "My Agent"

    def test_add_agent_to_user(self) -> None:
        """add_agent_to_user() requires user_password."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=AddAgentToUserResponse)
        http.request_model.return_value = mock_resp
        resource = IdentityResource(http)
        resource.add_agent_to_user(
            user_id="user-1",
            agent_name="Agent2",
            user_password="secret123",
        )
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "POST"
        assert "/v1/identity/users/user-1/agents" in call_args.args[1]
        json_body = call_args.kwargs["json"]
        assert json_body["user_password"] == "secret123"
        assert json_body["agent_name"] == "Agent2"

    def test_rotate_api_key(self) -> None:
        """rotate_api_key() sends body with
        user_password."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=RotateAgentApiKeyResponse)
        http.request_model.return_value = mock_resp
        resource = IdentityResource(http)
        resource.rotate_api_key(
            user_id="user-1",
            agent_id="agent-1",
            user_password="secret123",
        )
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "POST"
        assert (
            "/v1/identity/users/user-1"
            "/agents/agent-1/api-keys" in call_args.args[1]
        )
        json_body = call_args.kwargs["json"]
        assert json_body["user_password"] == "secret123"

    def test_begin_github_authorization(self) -> None:
        """begin_github_authorization() sends scope_tier and
        redirect_target."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=AuthorizeResponse)
        http.request_model.return_value = mock_resp
        resource = IdentityResource(http)
        resource.begin_github_authorization(
            scope_tier="repo",
            redirect_target="none",
        )
        http.request_model.assert_called_once()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1] == "/v1/identity/github/authorize"
        assert call_args.args[2] == AuthorizeResponse
        json_body = call_args.kwargs["json"]
        assert json_body["scope_tier"] == "repo"
        assert json_body["redirect_target"] == "none"

    def test_begin_github_authorization_defaults(self) -> None:
        """begin_github_authorization() uses identity scope by default."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=AuthorizeResponse)
        http.request_model.return_value = mock_resp
        resource = IdentityResource(http)
        resource.begin_github_authorization()
        call_args = http.request_model.call_args
        json_body = call_args.kwargs["json"]
        assert json_body["scope_tier"] == "identity"

    def test_complete_github_callback(self) -> None:
        """complete_github_callback() sends GET with query params."""
        http = MagicMock(spec=HttpClient)
        http.request.return_value = {"status": "ok"}
        resource = IdentityResource(http)
        result = resource.complete_github_callback(
            code="abc123",
            state="state-xyz",
        )
        assert result == {"status": "ok"}
        http.request.assert_called_once_with(
            "GET",
            "/v1/identity/github/callback",
            params={"code": "abc123", "state": "state-xyz"},
        )

    def test_begin_github_device_flow(self) -> None:
        """begin_github_device_flow() sends POST with scope_tier."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=DeviceBeginResponse)
        http.request_model.return_value = mock_resp
        resource = IdentityResource(http)
        result = resource.begin_github_device_flow(scope_tier="repo")
        assert result == mock_resp
        call_args = http.request_model.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1] == "/v1/identity/github/device"
        assert call_args.args[2] == DeviceBeginResponse
        json_body = call_args.kwargs["json"]
        assert json_body["scope_tier"] == "repo"

    def test_begin_github_device_flow_default_scope(self) -> None:
        """begin_github_device_flow() defaults to identity scope."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=DeviceBeginResponse)
        http.request_model.return_value = mock_resp
        resource = IdentityResource(http)
        resource.begin_github_device_flow()
        call_args = http.request_model.call_args
        json_body = call_args.kwargs["json"]
        assert json_body["scope_tier"] == "identity"

    def test_poll_github_device_flow_granted(self) -> None:
        """poll_github_device_flow() returns granted response when
        status is not pending."""
        http = MagicMock(spec=HttpClient)
        granted_data = {
            "status": "connected",
            "github_login": "octocat",
            "scope_tier": "identity",
        }
        http.request.return_value = granted_data
        resource = IdentityResource(http)
        result = resource.poll_github_device_flow(
            device_code="dev-123",
        )
        assert isinstance(result, DevicePollGrantedResponse)
        assert result.github_login == "octocat"
        call_args = http.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1] == "/v1/identity/github/device/poll"
        json_body = call_args.kwargs["json"]
        assert json_body["device_code"] == "dev-123"

    def test_poll_github_device_flow_pending(self) -> None:
        """poll_github_device_flow() returns pending response when
        status is pending."""
        http = MagicMock(spec=HttpClient)
        pending_data = {"status": "pending", "interval": 5}
        http.request.return_value = pending_data
        resource = IdentityResource(http)
        result = resource.poll_github_device_flow(
            device_code="dev-123",
        )
        assert isinstance(result, DevicePollPendingResponse)
        assert result.status == "pending"

    def test_get_github_identity(self) -> None:
        """get_github_identity() calls GET /v1/identity/github."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=GithubIdentityResponse)
        http.request_model.return_value = mock_resp
        resource = IdentityResource(http)
        result = resource.get_github_identity()
        assert result == mock_resp
        http.request_model.assert_called_once_with(
            "GET",
            "/v1/identity/github",
            GithubIdentityResponse,
        )

    def test_revoke_github_identity(self) -> None:
        """revoke_github_identity() calls DELETE /v1/identity/github."""
        http = MagicMock(spec=HttpClient)
        http.request.return_value = {"status": "disconnected"}
        resource = IdentityResource(http)
        result = resource.revoke_github_identity()
        assert result == {"status": "disconnected"}
        http.request.assert_called_once_with(
            "DELETE",
            "/v1/identity/github",
        )


# ---- PaymentsResource ----


class TestPaymentsResource:
    def test_get_order(self) -> None:
        """get_order() calls GET."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=OrderResponse)
        http.request_model.return_value = mock_resp
        resource = PaymentsResource(http)
        resource.get_order(order_id="order-1")
        http.request_model.assert_called_once_with(
            "GET",
            "/v1/payments/orders/order-1",
            OrderResponse,
        )

    def test_get_seller_readiness(self) -> None:
        """get_seller_readiness() calls GET."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=SellerReadinessResponse)
        http.request_model.return_value = mock_resp
        resource = PaymentsResource(http)
        resource.get_seller_readiness()
        http.request_model.assert_called_once_with(
            "GET",
            "/v1/payments/seller-readiness",
            SellerReadinessResponse,
        )

    def test_create_onboarding_link(self) -> None:
        """create_onboarding_link() calls POST."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=OnboardingLinkResponse)
        http.request_model.return_value = mock_resp
        resource = PaymentsResource(http)
        resource.create_onboarding_link()
        http.request_model.assert_called_once_with(
            "POST",
            "/v1/payments/connect-onboarding-sessions",
            OnboardingLinkResponse,
        )

    def test_get_creator_earnings(self) -> None:
        """get_creator_earnings() calls GET."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=GetCreatorEarningsResponse)
        http.request_model.return_value = mock_resp
        resource = PaymentsResource(http)
        resource.get_creator_earnings()
        http.request_model.assert_called_once_with(
            "GET",
            "/v1/payments/creator-earnings",
            GetCreatorEarningsResponse,
        )

    def test_request_cash_out(self) -> None:
        """request_cash_out() calls POST with body."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=RequestCashOutResponse)
        http.request_model.return_value = mock_resp
        resource = PaymentsResource(http)
        resource.request_cash_out()
        call_args = http.request_model.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1] == "/v1/payments/cash-out"
        assert call_args.args[2] == RequestCashOutResponse
        json_body = call_args.kwargs["json"]
        assert json_body["dry_run"] is False

    def test_request_cash_out_with_overrides(self) -> None:
        """request_cash_out() forwards minimum_payout_cents and dry_run."""
        http = MagicMock(spec=HttpClient)
        mock_resp = MagicMock(spec=RequestCashOutResponse)
        http.request_model.return_value = mock_resp
        resource = PaymentsResource(http)
        resource.request_cash_out(minimum_payout_cents=5000, dry_run=True)
        call_args = http.request_model.call_args
        json_body = call_args.kwargs["json"]
        assert json_body["minimum_payout_cents"] == 5000
        assert json_body["dry_run"] is True
