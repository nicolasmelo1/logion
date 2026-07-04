from __future__ import annotations

from logion_agent_proving_ground.redaction import redact_json, redact_text


def test_redacts_bearer_token() -> None:
    text = "Authorization: bearer abcdef1234567890abcdef"
    assert redact_text(text) == "Authorization: bearer <redacted>"


def test_redacts_logion_api_key() -> None:
    text = "LOGION_API_KEY=logion_abc123def456"
    assert "<redacted>" in redact_text(text)


def test_redacts_nested_setup_token() -> None:
    data = {"user": {"setup_token": "secret-value-12345"}}
    result = redact_json(data)
    assert result["user"]["setup_token"] == "<redacted>"


def test_does_not_redact_course_title() -> None:
    text = "Course: Build a Logion CLI workflow"
    assert redact_text(text) == text
