# SPDX-License-Identifier: MIT
"""Tests for logion._http module."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import httpx
import pytest
from pydantic import BaseModel

from logion._config import ClientConfig
from logion._errors import (
    AuthenticationError,
    ClientError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    ServerError,
    TransportError,
    ValidationError,
)
from logion._http import HttpClient, _raise_for_status


def _make_config(
    *,
    base_url: str = "http://localhost:4010",
    api_key: str = "lgk_test",
    timeout: float = 5.0,
    max_retries: int = 0,
    extra_headers: dict[str, str] | None = None,
) -> ClientConfig:
    """Build a ClientConfig with sensible test defaults."""
    return ClientConfig(
        base_url=base_url,
        api_key=api_key,
        timeout=timeout,
        max_retries=max_retries,
        extra_headers=extra_headers if extra_headers is not None else {},
    )


def _mock_response(
    status_code: int = 200,
    json_data: dict | None = None,
    text: str = "",
    headers: dict | None = None,
) -> MagicMock:
    """Create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.headers = httpx.Headers(headers or {})
    resp.text = text
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = Exception("no json")
    return resp


class TestHttpClientRequest:
    """Tests for HttpClient.request method."""

    @patch("httpx.Client.request")
    def test_successful_get_returns_json_dict(self, mock_request) -> None:
        """Successful GET request returns JSON dict."""
        mock_request.return_value = _mock_response(
            200, json_data={"status": "ok"}
        )
        client = HttpClient(_make_config())
        result = client.request("GET", "/health")
        assert result == {"status": "ok"}
        client.close()

    @patch("httpx.Client.request")
    def test_bearer_auth_header_sent(self, mock_request) -> None:
        """Bearer auth header is sent when api_key is set."""
        mock_request.return_value = _mock_response(200, json_data={})
        client = HttpClient(_make_config(api_key="lgk_secret"))
        client.request("GET", "/test")
        auth_header = client._client.headers.get("Authorization")
        assert auth_header == "Bearer lgk_secret"
        client.close()

    @patch("httpx.Client.request")
    def test_no_auth_header_when_empty_key(self, mock_request) -> None:
        """No auth header when api_key is empty."""
        mock_request.return_value = _mock_response(200, json_data={})
        client = HttpClient(_make_config(api_key=""))
        client.request("GET", "/test")
        auth_header = client._client.headers.get("Authorization")
        assert auth_header is None
        client.close()

    @patch("httpx.Client.request")
    def test_extra_headers_merged(self, mock_request) -> None:
        """Extra headers are merged into default headers."""
        mock_request.return_value = _mock_response(200, json_data={})
        extra = {"X-Custom": "custom-value"}
        client = HttpClient(_make_config(extra_headers=extra))
        assert client._client.headers.get("X-Custom") == "custom-value"
        client.close()

    @patch("httpx.Client.request")
    def test_x_request_id_header_sent(self, mock_request) -> None:
        """X-Request-ID header is sent on each request."""
        mock_request.return_value = _mock_response(200, json_data={})
        client = HttpClient(_make_config())
        client.request("GET", "/test")
        call_kwargs = mock_request.call_args
        headers = call_kwargs.kwargs.get("headers", {})
        assert "X-Request-ID" in headers
        client.close()

    @patch("httpx.Client.request")
    def test_transport_error_wrapped(self, mock_request) -> None:
        """httpx.ConnectError is wrapped in
        TransportError."""
        mock_request.side_effect = httpx.ConnectError("Connection refused")
        client = HttpClient(_make_config(max_retries=0))
        with pytest.raises(TransportError) as exc_info:
            client.request("GET", "/test")
        assert exc_info.value.original is not None
        assert "Connection refused" in str(exc_info.value.original)
        client.close()

    @patch("httpx.Client.request")
    def test_retries_on_502_for_get(self, mock_request) -> None:
        """Retries on 502 for GET (idempotent) method."""
        fail_resp = _mock_response(502, text="Bad Gateway")
        success_resp = _mock_response(200, json_data={"ok": True})
        mock_request.side_effect = [
            fail_resp,
            success_resp,
        ]
        client = HttpClient(_make_config(max_retries=2))
        with patch("logion._http.time.sleep"):
            result = client.request("GET", "/test")
        assert result == {"ok": True}
        assert mock_request.call_count == 2
        client.close()

    @patch("httpx.Client.request")
    def test_no_retry_on_502_for_post(self, mock_request) -> None:
        """No retry on 502 for POST (non-idempotent)."""
        fail_resp = _mock_response(502, text="Bad Gateway")
        mock_request.return_value = fail_resp
        client = HttpClient(_make_config(max_retries=2))
        with pytest.raises(ServerError):
            client.request("POST", "/test")
        assert mock_request.call_count == 1
        client.close()

    @patch("httpx.Client.request")
    def test_request_model_parses_response(self, mock_request) -> None:
        """request_model parses response into Pydantic
        model."""

        class SimpleModel(BaseModel):
            name: str
            value: int

        mock_request.return_value = _mock_response(
            200, json_data={"name": "test", "value": 42}
        )
        client = HttpClient(_make_config())
        result = client.request_model("GET", "/test", SimpleModel)
        assert isinstance(result, SimpleModel)
        assert result.name == "test"
        assert result.value == 42
        client.close()

    @patch("httpx.Client.close")
    def test_close_delegates(self, mock_close) -> None:
        """close() closes the underlying client."""
        client = HttpClient(_make_config())
        client.close()
        mock_close.assert_called_once()


class TestRaiseForStatus:
    """Tests for _raise_for_status function."""

    def test_2xx_does_not_raise(self) -> None:
        """2xx responses do not raise."""
        resp = _mock_response(200)
        _raise_for_status(resp)  # should not raise

    def test_401_raises_authentication_error(
        self,
    ) -> None:
        resp = _mock_response(401, text="Unauthorized", headers={})
        with pytest.raises(AuthenticationError) as exc_info:
            _raise_for_status(resp)
        assert exc_info.value.status_code == 401

    def test_403_raises_forbidden_error(self) -> None:
        resp = _mock_response(403, text="Forbidden")
        with pytest.raises(ForbiddenError):
            _raise_for_status(resp)

    def test_404_raises_not_found_error(self) -> None:
        resp = _mock_response(404, text="Not Found")
        with pytest.raises(NotFoundError):
            _raise_for_status(resp)

    def test_409_raises_conflict_error(self) -> None:
        resp = _mock_response(409, text="Conflict")
        with pytest.raises(ConflictError):
            _raise_for_status(resp)

    def test_422_raises_validation_error(self) -> None:
        resp = _mock_response(422, text="Unprocessable")
        with pytest.raises(ValidationError):
            _raise_for_status(resp)

    def test_429_raises_rate_limit_error(self) -> None:
        resp = _mock_response(429, text="Too Many")
        with pytest.raises(RateLimitError):
            _raise_for_status(resp)

    def test_500_raises_server_error(self) -> None:
        resp = _mock_response(500, text="Internal Error")
        with pytest.raises(ServerError):
            _raise_for_status(resp)

    def test_400_raises_client_error(self) -> None:
        """Unmapped 4xx raises ClientError."""
        resp = _mock_response(400, text="Bad Request")
        with pytest.raises(ClientError):
            _raise_for_status(resp)

    def test_502_raises_server_error(self) -> None:
        """502 (not in specific map) raises ServerError."""
        resp = _mock_response(502, text="Bad Gateway")
        with pytest.raises(ServerError):
            _raise_for_status(resp)

    def test_json_detail_from_body(self) -> None:
        """Response with detail key in JSON body uses it."""
        resp = _mock_response(
            400,
            json_data={"detail": "field required"},
        )
        with pytest.raises(ClientError) as exc_info:
            _raise_for_status(resp)
        assert exc_info.value.detail == "field required"

    def test_request_id_from_header(self) -> None:
        """Response with x-request-id header is captured."""
        resp = _mock_response(
            401,
            text="Unauthorized",
            headers={"x-request-id": "req-xyz"},
        )
        with pytest.raises(AuthenticationError) as exc_info:
            _raise_for_status(resp)
        assert exc_info.value.request_id == "req-xyz"

    def test_json_list_detail(self) -> None:
        """Response with list detail (validation errors)."""
        detail = [
            {"field": "email", "msg": "invalid"},
        ]
        resp = _mock_response(422, json_data={"detail": detail})
        with pytest.raises(ValidationError) as exc_info:
            _raise_for_status(resp)
        assert exc_info.value.detail == detail


class TestShapeNarrowingHelpers:
    """Response-shape guards, which live on the transport.

    ``request`` returns the full JSON grammar, so every caller that
    needs an object or an array of objects goes through one of these.
    Keeping the check here means each resource does not re-implement it,
    and a malformed body fails with the method and path in the message.
    """

    @patch("httpx.Client.request")
    def test_request_object_returns_an_object(self, mock_request) -> None:
        mock_request.return_value = _mock_response(
            200, json_data={"status": "ok"}
        )
        client = HttpClient(_make_config())
        assert client.request_object("GET", "/health") == {"status": "ok"}

    @pytest.mark.parametrize(
        "payload",
        [[], ["a"], 42, True],
    )
    @patch("httpx.Client.request")
    def test_request_object_rejects_non_objects(
        self, mock_request, payload: object
    ) -> None:
        mock_request.return_value = _mock_response(200, json_data=payload)
        client = HttpClient(_make_config())
        with pytest.raises(TypeError, match="Expected a JSON object"):
            client.request_object("GET", "/v1/resources")

    @patch("httpx.Client.request")
    def test_request_object_names_the_method_and_path(
        self, mock_request
    ) -> None:
        mock_request.return_value = _mock_response(200, json_data=["nope"])
        client = HttpClient(_make_config())
        with pytest.raises(TypeError, match=r"GET /v1/resources"):
            client.request_object("GET", "/v1/resources")

    @patch("httpx.Client.request")
    def test_request_list_returns_objects(self, mock_request) -> None:
        mock_request.return_value = _mock_response(
            200, json_data=[{"id": 1}, {"id": 2}]
        )
        client = HttpClient(_make_config())
        assert client.request_list("GET", "/v1/bounties") == [
            {"id": 1},
            {"id": 2},
        ]

    @patch("httpx.Client.request")
    def test_request_list_rejects_a_non_array(self, mock_request) -> None:
        mock_request.return_value = _mock_response(200, json_data={"a": 1})
        client = HttpClient(_make_config())
        with pytest.raises(TypeError, match="Expected a JSON array"):
            client.request_list("GET", "/v1/bounties")

    @patch("httpx.Client.request")
    def test_request_list_rejects_a_non_object_element(
        self, mock_request
    ) -> None:
        mock_request.return_value = _mock_response(
            200, json_data=[{"id": 1}, "nope"]
        )
        client = HttpClient(_make_config())
        with pytest.raises(TypeError, match=r"at index 1"):
            client.request_list("GET", "/v1/bounties")

    @patch("httpx.Client.request")
    def test_request_items_accepts_a_bare_array(self, mock_request) -> None:
        mock_request.return_value = _mock_response(
            200, json_data=[{"feedback_id": "fb-1"}]
        )
        client = HttpClient(_make_config())
        assert client.request_items("GET", "/v1/feedback/mine") == [
            {"feedback_id": "fb-1"}
        ]

    @patch("httpx.Client.request")
    def test_request_items_unwraps_an_items_envelope(
        self, mock_request
    ) -> None:
        mock_request.return_value = _mock_response(
            200, json_data={"items": [{"feedback_id": "fb-1"}]}
        )
        client = HttpClient(_make_config())
        assert client.request_items("GET", "/v1/feedback/mine") == [
            {"feedback_id": "fb-1"}
        ]

    @patch("httpx.Client.request")
    def test_request_items_rejects_a_non_collection(
        self, mock_request
    ) -> None:
        mock_request.return_value = _mock_response(
            200, json_data={"not": "a list"}
        )
        client = HttpClient(_make_config())
        with pytest.raises(TypeError, match="Expected a JSON array"):
            client.request_items("GET", "/v1/feedback/mine")


class TestQueryParamEncoding:
    """UUIDs and repeated parameters are encoded in one place."""

    @patch("httpx.Client.request")
    def test_uuid_values_become_strings(self, mock_request) -> None:
        mock_request.return_value = _mock_response(200, json_data={})
        client = HttpClient(_make_config())
        agent_id = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
        client.request("GET", "/v1/admin/courses", params={"a": agent_id})
        assert mock_request.call_args.kwargs["params"] == {
            "a": "123e4567-e89b-12d3-a456-426614174000"
        }

    @patch("httpx.Client.request")
    def test_none_values_are_dropped(self, mock_request) -> None:
        mock_request.return_value = _mock_response(200, json_data={})
        client = HttpClient(_make_config())
        client.request("GET", "/v1/x", params={"a": "1", "b": None})
        assert mock_request.call_args.kwargs["params"] == {"a": "1"}

    @patch("httpx.Client.request")
    def test_sequences_survive_as_repeated_params(self, mock_request) -> None:
        mock_request.return_value = _mock_response(200, json_data={})
        client = HttpClient(_make_config())
        client.request("GET", "/v1/x", params={"ids": ["a", "b"]})
        assert mock_request.call_args.kwargs["params"] == {"ids": ["a", "b"]}

    @patch("httpx.Client.request")
    def test_none_inside_a_sequence_is_dropped(self, mock_request) -> None:
        mock_request.return_value = _mock_response(200, json_data={})
        client = HttpClient(_make_config())
        client.request("GET", "/v1/x", params={"ids": ["a", None, "b"]})
        assert mock_request.call_args.kwargs["params"] == {"ids": ["a", "b"]}
