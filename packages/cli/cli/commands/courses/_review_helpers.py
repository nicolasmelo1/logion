"""Helper functions for courses reviews commands."""

from __future__ import annotations

from typing import Any

from cli._output import to_data


def data_or_model_dump(result: object) -> dict[str, Any]:
    """Return model_dump() for Pydantic models, else to_data."""
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")  # type: ignore[union-attr]
    return to_data(result)


def collect_reviews(
    client: object,
    course_id: str,
    version: str | None,
    limit: int | None,
) -> list[dict[str, Any]]:
    """Paginate through list_reviews and return all review dicts."""
    from cli._utils import only_not_none

    reviews: list[dict[str, Any]] = []
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
            data: dict[str, Any] = result.model_dump(mode="json")
        elif isinstance(result, dict):
            data = result
        else:
            import json

            data = json.loads(json.dumps(result, default=str))
        batch = data.get("reviews", [])
        reviews.extend(batch)
        next_cursor = data.get("next_cursor")
        if not next_cursor or (limit and len(reviews) >= limit):
            break
        cursor = next_cursor
    return reviews


def compute_summary(
    course_id: str,
    all_reviews: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the summary dict from a list of review dicts."""
    avg_score_fields = (
        "reliability",
        "usefulness",
        "tool_safety",
        "token_efficiency",
    )
    counted = [r for r in all_reviews if r.get("counts_toward_rating", True)]
    total = len(counted)
    summary: dict[str, Any] = {
        "course_id": course_id,
        "total_reviews": total,
    }
    if total > 0:
        avg_rating = sum(r.get("rating", 0) for r in counted) / total
        summary["avg_rating"] = round(avg_rating, 2)
        for field in avg_score_fields:
            vals = [r[field] for r in counted if r.get(field) is not None]
            if vals:
                summary[f"avg_{field}"] = round(sum(vals) / len(vals), 2)
    else:
        summary["avg_rating"] = None
    return summary
