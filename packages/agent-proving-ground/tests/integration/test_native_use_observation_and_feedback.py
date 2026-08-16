from agent_proving_ground.scenarios.loader import load_scenario


def test_native_feedback_scenario_uses_real_local_stack() -> None:
    scenario = load_scenario("builtin:native_use_observation_and_feedback")
    assert scenario.api_adapter == "local-devrig"
    assert {agent.driver for agent in scenario.agents} == {"codex"}
    assert scenario.driver_config["codex"]["model"] == "gpt-5.4-mini"


def test_native_feedback_scenario_keeps_required_observed_effects() -> None:
    scenario = load_scenario("builtin:native_use_observation_and_feedback")
    assertion_types = {
        assertion.type
        for phase in scenario.phases
        for assertion in phase.assertions
    } | {assertion.type for assertion in scenario.final_assertions}
    assert {
        "files.native_use_observed",
        "files.feedback_pending",
        "files.usage_pending_empty",
        "api.resource_feedback_exists",
        "api.feedback_linked_to_acquisition",
        "api.course_review_projection_exists",
        "api.raw_observation_not_uploaded",
        "api.feedback_submission_idempotent",
        "logs.no_500s",
    }.issubset(assertion_types)
