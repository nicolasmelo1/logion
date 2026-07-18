"""Tests for bounded HTTP transport retries."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

from logion_indexer.transport import (
    GET_MAX_ATTEMPTS,
    GET_TIMEOUT_SECONDS,
    Transport,
)


def _response(body: bytes = b"ok") -> MagicMock:
    response = MagicMock()
    response.__enter__.return_value = response
    response.status = 200
    response.read.return_value = body
    response.headers = {}
    return response


def test_get_retries_transient_errors_then_succeeds() -> None:
    response = _response()
    with (
        patch(
            "logion_indexer.transport.urllib.request.urlopen",
            side_effect=[URLError("timeout"), TimeoutError(), response],
        ) as urlopen,
        patch("logion_indexer.transport.time.sleep") as sleep,
    ):
        result = Transport().get("https://example.com/archive.tar.gz")

    assert result.status == 200
    assert result.body == b"ok"
    assert urlopen.call_count == GET_MAX_ATTEMPTS
    assert all(
        call.kwargs["timeout"] == GET_TIMEOUT_SECONDS
        for call in urlopen.call_args_list
    )
    assert [call.args[0] for call in sleep.call_args_list] == [1, 2]


def test_get_raises_after_retry_budget_is_exhausted() -> None:
    with (
        patch(
            "logion_indexer.transport.urllib.request.urlopen",
            side_effect=URLError("timeout"),
        ) as urlopen,
        patch("logion_indexer.transport.time.sleep"),
        pytest.raises(URLError, match="timeout"),
    ):
        Transport().get("https://example.com/archive.tar.gz")

    assert urlopen.call_count == GET_MAX_ATTEMPTS
