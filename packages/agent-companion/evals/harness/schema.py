# SPDX-License-Identifier: MIT
"""Schemas for scenarios, catalogs, and tool traces.

These are validated at load time so a malformed YAML fails fast instead of
producing a misleading grading result. Validation is intentionally simple
(no pydantic) to keep the harness dependency footprint minimal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from evals.harness._json import JsonObject, JsonValue

KNOWN_TOOLS = {
    "logion_bounties_create",
    "logion_bounties_fund",
    "logion_bounties_get",
    "logion_bounties_ls",
    "logion_bounties_open",
    "logion_bounties_submission_create",
    "logion_course_reviews_list",
    "logion_courses_capabilities_print",
    "logion_courses_capabilities_validate",
    "logion_courses_create",
    "logion_courses_get",
    "logion_courses_feedback",
    "logion_courses_publication_latest",
    "logion_courses_publication_request",
    "logion_courses_report_usage",
    "logion_courses_update",
    "logion_courses_uploads_complete",
    "logion_courses_uploads_create",
    "logion_courses_uploads_push",
    "logion_listings_search",
    "logion_notifications_list",
    "logion_notifications_unread_count",
    "logion_credits_top_up",
    "logion_indexed_get",
    "logion_payments_onboarding_link",
    "logion_payments_orders_get",
    "logion_payments_seller_readiness",
    "logion_recall_search",
    "logion_reports_create",
    "logion_skills_install",
    "logion_skills_inspect",
    "logion_skills_permission_expand",
    "logion_skills_update",
    "logion_skills_updates",
}


class SchemaError(ValueError):
    """Raised when a scenario or catalog file violates the schema."""


@dataclass(frozen=True)
class CatalogCourse:
    id: str
    name: str
    summary: str
    price_usd: float
    review_status: str
    required_tools: tuple[str, ...]
    required_env: tuple[str, ...]
    capability_ids: tuple[str, ...]
    tags: tuple[str, ...]
    rating_avg: float | None = None
    rating_count: int = 0
    latest_version_review_status: str = ""

    @property
    def is_free(self) -> bool:
        return self.price_usd == 0


@dataclass(frozen=True)
class Catalog:
    version: int
    courses: tuple[CatalogCourse, ...]

    def by_id(self, course_id: str) -> CatalogCourse | None:
        for course in self.courses:
            if course.id == course_id:
                return course
        return None

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(c.id for c in self.courses)


@dataclass(frozen=True)
class ToolCall:
    tool: str
    args: JsonObject


@dataclass(frozen=True)
class Trace:
    scenario_id: str
    model: str
    calls: tuple[ToolCall, ...]
    final_answer: str
    selected_course_ids: tuple[str, ...]
    loaded_skill_ids: tuple[str, ...]
    token_estimate: dict[str, int]

    def tools_called(self) -> list[str]:
        return [c.tool for c in self.calls]


@dataclass(frozen=True)
class Expected:
    should_query_marketplace: bool | None = None
    should_install: bool | None = None
    should_ask_confirmation: bool | None = None
    should_run_recall: bool | None = None
    acceptable_course_ids: tuple[str, ...] = ()
    forbidden_course_ids: tuple[str, ...] = ()
    max_courses_inspected: int | None = None
    max_loaded_skills: int | None = None
    max_listings_limit: int | None = None
    must_mention: tuple[str, ...] = ()
    must_not_mention: tuple[str, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    required_tools: tuple[str, ...] = ()
    required_tool_sequence: tuple[str, ...] = ()
    recall_bypass_allowed: bool = False


@dataclass(frozen=True)
class FakeTrace:
    """Trace the fake provider replays for this scenario."""

    calls: tuple[ToolCall, ...]
    final_answer: str
    selected_course_ids: tuple[str, ...] = ()
    loaded_skill_ids: tuple[str, ...] = ()
    token_estimate: dict[str, int] = field(
        default_factory=lambda: {"input": 0, "output": 0}
    )


@dataclass(frozen=True)
class Scenario:
    id: str
    prompt: str
    suite: str
    installed_capabilities: tuple[str, ...]
    local_recall: tuple[JsonObject, ...]
    catalog_fixture: str
    expected: Expected
    fake_trace: FakeTrace
    notes: str = ""


def _as_tuple(value: JsonValue, *, kind: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise SchemaError(f"{kind} must be a list, got {type(value).__name__}")
    return tuple(str(v) for v in value)


def _load_local_recall(value: JsonValue) -> tuple[JsonObject, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise SchemaError(
            f"local_recall must be a list, got {type(value).__name__}"
        )
    entries: list[JsonObject] = []
    for entry in value:
        if not isinstance(entry, dict):
            raise SchemaError(
                f"Each local_recall entry must be a mapping: {entry!r}"
            )
        entries.append(dict(entry))
    return tuple(entries)


def _load_token_estimate(value: JsonValue) -> dict[str, int]:
    if value is None:
        value = {"input": 0, "output": 0}
    if not isinstance(value, dict):
        raise SchemaError("'token_estimate' must be a mapping")

    token_estimate: dict[str, int] = {}
    for key in ("input", "output"):
        raw = value.get(key, 0)
        try:
            parsed = int(raw)
        except (TypeError, ValueError) as exc:
            raise SchemaError(
                f"token_estimate.{key} must be an integer, got {raw!r}"
            ) from exc
        if parsed < 0:
            raise SchemaError(
                f"token_estimate.{key} must be non-negative, got {raw!r}"
            )
        token_estimate[key] = parsed
    return token_estimate


def _optional_bool(value: JsonValue, *, kind: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise SchemaError(f"{kind} must be a boolean, got {value!r}")
    return value


def _optional_non_negative_int(value: JsonValue, *, kind: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaError(
            f"{kind} must be a non-negative integer, got {value!r}"
        )
    if value < 0:
        raise SchemaError(
            f"{kind} must be a non-negative integer, got {value!r}"
        )
    return value


def load_catalog(  # noqa: C901 - one shape check per catalog field,
    # each with its own SchemaError message; splitting them would
    # scatter the schema definition across a dozen helpers.
    path: Path,
) -> Catalog:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SchemaError(f"Catalog {path} must be a mapping")
    if raw.get("version") != 1:
        raise SchemaError(f"Catalog {path} must declare version: 1")
    courses_raw = raw.get("courses")
    if not isinstance(courses_raw, list) or not courses_raw:
        raise SchemaError(
            f"Catalog {path} must have a non-empty 'courses' list"
        )
    courses: list[CatalogCourse] = []
    seen: set[str] = set()
    for entry in courses_raw:
        if not isinstance(entry, dict):
            raise SchemaError(
                f"Catalog course entry must be a mapping: {entry!r}"
            )
        course_id = entry.get("id")
        if not isinstance(course_id, str) or not course_id:
            raise SchemaError(f"Catalog course missing id: {entry!r}")
        if course_id in seen:
            raise SchemaError(f"Catalog has duplicate course id: {course_id}")
        seen.add(course_id)
        price = entry.get("price_usd", 0)
        if not isinstance(price, (int, float)) or price < 0:
            raise SchemaError(
                f"Course {course_id} has invalid price_usd: {price!r}"
            )
        valid_statuses = {"approved", "pending", "rejected", "in_review"}
        review_status = entry.get("review_status", "approved")
        if review_status not in valid_statuses:
            raise SchemaError(
                f"Course {course_id} has invalid review_status: "
                f"{review_status!r}"
            )
        rating_avg_raw = entry.get("rating_avg")
        if rating_avg_raw is not None and not isinstance(
            rating_avg_raw, (int, float)
        ):
            raise SchemaError(
                "Course "
                f"{course_id} has invalid rating_avg: {rating_avg_raw!r}"
            )
        rating_count_raw = entry.get("rating_count", 0)
        if (
            isinstance(rating_count_raw, bool)
            or not isinstance(rating_count_raw, int)
            or rating_count_raw < 0
        ):
            raise SchemaError(
                "Course "
                f"{course_id} has invalid rating_count: "
                f"{rating_count_raw!r}"
            )
        valid_review_statuses = {
            "approved",
            "pending",
            "rejected",
            "in_review",
        }
        latest_version_review_status = entry.get(
            "latest_version_review_status", review_status
        )
        if latest_version_review_status not in valid_review_statuses:
            raise SchemaError(
                "Course "
                f"{course_id} has invalid latest_version_review_status: "
                f"{latest_version_review_status!r}"
            )
        courses.append(
            CatalogCourse(
                id=course_id,
                name=str(entry.get("name", course_id)),
                summary=str(entry.get("summary", "")).strip(),
                price_usd=float(price),
                review_status=review_status,
                required_tools=_as_tuple(
                    entry.get("required_tools"), kind="required_tools"
                ),
                required_env=_as_tuple(
                    entry.get("required_env"), kind="required_env"
                ),
                capability_ids=_as_tuple(
                    entry.get("capability_ids"), kind="capability_ids"
                ),
                tags=_as_tuple(entry.get("tags"), kind="tags"),
                rating_avg=(
                    float(rating_avg_raw)
                    if rating_avg_raw is not None
                    else None
                ),
                rating_count=rating_count_raw,
                latest_version_review_status=latest_version_review_status,
            )
        )
    return Catalog(version=1, courses=tuple(courses))


def _load_expected(raw: JsonObject) -> Expected:
    if not isinstance(raw, dict):
        raise SchemaError("'expected' must be a mapping")
    allowed_keys = {
        "should_query_marketplace",
        "should_install",
        "should_ask_confirmation",
        "should_run_recall",
        "acceptable_course_ids",
        "forbidden_course_ids",
        "max_courses_inspected",
        "max_loaded_skills",
        "max_listings_limit",
        "must_mention",
        "must_not_mention",
        "forbidden_tools",
        "required_tools",
        "required_tool_sequence",
        "recall_bypass_allowed",
    }
    unknown = set(raw) - allowed_keys
    if unknown:
        raise SchemaError(f"Unknown 'expected' keys: {sorted(unknown)}")
    return Expected(
        should_query_marketplace=_optional_bool(
            raw.get("should_query_marketplace"),
            kind="should_query_marketplace",
        ),
        should_install=_optional_bool(
            raw.get("should_install"),
            kind="should_install",
        ),
        should_ask_confirmation=_optional_bool(
            raw.get("should_ask_confirmation"),
            kind="should_ask_confirmation",
        ),
        should_run_recall=_optional_bool(
            raw.get("should_run_recall"),
            kind="should_run_recall",
        ),
        acceptable_course_ids=_as_tuple(
            raw.get("acceptable_course_ids"), kind="acceptable_course_ids"
        ),
        forbidden_course_ids=_as_tuple(
            raw.get("forbidden_course_ids"), kind="forbidden_course_ids"
        ),
        max_courses_inspected=_optional_non_negative_int(
            raw.get("max_courses_inspected"),
            kind="max_courses_inspected",
        ),
        max_loaded_skills=_optional_non_negative_int(
            raw.get("max_loaded_skills"),
            kind="max_loaded_skills",
        ),
        max_listings_limit=_optional_non_negative_int(
            raw.get("max_listings_limit"),
            kind="max_listings_limit",
        ),
        must_mention=_as_tuple(raw.get("must_mention"), kind="must_mention"),
        must_not_mention=_as_tuple(
            raw.get("must_not_mention"), kind="must_not_mention"
        ),
        forbidden_tools=_as_tuple(
            raw.get("forbidden_tools"), kind="forbidden_tools"
        ),
        required_tools=_as_tuple(
            raw.get("required_tools"), kind="required_tools"
        ),
        required_tool_sequence=_as_tuple(
            raw.get("required_tool_sequence"), kind="required_tool_sequence"
        ),
        recall_bypass_allowed=_optional_bool(
            raw.get("recall_bypass_allowed", False),
            kind="recall_bypass_allowed",
        )
        or False,
    )


def _load_calls(raw: JsonValue) -> tuple[ToolCall, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise SchemaError("'calls' must be a list")
    calls: list[ToolCall] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise SchemaError(f"Each call must be a mapping: {entry!r}")
        tool = entry.get("tool")
        if not isinstance(tool, str) or tool not in KNOWN_TOOLS:
            raise SchemaError(
                f"Unknown tool {tool!r}; allowed: {sorted(KNOWN_TOOLS)}"
            )
        args = entry.get("args", {})
        if not isinstance(args, dict):
            raise SchemaError(
                f"Call args must be a mapping for tool {tool}: {args!r}"
            )
        calls.append(ToolCall(tool=tool, args=dict(args)))
    return tuple(calls)


def _load_fake_trace(raw: JsonValue) -> FakeTrace:
    if not isinstance(raw, dict):
        raise SchemaError("'fake_trace' must be a mapping")
    return FakeTrace(
        calls=_load_calls(raw.get("calls")),
        final_answer=str(raw.get("final_answer", "")),
        selected_course_ids=_as_tuple(
            raw.get("selected_course_ids"), kind="selected_course_ids"
        ),
        loaded_skill_ids=_as_tuple(
            raw.get("loaded_skill_ids"), kind="loaded_skill_ids"
        ),
        token_estimate=_load_token_estimate(raw.get("token_estimate")),
    )


def load_scenarios_from_file(
    path: Path, *, suite: str | None = None
) -> list[Scenario]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SchemaError(f"Scenario file {path} must be a mapping")
    scenarios_raw = raw.get("scenarios")
    if not isinstance(scenarios_raw, list) or not scenarios_raw:
        raise SchemaError(
            f"Scenario file {path} must contain a non-empty 'scenarios' list"
        )
    suite_name = suite or raw.get("suite") or path.stem
    out: list[Scenario] = []
    seen: set[str] = set()
    for entry in scenarios_raw:
        if not isinstance(entry, dict):
            raise SchemaError(f"Scenario must be a mapping: {entry!r}")
        scenario_id = entry.get("id")
        if not isinstance(scenario_id, str) or not scenario_id:
            raise SchemaError(f"Scenario in {path} is missing 'id'")
        if scenario_id in seen:
            raise SchemaError(
                f"Duplicate scenario id in {path}: {scenario_id}"
            )
        seen.add(scenario_id)
        prompt = entry.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise SchemaError(
                f"Scenario {scenario_id} missing non-empty 'prompt'"
            )
        catalog_fixture = entry.get("catalog_fixture")
        if not isinstance(catalog_fixture, str) or not catalog_fixture:
            raise SchemaError(
                f"Scenario {scenario_id} missing 'catalog_fixture'"
            )
        out.append(
            Scenario(
                id=scenario_id,
                prompt=prompt,
                suite=str(suite_name),
                installed_capabilities=_as_tuple(
                    entry.get("installed_capabilities"),
                    kind="installed_capabilities",
                ),
                local_recall=_load_local_recall(entry.get("local_recall")),
                catalog_fixture=catalog_fixture,
                expected=_load_expected(entry.get("expected", {})),
                fake_trace=_load_fake_trace(entry.get("fake_trace", {})),
                notes=str(entry.get("notes", "")),
            )
        )
    return out


def load_scenarios_from_dir(scenarios_dir: Path) -> list[Scenario]:
    if not scenarios_dir.is_dir():
        raise SchemaError(f"Scenarios directory missing: {scenarios_dir}")
    scenarios: list[Scenario] = []
    ids_seen: set[str] = set()
    for path in sorted(scenarios_dir.glob("*.yaml")):
        for scenario in load_scenarios_from_file(path):
            if scenario.id in ids_seen:
                raise SchemaError(
                    f"Duplicate scenario id across suite files: {scenario.id}"
                )
            ids_seen.add(scenario.id)
            scenarios.append(scenario)
    return scenarios
