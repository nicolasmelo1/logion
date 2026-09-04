"""Regression coverage for the standalone scenario actor checker."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "check_scenario_actors.py"


def _module():
    spec = importlib.util.spec_from_file_location("scenario_actors", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_records_keeps_only_direct_phase_entries_and_multiline_goals() -> None:
    module = _module()
    lines = [
        "phases:",
        "  - id: seed",
        "    actor: operator",
        '    goal: ""',
        "    local_hook_args:",
        "      - seed",
        "  - id: operate",
        "    actor: operator",
        "    goal: |",
        "      Execute the measured flow.",
        "      Keep the evidence directory intact.",
        "    assertions:",
        "      - type: files.exists",
    ]

    assert module._records(lines, "phases") == [
        {"id": "seed", "actor": "operator", "goal": '""', "local_hook_args": ""},
        {
            "id": "operate",
            "actor": "operator",
            "goal": "Execute the measured flow. Keep the evidence directory intact.",
            "assertions": "",
        },
    ]
