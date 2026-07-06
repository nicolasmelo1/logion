from __future__ import annotations

from agent_proving_ground.api_adapters.mock import MockApiAdapter
from agent_proving_ground.assertions.base import AssertionContext
from agent_proving_ground.assertions.timeline import (
    TimelineNoUnredactedSecretAssertion,
)
from agent_proving_ground.models import World
from agent_proving_ground.redaction import redact_json, redact_text
from agent_proving_ground.timeline import Timeline


def test_redacts_bearer_token() -> None:
    text = "Authorization: bearer abcdef1234567890abcdef"
    assert redact_text(text) == "Authorization: bearer <redacted>"


def test_redacts_logion_api_key() -> None:
    text = "LOGION_API_KEY=logion_abc123def456"  # pragma: allowlist secret
    assert "<redacted>" in redact_text(text)


def test_redacts_nested_setup_token() -> None:
    data = {"user": {"setup_token": "secret-value-12345"}}
    result = redact_json(data)
    assert result["user"]["setup_token"] == "<redacted>"


def test_does_not_redact_course_title() -> None:
    text = "Course: Build a Logion CLI workflow"
    assert redact_text(text) == text


async def test_timeline_secret_assertion_detects_any_redactable_secret(
    tmp_path,
) -> None:
    timeline_path = tmp_path / "timeline.jsonl"
    timeline_path.write_text(
        (
            '{"type":"agent.turn.completed","summary":"github_token='
            "ghp_testtoken0123456789"
            'abcdef0123456789ab"}\n'
        ),
        encoding="utf-8",
    )
    ctx = AssertionContext(
        scenario_name="test",
        phase_id=None,
        world=World(run_id="r1", base_url="http://mock", root_dir=tmp_path),
        api=MockApiAdapter(),
        artifacts_dir=tmp_path,
        timeline=Timeline(timeline_path),
    )

    outcome = await TimelineNoUnredactedSecretAssertion().evaluate(ctx, {})

    assert outcome.status == "failed"
    assert "unredacted secret-like value" in outcome.message
    assert outcome.evidence == {
        "line": (
            '{"type":"agent.turn.completed","summary":"github_token='
            '<redacted>"}'
        )
    }
    ctx.timeline.close()
