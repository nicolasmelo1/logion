"""Tests for the handwritten runner resource."""

from unittest.mock import MagicMock

import pytest

from logion._http import HttpClient
from logion.v1._resources.runners import RunnersResource


def test_enroll_runner_uses_public_endpoint() -> None:
    http = MagicMock(spec=HttpClient)
    http.request_object.return_value = {"runner_id": "runner-1"}

    result = RunnersResource(http).enroll("creator-runner")

    assert result == {"runner_id": "runner-1"}
    http.request_object.assert_called_once_with(
        "POST", "/v1/runners/enroll", json={"name": "creator-runner"}
    )


def test_enroll_runner_rejects_empty_name() -> None:
    http = MagicMock(spec=HttpClient)

    with pytest.raises(ValueError, match="must not be empty"):
        RunnersResource(http).enroll("  ")

    http.request_object.assert_not_called()


def test_enroll_strips_surrounding_whitespace() -> None:
    http = MagicMock(spec=HttpClient)
    RunnersResource(http).enroll("  creator-runner\t")
    http.request_object.assert_called_once_with(
        "POST", "/v1/runners/enroll", json={"name": "creator-runner"}
    )
