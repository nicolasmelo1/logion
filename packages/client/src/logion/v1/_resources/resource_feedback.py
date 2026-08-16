# SPDX-License-Identifier: MIT
"""Resource feedback resource — ratings, reviews, and summaries."""

from __future__ import annotations

from typing import Any

from logion._http import HttpClient


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
    ) -> dict[str, Any]:
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
        payload: dict[str, Any] = {
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
        result = self._http.request(
            "POST",
            f"/v1/resources/{resource_id}/versions/{version_id}/feedback",
            json=payload,
        )
        if not isinstance(result, dict):
            msg = (
                f"Expected a JSON object from POST feedback, "
                f"got {type(result).__name__}"
            )
            raise TypeError(msg)
        return result

    def list_mine(self) -> list[dict[str, Any]]:
        """List feedback submitted by the authenticated user."""
        result = self._http.request("GET", "/v1/feedback/mine")
        items: Any = (
            result.get("items") if isinstance(result, dict) else result
        )
        if not isinstance(items, list):
            msg = (
                f"Expected a JSON array from GET /v1/feedback/mine, "
                f"got {type(items).__name__}"
            )
            raise TypeError(msg)
        return items

    def list_for_resource(self, resource_id: str) -> list[dict[str, Any]]:
        """List public feedback for a specific resource."""
        result = self._http.request(
            "GET",
            f"/v1/resources/{resource_id}/feedback",
        )
        items: Any = (
            result.get("items") if isinstance(result, dict) else result
        )
        if not isinstance(items, list):
            msg = (
                f"Expected a JSON array from GET feedback, "
                f"got {type(items).__name__}"
            )
            raise TypeError(msg)
        return items

    def get_summary(self, resource_id: str) -> dict[str, Any]:
        """Get aggregated feedback summary for a resource."""
        result = self._http.request(
            "GET",
            f"/v1/resources/{resource_id}/feedback/summary",
        )
        if not isinstance(result, dict):
            msg = (
                f"Expected a JSON object from feedback summary, "
                f"got {type(result).__name__}"
            )
            raise TypeError(msg)
        return result
