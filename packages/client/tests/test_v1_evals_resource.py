"""Tests for the handwritten evals resource."""

from unittest.mock import MagicMock

from logion._http import HttpClient
from logion.v1._resources.evals import EvalsResource


def test_get_contract_quotes_friendly_name_as_one_path_segment() -> None:
    http = MagicMock(spec=HttpClient)
    http.request_object.return_value = {"digest": "a" * 64}

    EvalsResource(http).get_contract("team/golden eval")

    http.request_object.assert_called_once_with(
        "GET", "/v1/evals/contracts/team%2Fgolden%20eval"
    )
