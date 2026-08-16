# SPDX-License-Identifier: MIT
"""Tests for ResourcesResource client class."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from logion._http import HttpClient
from logion.v1._resources.resources import ResourcesResource

RESOURCE_ID = "123e4567-e89b-12d3-a456-426614174000"


class TestResourcesResourceSearch:
    def test_rejects_query_missing_from_public_contract(self) -> None:
        http = MagicMock(spec=HttpClient)
        resource = ResourcesResource(http)
        with pytest.raises(ValueError, match="does not support query"):
            resource.search(query="rag")
        http.request_object.assert_not_called()

    def test_rejects_tags_missing_from_public_contract(self) -> None:
        http = MagicMock(spec=HttpClient)
        resource = ResourcesResource(http)
        with pytest.raises(ValueError, match="does not support tags"):
            resource.search(tags="ai")
        http.request_object.assert_not_called()

    def test_search_with_contract_filters(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request_object.return_value = {"items": []}
        resource = ResourcesResource(http)
        resource.search(
            resource_type="agent_skill",
            lifecycle_status="active",
            limit=100,
            cursor="abc123",
        )
        http.request_object.assert_called_once_with(
            "GET",
            "/v1/resources",
            params={
                "resource_type": "agent_skill",
                "lifecycle_status": "active",
                "limit": 100,
                "cursor": "abc123",
            },
        )

    @pytest.mark.parametrize("limit", [0, 101, -1, True])
    def test_search_rejects_limit_outside_public_contract(
        self, limit: int
    ) -> None:
        http = MagicMock(spec=HttpClient)
        resource = ResourcesResource(http)
        with pytest.raises(ValueError, match="between 1 and 100"):
            resource.search(limit=limit)
        http.request_object.assert_not_called()

    def test_search_no_params(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request_object.return_value = {"items": []}
        resource = ResourcesResource(http)
        resource.search()
        http.request_object.assert_called_once_with(
            "GET", "/v1/resources", params={}
        )


class TestResourcesResourceGet:
    def test_get_by_resource_uuid(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request_object.return_value = {
            "resource": {"id": RESOURCE_ID, "title": "Hello"}
        }
        resource = ResourcesResource(http)
        result = resource.get(resource_id=RESOURCE_ID)
        http.request_object.assert_called_once_with(
            "GET", f"/v1/resources/{RESOURCE_ID}"
        )
        assert result["resource"]["title"] == "Hello"  # type: ignore[index]


class TestResourcesResourceVersions:
    def test_versions_with_defaults(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request_object.return_value = {"items": []}
        resource = ResourcesResource(http)
        resource.versions(resource_id=RESOURCE_ID)
        http.request_object.assert_called_once_with(
            "GET", f"/v1/resources/{RESOURCE_ID}/versions", params={}
        )

    def test_versions_with_limit(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request_object.return_value = {"items": []}
        resource = ResourcesResource(http)
        resource.versions(resource_id=RESOURCE_ID, limit=5)
        call_args = http.request_object.call_args
        assert call_args.kwargs["params"]["limit"] == 5

    @pytest.mark.parametrize("limit", [0, 101, -1, True])
    def test_versions_rejects_limit_outside_public_contract(
        self, limit: int
    ) -> None:
        http = MagicMock(spec=HttpClient)
        resource = ResourcesResource(http)
        with pytest.raises(ValueError, match="between 1 and 100"):
            resource.versions(resource_id=RESOURCE_ID, limit=limit)
        http.request_object.assert_not_called()

    def test_versions_rejects_cursor_missing_from_contract(self) -> None:
        http = MagicMock(spec=HttpClient)
        resource = ResourcesResource(http)
        with pytest.raises(ValueError, match="does not support cursor"):
            resource.versions(resource_id=RESOURCE_ID, cursor="next")
        http.request_object.assert_not_called()


class TestAcquisitionSurfaceContract:
    """Pin the acquisition wire contract the CLI depends on.

    These two operations are handwritten ahead of the generated contract
    sync, so nothing else checks that the SDK builds the paths, methods,
    and query parameters the backend actually publishes. Until the sync
    lands, this test is the contract.
    """

    VERSION_ID = "223e4567-e89b-12d3-a456-426614174111"

    def test_acquisition_plan_path_and_channel_param(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request_object.return_value = {}
        resource = ResourcesResource(http)
        resource.acquisition_plan(
            resource_id=RESOURCE_ID,
            version_id=self.VERSION_ID,
            channel="npx_skills",
        )
        http.request_object.assert_called_once_with(
            "GET",
            f"/v1/resources/{RESOURCE_ID}/versions/{self.VERSION_ID}"
            "/acquisition-plan",
            params={"channel": "npx_skills"},
        )

    def test_acquisition_plan_omits_unset_channel(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request_object.return_value = {}
        resource = ResourcesResource(http)
        resource.acquisition_plan(
            resource_id=RESOURCE_ID, version_id=self.VERSION_ID
        )
        assert http.request_object.call_args.kwargs["params"] == {}

    def test_acquisition_plan_percent_encodes_identifiers(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request_object.return_value = {}
        resource = ResourcesResource(http)
        resource.acquisition_plan(resource_id="a/../b", version_id="c d")
        path = http.request_object.call_args.args[1]
        assert "a%2F..%2Fb" in path
        assert "c%20d" in path

    def test_create_download_is_a_post_without_body(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request_object.return_value = {"files": []}
        resource = ResourcesResource(http)
        resource.create_download(
            resource_id=RESOURCE_ID, version_id=self.VERSION_ID
        )
        http.request_object.assert_called_once_with(
            "POST",
            f"/v1/resources/{RESOURCE_ID}/versions/{self.VERSION_ID}/download",
        )
