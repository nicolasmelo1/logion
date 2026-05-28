"""Tests for the v1 JSON output envelope helpers."""

from __future__ import annotations

import json

from cli._errors import ALLOWED_ERROR_CODES, emit_error_json
from cli._output import emit_json, truncate_summary


def test_emit_json_envelope_shape(capsys: object) -> None:
    """emit_json produces a v1 envelope with version, kind, and data."""
    emit_json("logion.recall.search", {"query": "test"})
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    payload = json.loads(captured.out)
    assert payload["version"] == "v1"
    assert "kind" in payload
    assert payload["kind"].startswith("logion.")
    assert "data" in payload


def test_emit_json_payload_is_kind_namespaced(capsys: object) -> None:
    """The kind string is passed through verbatim."""
    emit_json("logion.recall.search", [])
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    payload = json.loads(captured.out)
    assert payload["kind"] == "logion.recall.search"


def test_truncate_summary_long_text_appends_ellipsis() -> None:
    """Long text is truncated to max_len with a trailing ellipsis character."""
    text = "x" * 200
    result = truncate_summary(text, max_len=120)
    assert len(result) == 120
    assert result.endswith("…")
    assert result == "x" * 119 + "…"


def test_truncate_summary_short_text_unchanged() -> None:
    """Short text passes through unchanged."""
    text = "y" * 80
    assert truncate_summary(text) == text


def test_emit_error_json_includes_required_keys(capsys: object) -> None:
    """emit_error_json writes a v1 error envelope to stderr."""
    emit_error_json("not_found", "resource missing", 1)
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    payload = json.loads(captured.err)
    assert payload["version"] == "v1"
    assert payload["kind"] == "logion.error"
    assert payload["data"]["code"] == "not_found"
    assert payload["data"]["message"] == "resource missing"
    assert payload["data"]["exit_code"] == 1


def test_emit_error_json_code_is_in_allowed_set(capsys: object) -> None:
    """Every emitted error code must be a member of ALLOWED_ERROR_CODES."""
    code = "auth_missing"
    emit_error_json(code, "test", 1)
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    payload = json.loads(captured.err)
    assert payload["data"]["code"] in ALLOWED_ERROR_CODES
