# SPDX-License-Identifier: MIT
"""Validation helpers for the minimum-disclosure observation envelope."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from cli._harness.scopes import VALID_SCOPES

ALLOWED_EVENTS = frozenset({"resource.use.completed"})
ALLOWED_OUTCOMES = frozenset({"completed", "failed", "abandoned", "unknown"})
OPAQUE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
FORBIDDEN_KEY_SUBSTRINGS: tuple[str, ...] = (
    "prompt",
    "source_code",
    "source",
    "code",
    "path",
    "tool_arg",
    "argument",
    "secret",
    "token",
    "key",
    "password",
    "credential",
    "model_context",
    "context",
    "terminal",
    "stdout",
    "stderr",
    "output",
    "request",
    "response",
    "body",
    "payload",
    "raw",
    "task_data",
    "task_input",
    "task_output",
    "content",
)
FORBIDDEN_NAME_EXCEPTIONS = frozenset({"resource_version_id"})


def validate_envelope_fields(
    *,
    event: str,
    harness: str,
    harness_session_id: str,
    installation_id: str,
    resource_version_id: str | None,
    scope_kind: str,
    scope_id: str,
    task_class: str | None,
    outcome: str,
    started_at: str,
    finished_at: str,
    integration_version: str,
    expected_version: str,
) -> None:
    if event not in ALLOWED_EVENTS:
        raise ValueError(f"unsupported observation event: {event!r}")
    if outcome not in ALLOWED_OUTCOMES:
        raise ValueError(f"unsupported observation outcome: {outcome!r}")
    if scope_kind not in VALID_SCOPES:
        raise ValueError(f"non-canonical observation scope: {scope_kind!r}")
    if integration_version != expected_version:
        raise ValueError(
            f"unsupported integration version: {integration_version!r}"
        )
    identifiers = {
        "harness_session_id": harness_session_id,
        "installation_id": installation_id,
        "scope_id": scope_id,
    }
    if resource_version_id is not None:
        identifiers["resource_version_id"] = resource_version_id
    for field_name, value in identifiers.items():
        if not OPAQUE_ID_RE.fullmatch(value):
            raise ValueError(
                f"{field_name} must be an opaque identifier "
                "without paths or whitespace"
            )
    _validate_slug("harness", harness)
    if task_class is not None:
        _validate_slug("task_class", task_class)
    started = _parse_rfc3339("started_at", started_at)
    finished = _parse_rfc3339("finished_at", finished_at)
    if finished < started:
        raise ValueError("finished_at must not precede started_at")


def assert_allowed_payload_keys(
    payload: dict[str, Any], allowed_field_names: frozenset[str]
) -> None:
    for key in payload:
        forbidden_name = any(
            part in key.lower() for part in FORBIDDEN_KEY_SUBSTRINGS
        )
        if key not in allowed_field_names or (
            forbidden_name and key not in FORBIDDEN_NAME_EXCEPTIONS
        ):
            raise ValueError(
                f"observation envelope field {key!r} is not permitted"
                " — forbidden raw-task-data field"
            )


def _validate_slug(field_name: str, value: str) -> None:
    if not SLUG_RE.fullmatch(value):
        raise ValueError(f"{field_name} must be a lowercase slug")


def _parse_rfc3339(field_name: str, value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be RFC3339") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")
    return parsed.astimezone(UTC)
