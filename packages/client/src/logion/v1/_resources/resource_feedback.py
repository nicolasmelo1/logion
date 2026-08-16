# SPDX-License-Identifier: MIT
"""Resource feedback resource — ratings, reviews, and summaries."""

from __future__ import annotations

from logion._http import HttpClient
from logion._json import JsonObject


class ResourceFeedbackResource:
    """Submit and browse resource-use feedback (ratings and reviews)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def submit(
        self,
        resource_id: str,
        version_id: str,
        *,
        rating: int,
        acquisition_channel: str,
        task_class: str,
        usefulness: int | None = None,
        reliability: int | None = None,
        tool_safety: int | None = None,
        token_efficiency: int | None = None,
        completed_task: bool | None = None,
        body: str | None = None,
        source_receipt_id: str | None = None,
    ) -> JsonObject:
        """Submit feedback for a resource version.

        Parameters
        ----------
        resource_id:
            UUID of the resource being reviewed.
        version_id:
            UUID of the specific resource version.
        rating:
            Overall rating (1-5).
        usefulness, reliability, tool_safety, token_efficiency:
            Optional sub-scores (1-5).
        completed_task:
            Whether the resource successfully completed the task.
        task_class:
            Classification of the task (e.g. ``software-development``).
        body:
            Optional free-text review.
        """
        payload: JsonObject = {
            "rating": rating,
            "acquisition_channel": acquisition_channel,
            "task_class": task_class,
        }
        if usefulness is not None:
            payload["usefulness"] = usefulness
        if reliability is not None:
            payload["reliability"] = reliability
        if tool_safety is not None:
            payload["tool_safety"] = tool_safety
        if token_efficiency is not None:
            payload["token_efficiency"] = token_efficiency
        if completed_task is not None:
            payload["completed_task"] = completed_task
        if body is not None:
            payload["body"] = body
        if source_receipt_id is not None:
            payload["source_receipt_id"] = source_receipt_id
        return self._http.request_object(
            "POST",
            f"/v1/resources/{resource_id}/versions/{version_id}/feedback",
            json=payload,
        )

    def list_mine(self) -> list[JsonObject]:
        """List feedback submitted by the authenticated user."""
        return self._http.request_items("GET", "/v1/feedback/mine")

    def list_for_resource(self, resource_id: str) -> list[JsonObject]:
        """List public feedback for a specific resource."""
        return self._http.request_items(
            "GET",
            f"/v1/resources/{resource_id}/feedback",
        )

    def get_summary(self, resource_id: str) -> JsonObject:
        """Get aggregated feedback summary for a resource."""
        return self._http.request_object(
            "GET",
            f"/v1/resources/{resource_id}/feedback/summary",
        )
