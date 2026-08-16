# SPDX-License-Identifier: MIT
"""Tests for ResourceFeedbackResource client class."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from logion._http import HttpClient
from logion.v1._resources.resource_feedback import ResourceFeedbackResource
from logion.v1._resources.usage_receipts import UsageReceiptResource

RESOURCE_ID = "123e4567-e89b-12d3-a456-426614174000"
VERSION_ID = "123e4567-e89b-12d3-a456-426614174001"


class TestResourceFeedbackSubmit:
    def test_submit_calls_post(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request.return_value = {"feedback_id": "fb-001"}
        resource = ResourceFeedbackResource(http)

        result = resource.submit(
            RESOURCE_ID,
            VERSION_ID,
            rating=4,
            acquisition_channel="logion-marketplace",
            usefulness=5,
            completed_task=True,
            task_class="software-development",
            body="Great resource",
        )

        assert result == {"feedback_id": "fb-001"}
        http.request.assert_called_once()
        call_args = http.request.call_args
        assert call_args.args[0] == "POST"
        assert (
            call_args.args[1]
            == f"/v1/resources/{RESOURCE_ID}/versions/{VERSION_ID}/feedback"
        )
        json_body = call_args.kwargs["json"]
        assert json_body["rating"] == 4
        assert json_body["usefulness"] == 5
        assert json_body["completed_task"] is True
        assert json_body["task_class"] == "software-development"
        assert json_body["body"] == "Great resource"

    def test_submit_all_scores(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request.return_value = {"feedback_id": "fb-003"}
        resource = ResourceFeedbackResource(http)

        resource.submit(
            RESOURCE_ID,
            VERSION_ID,
            rating=5,
            acquisition_channel="logion-marketplace",
            task_class="coding",
            usefulness=4,
            reliability=5,
            tool_safety=4,
            token_efficiency=3,
        )

        json_body = http.request.call_args.kwargs["json"]
        assert json_body["rating"] == 5
        assert json_body["usefulness"] == 4
        assert json_body["reliability"] == 5
        assert json_body["tool_safety"] == 4
        assert json_body["token_efficiency"] == 3

    def test_submit_raises_on_non_dict_response(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request.return_value = ["not", "a", "dict"]
        resource = ResourceFeedbackResource(http)

        with pytest.raises(TypeError, match="Expected a JSON object"):
            resource.submit(
                RESOURCE_ID,
                VERSION_ID,
                rating=4,
                acquisition_channel="logion-marketplace",
                task_class="coding",
            )


class TestResourceFeedbackListMine:
    def test_list_mine_calls_get(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request.return_value = [{"feedback_id": "fb-001", "rating": 4}]
        resource = ResourceFeedbackResource(http)

        result = resource.list_mine()

        assert result == [{"feedback_id": "fb-001", "rating": 4}]
        http.request.assert_called_once_with("GET", "/v1/feedback/mine")

    def test_list_mine_raises_on_non_list_response(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request.return_value = {"not": "a list"}
        resource = ResourceFeedbackResource(http)

        with pytest.raises(TypeError, match="Expected a JSON array"):
            resource.list_mine()


class TestResourceFeedbackListForResource:
    def test_list_for_resource_calls_get(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request.return_value = [{"feedback_id": "fb-001", "rating": 4}]
        resource = ResourceFeedbackResource(http)

        result = resource.list_for_resource(RESOURCE_ID)

        assert result == [{"feedback_id": "fb-001", "rating": 4}]
        http.request.assert_called_once_with(
            "GET",
            f"/v1/resources/{RESOURCE_ID}/feedback",
        )

    def test_list_for_resource_raises_on_non_list_response(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request.return_value = {"not": "a list"}
        resource = ResourceFeedbackResource(http)

        with pytest.raises(TypeError, match="Expected a JSON array"):
            resource.list_for_resource(RESOURCE_ID)


class TestResourceFeedbackGetSummary:
    def test_get_summary_calls_get(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request.return_value = {
            "resource_id": RESOURCE_ID,
            "total_feedback": 5,
            "average_rating": 4.2,
        }
        resource = ResourceFeedbackResource(http)

        result = resource.get_summary(RESOURCE_ID)

        assert result["total_feedback"] == 5
        assert result["average_rating"] == 4.2
        http.request.assert_called_once_with(
            "GET",
            f"/v1/resources/{RESOURCE_ID}/feedback/summary",
        )

    def test_get_summary_raises_on_non_dict_response(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request.return_value = ["not", "a", "dict"]
        resource = ResourceFeedbackResource(http)

        with pytest.raises(TypeError, match="Expected a JSON object"):
            resource.get_summary(RESOURCE_ID)


class TestUsageReceiptSubmit:
    def test_submit_calls_post(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request.return_value = {"receipt_id": "r-001"}
        resource = UsageReceiptResource(http)

        result = resource.submit(
            RESOURCE_ID,
            VERSION_ID,
            observation_id="123e4567-e89b-12d3-a456-426614174002",
            task_class="software-development",
            harness="codex",
            outcome="completed",
            acquisition_channel="logion-marketplace",
            consent_policy_digest="sha256:policy",
        )

        assert result == {"receipt_id": "r-001"}
        http.request.assert_called_once()
        call_args = http.request.call_args
        assert call_args.args[0] == "POST"
        assert (
            call_args.args[1] == f"/v1/resources/{RESOURCE_ID}/versions/"
            f"{VERSION_ID}/usage-receipts"
        )
        json_body = call_args.kwargs["json"]
        assert json_body["task_class"] == "software-development"
        assert json_body["harness"] == "codex"
        assert json_body["outcome"] == "completed"
        assert json_body["acquisition_channel"] == "logion-marketplace"

    def test_submit_raises_on_non_dict_response(self) -> None:
        http = MagicMock(spec=HttpClient)
        http.request.return_value = ["not", "a", "dict"]
        resource = UsageReceiptResource(http)

        with pytest.raises(TypeError, match="Expected a JSON object"):
            resource.submit(
                RESOURCE_ID,
                VERSION_ID,
                observation_id="123e4567-e89b-12d3-a456-426614174002",
                task_class="coding",
                acquisition_channel="logion-marketplace",
                consent_policy_digest="sha256:policy",
            )


class TestV1NamespaceRegistration:
    def test_v1_namespace_has_resource_feedback(self) -> None:
        from logion._config import ClientConfig
        from logion._http import HttpClient
        from logion.v1 import V1Namespace

        config = ClientConfig(
            api_key="test",  # pragma: allowlist secret
            base_url="http://localhost",
        )
        http = HttpClient(config)
        try:
            ns = V1Namespace(http)
            assert hasattr(ns, "resource_feedback")
            assert isinstance(ns.resource_feedback, ResourceFeedbackResource)
        finally:
            http.close()

    def test_v1_namespace_has_usage_receipts(self) -> None:
        from logion._config import ClientConfig
        from logion._http import HttpClient
        from logion.v1 import V1Namespace

        config = ClientConfig(
            api_key="test",  # pragma: allowlist secret
            base_url="http://localhost",
        )
        http = HttpClient(config)
        try:
            ns = V1Namespace(http)
            assert hasattr(ns, "usage_receipts")
            assert isinstance(ns.usage_receipts, UsageReceiptResource)
        finally:
            http.close()
