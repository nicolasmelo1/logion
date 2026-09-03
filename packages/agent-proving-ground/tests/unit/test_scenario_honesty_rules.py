"""Rules that keep a scenario from claiming coverage it does not have.

Three failure modes, all observed in this package's own scenarios rather
than imagined:

* a scenario counted as agent coverage when every phase is a script;
* a goal that dictates the rating the agent is supposed to form, which
  turns the one deliberate-judgement signal class into a number the
  scenario author typed;
* a caption over rig work, which reads as an agent phase in every listing.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent_proving_ground.scenarios.loader import (
    list_builtin_scenarios,
    load_scenario,
)
from agent_proving_ground.scenarios.schema import ScenarioSpec

AGENTS = [{"id": "a", "role": "tester"}]


def _spec(**overrides) -> dict:
    base = {
        "name": "s",
        "description": "d",
        "agents": AGENTS,
        "phases": [{"id": "p", "actor": "a", "goal": "do the thing"}],
    }
    base.update(overrides)
    return base


def test_a_scenario_with_no_agent_phase_must_declare_itself_rig() -> None:
    scripted = _spec(
        phases=[{"id": "p", "actor": "a", "goal": "", "local_hook": "x.py"}]
    )
    with pytest.raises(ValidationError, match="kind: rig"):
        ScenarioSpec.model_validate(scripted)
    ScenarioSpec.model_validate({**scripted, "kind": "rig"})


def test_a_rig_scenario_may_not_send_a_goal_to_an_agent() -> None:
    with pytest.raises(ValidationError, match="declares kind: rig"):
        ScenarioSpec.model_validate(_spec(kind="rig"))


def test_a_goal_may_not_dictate_the_agents_rating() -> None:
    for flag in (
        "--rating 4",
        "--usefulness 4",
        "--reliability 3.5",
        "--tool-safety 5",
        "--token-efficiency 4",
    ):
        with pytest.raises(ValidationError, match="dictates a judgement"):
            ScenarioSpec.model_validate(
                _spec(
                    phases=[
                        {
                            "id": "p",
                            "actor": "a",
                            "goal": f"submit feedback {flag} --json",
                        }
                    ]
                )
            )


def test_a_success_hint_may_not_dictate_the_agents_rating() -> None:
    with pytest.raises(ValidationError, match="dictates a judgement"):
        ScenarioSpec.model_validate(
            _spec(
                phases=[
                    {
                        "id": "p",
                        "actor": "a",
                        "goal": "report on it",
                        "success_hint": "run it with --rating 5",
                    }
                ]
            )
        )


def test_a_placeholder_rating_is_allowed() -> None:
    """The shape of the command is plumbing; only the number is the claim."""
    ScenarioSpec.model_validate(
        _spec(
            phases=[
                {
                    "id": "p",
                    "actor": "a",
                    "goal": "submit feedback --rating <1-5> --json",
                }
            ]
        )
    )


def test_a_caption_over_rig_work_is_rejected() -> None:
    with pytest.raises(ValidationError, match="asserts nothing"):
        ScenarioSpec.model_validate(
            _spec(
                phases=[
                    {
                        "id": "p",
                        "actor": "a",
                        "goal": "Create the course",
                        "local_hook": "create_course.py",
                    }
                ]
            )
        )


def test_a_hook_that_prepares_state_the_agent_acts_on_is_allowed() -> None:
    """The legitimate shape: the rig sets up, the agent acts, and the
    phase asserts what the agent did."""
    ScenarioSpec.model_validate(
        _spec(
            phases=[
                {
                    "id": "p",
                    "actor": "a",
                    "goal": "One file was tampered with. Re-run reconcile.",
                    "local_hook": "tamper.py",
                    "assertions": [{"type": "files.exists"}],
                }
            ]
        )
    )


@pytest.mark.parametrize("name", list_builtin_scenarios())
def test_every_builtin_scenario_obeys_the_rules(name: str) -> None:
    """Loading is the check: the rules above are schema validators."""
    spec = load_scenario(f"builtin:{name}")
    assert bool(spec.agent_phase_ids) == (spec.kind == "agent")
