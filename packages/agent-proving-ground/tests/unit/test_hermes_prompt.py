"""Regression tests for the Hermes prompt builder.

These ensure that phase-specific scaffolding (course-creation hints,
bundle-upload syntax) is only injected into creator/publisher phases
and NOT into reviewer, learner, admin, or bounty phases.
"""

from __future__ import annotations

from logion_agent_proving_ground.drivers.hermes import (
    _build_prompt,
    _phase_scaffolding,
)


class TestPhaseScaffolding:
    """_phase_scaffolding must only emit creation hints for creator phases."""

    def test_creator_phase_includes_course_scaffolding(self) -> None:
        result = _phase_scaffolding("creator_publishes_course", "slug-123")
        assert len(result) > 0
        assert any("unique slug" in line for line in result)
        assert any("SKILL.md" in line for line in result)
        assert any("capabilities.yaml" in line for line in result)

    def test_publisher_phase_includes_course_scaffolding(self) -> None:
        result = _phase_scaffolding("publisher_publishes_course", "slug-456")
        assert len(result) > 0
        assert any("unique slug" in line for line in result)

    def test_admin_approve_phase_returns_empty(self) -> None:
        result = _phase_scaffolding("admin_approves_publication", "slug-789")
        assert result == []

    def test_learner_buy_phase_returns_empty(self) -> None:
        result = _phase_scaffolding("learner_buys_uses_reviews", "slug-abc")
        assert result == []

    def test_bounty_phase_returns_empty(self) -> None:
        result = _phase_scaffolding("creator_opens_bounty", "slug-def")
        assert result == []

    def test_bounty_submission_phase_returns_empty(self) -> None:
        result = _phase_scaffolding("learner_submits_bounty_work", "slug-ghi")
        assert result == []

    def test_bounty_accept_phase_returns_empty(self) -> None:
        result = _phase_scaffolding("creator_accepts_bounty", "slug-jkl")
        assert result == []

    def test_admin_review_phase_returns_empty(self) -> None:
        result = _phase_scaffolding(
            "admin_reviews_marketplace_state", "slug-mno"
        )
        assert result == []


class TestBuildPrompt:
    """_build_prompt must inject scaffolding only for creator phases."""

    def test_creator_prompt_contains_course_creation(self) -> None:
        prompt = _build_prompt(
            goal="Publish a course.",
            unique_slug="test-slug",
            phase_id="creator_publishes_course",
        )
        assert "Create a NEW course" in prompt
        assert "SKILL.md" in prompt
        assert "capabilities.yaml" in prompt

    def test_creator_prompt_contains_success_hint(self) -> None:
        prompt = _build_prompt(
            goal="Publish a course.",
            unique_slug="test-slug",
            success_hint="Use a unique slug.",
            phase_id="creator_publishes_course",
        )
        assert "Success hint: Use a unique slug." in prompt

    def test_admin_prompt_has_no_course_creation(self) -> None:
        prompt = _build_prompt(
            goal="Approve the pending course.",
            unique_slug="test-slug",
            phase_id="admin_approves_publication",
        )
        assert "Create a NEW course" not in prompt
        assert "SKILL.md" not in prompt
        assert "capabilities.yaml" not in prompt
        assert "Operational constraints:" in prompt

    def test_learner_prompt_has_no_course_creation(self) -> None:
        prompt = _build_prompt(
            goal="Buy and review the course.",
            unique_slug="test-slug",
            phase_id="learner_buys_uses_reviews",
        )
        assert "Create a NEW course" not in prompt
        assert "Operational constraints:" in prompt

    def test_bounty_prompt_has_no_course_creation(self) -> None:
        prompt = _build_prompt(
            goal="Open a bounty.",
            unique_slug="test-slug",
            phase_id="creator_opens_bounty",
        )
        assert "Create a NEW course" not in prompt

    def test_empty_phase_id_still_has_constraints(self) -> None:
        prompt = _build_prompt(
            goal="Do something.",
            unique_slug="test-slug",
        )
        assert "Operational constraints:" in prompt
        assert "Create a NEW course" not in prompt

    def test_result_marker_instructions_always_present(self) -> None:
        for phase in [
            "creator_publishes_course",
            "admin_approves_publication",
            "learner_buys_uses_reviews",
            "",
        ]:
            prompt = _build_prompt(
                goal="Do it.",
                unique_slug="slug",
                phase_id=phase,
            )
            assert "RESULT: completed" in prompt
