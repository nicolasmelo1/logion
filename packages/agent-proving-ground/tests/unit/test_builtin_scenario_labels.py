import re

from agent_proving_ground.config import BUILTIN_SCENARIOS_ROOT

PLANNING_PHASE_LABEL = re.compile(
    r"(?:phase|fase)[\s._-]*\d+(?:[._-]\d+)*",
    re.IGNORECASE,
)

# The workspace contract-audit policy is the canonical phase gate: a
# phase's required scenario is matched by exact name, and the audit
# fails closed (PHASE_REQUIRED_SCENARIO_MISSING) when a builtin file
# with that name does not exist. Phase 15.14.1's policy entry names
# `phase_15_14_1_local_multi_agent_node`, written after (2026-08-26,
# workspace #156) the behavior-naming rule below (2026-08-14, #254).
# A scenario the canonical gate mandates by phase identity cannot be
# renamed on this side without breaking the gate, so policy-mandated
# names are declared here rather than silently diverging from the
# workspace. Every new builtin scenario should still be behavior-
# named; a phase-labelled name appears only when the workspace gate
# demands it.
POLICY_MANDATED_SCENARIO_NAMES = frozenset({
    "phase_15_14_1_local_multi_agent_node",
})


def _builtin_scenario_paths():
    return sorted(BUILTIN_SCENARIOS_ROOT.glob("*.yaml"))


def _policy_mandated_offenders(paths, extract):
    return [
        path.name
        for path in paths
        if path.stem not in POLICY_MANDATED_SCENARIO_NAMES
        and PLANNING_PHASE_LABEL.search(extract(path))
    ]


def test_builtin_scenario_filenames_do_not_use_planning_phase_labels() -> None:
    offenders = _policy_mandated_offenders(
        _builtin_scenario_paths(), lambda path: path.stem
    )

    assert offenders == [], (
        "builtin scenario filenames must describe behavior, "
        "not planning phases: "
        f"{offenders}"
    )


def test_builtin_scenario_content_does_not_use_planning_phase_labels() -> None:
    offenders = _policy_mandated_offenders(
        _builtin_scenario_paths(),
        lambda path: path.read_text(encoding="utf-8"),
    )

    assert offenders == [], (
        "builtin scenario content must describe behavior, "
        "not planning phases: "
        f"{offenders}"
    )


def test_policy_mandated_scenario_names_stay_minimal() -> None:
    """The exemption is a named set, not a regex relaxation.

    If this set grows, each new entry must correspond to a
    required_scenarios name in the workspace phase-integrity policy;
    a scenario named for a phase nothing mandates is still a
    violation. Keeping the set visible here makes every addition a
    reviewable decision instead of drift.
    """
    policy_mandated_files = [
        path
        for path in _builtin_scenario_paths()
        if path.stem in POLICY_MANDATED_SCENARIO_NAMES
    ]
    assert sorted(path.stem for path in policy_mandated_files) == sorted(
        POLICY_MANDATED_SCENARIO_NAMES
    ), (
        "every policy-mandated scenario name must exist as a builtin "
        "scenario file"
    )
