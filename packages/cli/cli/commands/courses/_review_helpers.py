# SPDX-License-Identifier: MIT
"""Helper functions for courses reviews commands."""

from __future__ import annotations

from cli._json import JsonObject, elements, opt_int
from cli._output import to_object, truncate_summary


def data_or_model_dump(result: object) -> JsonObject:
    """Return the response as a JSON object.

    to_object already unwraps a Pydantic model, so the hasattr probe
    and its type: ignore are gone.
    """
    return to_object(result)


def collect_reviews(
    client: object,
    course_id: str,
    version: str | None,
    limit: int | None,
) -> list[JsonObject]:
    """Paginate through list_reviews and return all review dicts."""
    from cli._utils import only_not_none

    reviews: list[JsonObject] = []
    cursor: str | None = None
    page_size = limit or 100
    while True:
        kwargs = only_not_none(
            {"course_id": course_id},
            version=version,
            limit=page_size,
            cursor=cursor,
        )
        result = client.v1.courses.list_reviews(**kwargs)  # type: ignore[attr-defined]
        if hasattr(result, "model_dump"):
            data: JsonObject = result.model_dump(mode="json")
        elif isinstance(result, dict):
            data = result
        else:
            import json

            data = json.loads(json.dumps(result, default=str))
        batch = elements(data, "reviews")
        reviews.extend(batch)
        next_cursor = data.get("next_cursor")
        if not next_cursor or (limit and len(reviews) >= limit):
            break
        cursor = next_cursor
    return reviews[:limit] if limit is not None else reviews


def compute_summary(
    course_id: str,
    all_reviews: list[JsonObject],
) -> JsonObject:
    """Build the summary dict from a list of review dicts."""
    counted = [r for r in all_reviews if r.get("counts_toward_rating", True)]
    review_count = len(counted)
    rating_histogram = {str(score): 0 for score in range(1, 6)}
    for review in counted:
        rating = review.get("rating")
        if isinstance(rating, int) and 1 <= rating <= 5:
            rating_histogram[str(rating)] += 1

    summary: JsonObject = {
        "course_id": course_id,
        "review_count": review_count,
        "rating_avg": None,
        "rating_histogram": rating_histogram,
    }
    if review_count > 0:
        avg_rating = (
            sum(opt_int(r, "rating", 0) for r in counted) / review_count
        )
        summary["rating_avg"] = round(avg_rating, 2)
    return summary


def compact_review(review: JsonObject) -> JsonObject:
    """Build the compact review payload required by the CLI contract."""
    return {
        "review_id": review.get("review_id", review.get("id")),
        "rating": review.get("rating"),
        "body_excerpt": truncate_summary(
            review.get("body") if isinstance(review.get("body"), str) else None
        ),
        "agent_id": review.get("agent_id", review.get("reviewer_agent_id")),
        "version_id": review.get(
            "version_id", review.get("course_version_id")
        ),
        "created_at": review.get("created_at", review.get("submitted_at")),
    }
