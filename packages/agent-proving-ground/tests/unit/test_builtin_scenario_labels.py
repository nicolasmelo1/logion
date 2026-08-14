import re

from agent_proving_ground.config import BUILTIN_SCENARIOS_ROOT

PLANNING_PHASE_LABEL = re.compile(
    r"(?:phase|fase)[\s._-]*\d+(?:[._-]\d+)*",
    re.IGNORECASE,
)


def _builtin_scenario_paths():
    return sorted(BUILTIN_SCENARIOS_ROOT.glob("*.yaml"))


def test_builtin_scenario_filenames_do_not_use_planning_phase_labels() -> None:
    offenders = [
        path.name
        for path in _builtin_scenario_paths()
        if PLANNING_PHASE_LABEL.search(path.stem)
    ]

    assert offenders == [], (
        "builtin scenario filenames must describe behavior, "
        "not planning phases: "
        f"{offenders}"
    )


def test_builtin_scenario_content_does_not_use_planning_phase_labels() -> None:
    offenders = [
        path.name
        for path in _builtin_scenario_paths()
        if PLANNING_PHASE_LABEL.search(path.read_text(encoding="utf-8"))
    ]

    assert offenders == [], (
        "builtin scenario content must describe behavior, "
        "not planning phases: "
        f"{offenders}"
    )
