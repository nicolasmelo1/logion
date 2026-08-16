from agent_proving_ground.scenarios.loader import load_scenario


def test_remote_mcp_feedback_scenario_uses_real_local_stack() -> None:
    scenario = load_scenario("builtin:remote_private_mcp_feedback")
    assert scenario.api_adapter == "local-devrig"
    assert {agent.driver for agent in scenario.agents} == {"codex"}
    assert scenario.driver_config["codex"]["model"] == "gpt-5.4-mini"


def test_remote_mcp_feedback_scenario_keeps_required_observed_effects() -> (
    None
):
    scenario = load_scenario("builtin:remote_private_mcp_feedback")
    assertion_types = {
        assertion.type
        for phase in scenario.phases
        for assertion in phase.assertions
    } | {assertion.type for assertion in scenario.final_assertions}
    assert {
        "files.remote_mcp_reconciled",
        "files.vendor_install_unchanged",
        "files.no_mcp_proxy_installed",
        "api.remote_mcp_use_attributed",
        "api.original_publisher_preserved",
        "api.remote_mcp_feedback_linked",
        "api.remote_mcp_private_payload_not_recorded",
        "logs.no_500s",
    }.issubset(assertion_types)
