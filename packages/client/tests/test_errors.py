"""Tests for logion._errors module."""

from __future__ import annotations

from logion import (
    APIError,
    AuthenticationError,
    ClientError,
    ConflictError,
    ForbiddenError,
    LogionError,
    NotFoundError,
    RateLimitError,
    ServerError,
    TransportError,
    ValidationError,
)


class TestErrorInheritance:
    """All error classes inherit from correct parents."""

    def test_logion_error_is_exception(self) -> None:
        assert issubclass(LogionError, Exception)

    def test_api_error_inherits_logion_error(self) -> None:
        assert issubclass(APIError, LogionError)

    def test_client_error_inherits_api_error(self) -> None:
        assert issubclass(ClientError, APIError)

    def test_authentication_error_inherits_api_error(self) -> None:
        assert issubclass(AuthenticationError, APIError)

    def test_forbidden_error_inherits_api_error(self) -> None:
        assert issubclass(ForbiddenError, APIError)

    def test_not_found_error_inherits_api_error(self) -> None:
        assert issubclass(NotFoundError, APIError)

    def test_conflict_error_inherits_api_error(self) -> None:
        assert issubclass(ConflictError, APIError)

    def test_validation_error_inherits_api_error(self) -> None:
        assert issubclass(ValidationError, APIError)

    def test_rate_limit_error_inherits_api_error(self) -> None:
        assert issubclass(RateLimitError, APIError)

    def test_server_error_inherits_api_error(self) -> None:
        assert issubclass(ServerError, APIError)

    def test_transport_error_inherits_logion_error(self) -> None:
        assert issubclass(TransportError, LogionError)
        assert not issubclass(TransportError, APIError)

    def test_all_api_subclasses_are_logion_error(self) -> None:
        """All APIError subclasses are also LogionError."""
        subclasses = [
            ClientError,
            AuthenticationError,
            ForbiddenError,
            NotFoundError,
            ConflictError,
            ValidationError,
            RateLimitError,
            ServerError,
        ]
        for cls in subclasses:
            assert issubclass(cls, LogionError), (
                f"{cls.__name__} should be LogionError"
            )


class TestAPIError:
    """Tests for APIError attributes and formatting."""

    def test_stores_status_code_detail_request_id(self) -> None:
        """APIError stores status_code, detail, request_id."""
        err = APIError(
            status_code=400,
            detail="Bad Request",
            request_id="req-123",
        )
        assert err.status_code == 400
        assert err.detail == "Bad Request"
        assert err.request_id == "req-123"

    def test_formats_message(self) -> None:
        """APIError formats message with status, request_id, detail."""
        err = APIError(
            status_code=401,
            detail="Unauthorized",
            request_id="req-abc",
        )
        assert "401" in str(err)
        assert "req-abc" in str(err)
        assert "Unauthorized" in str(err)

    def test_message_without_request_id(self) -> None:
        """APIError formats message without request_id when None."""
        err = APIError(
            status_code=500,
            detail="Internal Server Error",
        )
        msg = str(err)
        assert "500" in msg
        assert "Internal Server Error" in msg
        assert "request_id" not in msg

    def test_list_detail(self) -> None:
        """APIError stores list detail (validation errors)."""
        detail: list[dict[str, object]] = [
            {"field": "email", "msg": "Invalid email"},
            {"field": "name", "msg": "Too short"},
        ]
        err = APIError(
            status_code=422,
            detail=detail,
            request_id="req-val",
        )
        assert err.detail == detail
        assert isinstance(err.detail, list)


class TestTransportError:
    """Tests for TransportError attributes."""

    def test_stores_original_and_message(self) -> None:
        """TransportError stores original exception and message."""
        original = ConnectionError("DNS failure")
        err = TransportError("Network issue", original=original)
        assert err.original is original
        assert str(err) == "Network issue"

    def test_original_default_none(self) -> None:
        """TransportError original defaults to None."""
        err = TransportError("Something failed")
        assert err.original is None
