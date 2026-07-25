# SPDX-License-Identifier: MIT
"""Tests for ResourcesResource client class."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from logion._http import HttpClient
from logion.v1._resources.resources import ResourcesResource


class TestResourcesResourceSearch:
    def test_search_with_query(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request.return_value = {"items": []}
        resource = ResourcesResource(http)
        resource.search(query="rag")
        http.request.assert_called_once_with(
            "GET",
            "/v1/resources",
            params={"query": "rag"},
        )

    def test_search_with_resource_type(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request.return_value = {"items": []}
        resource = ResourcesResource(http)
        resource.search(query="test", resource_type="plugin")
        call_args = http.request.call_args
        params = call_args.kwargs["params"]
        assert params["query"] == "test"
        assert params["resource_type"] == "plugin"

    def test_search_with_all_params(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request.return_value = {"items": []}
        resource = ResourcesResource(http)
        resource.search(
            query="test",
            resource_type="skill",
            tags="python,ai",
            limit=10,
            cursor="abc123",
        )
        call_args = http.request.call_args
        params = call_args.kwargs["params"]
        assert params["query"] == "test"
        assert params["resource_type"] == "skill"
        assert params["tags"] == "python,ai"
        assert params["limit"] == 10
        assert params["cursor"] == "abc123"

    def test_search_no_params(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request.return_value = {"items": []}
        resource = ResourcesResource(http)
        resource.search()
        call_args = http.request.call_args
        params = call_args.kwargs["params"]
        assert params == {}

    def test_search_raises_on_non_dict_response(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request.return_value = ["not", "a", "dict"]
        resource = ResourcesResource(http)
        with pytest.raises(TypeError, match="Expected a JSON object"):
            resource.search(query="test")


class TestResourcesResourceGet:
    def test_get_by_resource_id(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request.return_value = {
            "canonical": "skill:gh:octocat/hello",
            "title": "Hello",
        }
        resource = ResourcesResource(http)
        result = resource.get(resource_id="skill:gh:octocat/hello")
        http.request.assert_called_once_with(
            "GET",
            "/v1/resources/skill%3Agh%3Aoctocat%2Fhello",
        )
        assert result["title"] == "Hello"

    def test_get_raises_on_non_dict_response(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request.return_value = "not a dict"
        resource = ResourcesResource(http)
        with pytest.raises(TypeError, match="Expected a JSON object"):
            resource.get(resource_id="skill:gh:octocat/hello")


class TestResourcesResourceVersions:
    def test_versions_with_defaults(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request.return_value = {"items": []}
        resource = ResourcesResource(http)
        resource.versions(resource_id="skill:gh:octocat/hello")
        http.request.assert_called_once_with(
            "GET",
            "/v1/resources/skill%3Agh%3Aoctocat%2Fhello/versions",
            params={},
        )

    def test_versions_with_limit(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request.return_value = {"items": []}
        resource = ResourcesResource(http)
        resource.versions(resource_id="skill:gh:octocat/hello", limit=5)
        call_args = http.request.call_args
        params = call_args.kwargs["params"]
        assert params["limit"] == 5

    def test_versions_raises_on_non_dict_response(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request.return_value = ["not", "a", "dict"]
        resource = ResourcesResource(http)
        with pytest.raises(TypeError, match="Expected a JSON object"):
            resource.versions(resource_id="skill:gh:octocat/hello")
