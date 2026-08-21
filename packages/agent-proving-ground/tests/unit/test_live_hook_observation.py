from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from agent_proving_ground.assertions.base import AssertionContext
from agent_proving_ground.assertions.files import (
    ObservationFromLiveHookAssertion,
)
from agent_proving_ground.models import World
from agent_proving_ground.runner import _CLI_SHIM
from agent_proving_ground.timeline import Timeline

#: Read at import time: the committed fixture is the payload the gate used
#: to replay, and this suite asserts it can no longer satisfy the gate.
FIXTURE_PAYLOAD = Path(
    "packages/cli/tests/fixtures/hook_payloads/claude_code_post_tool_use.json"
).read_text(encoding="utf-8")


async def _ctx(tmp_path: Path) -> AssertionContext:
    return AssertionContext(
        scenario_name="test",
        phase_id="p1",
        world=World(
            run_id="r1",
            base_url="http://example.test",
            root_dir=tmp_path,
            data={},
        ),
        api=None,  # type: ignore[arg-type]
        artifacts_dir=tmp_path,
        timeline=Timeline(tmp_path / "timeline.jsonl"),
    )


def _records(tmp_path: Path) -> Path:
    records = tmp_path / "hook-invocations"
    records.mkdir()
    return records


async def test_fails_when_harness_never_ran_the_hook(tmp_path) -> None:
    _records(tmp_path)
    result = await ObservationFromLiveHookAssertion().evaluate(
        await _ctx(tmp_path), {"invocations_dir": "hook-invocations"}
    )
    assert result.status == "failed"
    assert "never ran the installed hook" in result.message


async def test_fails_when_hook_ran_but_recorded_nothing(tmp_path) -> None:
    records = _records(tmp_path)
    (records / "1.stdin.json").write_text("{}", encoding="utf-8")
    result = await ObservationFromLiveHookAssertion().evaluate(
        await _ctx(tmp_path), {"invocations_dir": "hook-invocations"}
    )
    assert result.status == "failed"
    assert "recorded an observation" in result.message


async def test_fails_on_replayed_fixture_payload(tmp_path) -> None:
    records = _records(tmp_path)
    (records / "recorded.stdin.json").write_text(
        FIXTURE_PAYLOAD, encoding="utf-8"
    )
    result = await ObservationFromLiveHookAssertion().evaluate(
        await _ctx(tmp_path), {"invocations_dir": "hook-invocations"}
    )
    assert result.status == "failed"
    assert "placeholder" in result.message


async def test_fails_when_transcript_does_not_exist(tmp_path) -> None:
    records = _records(tmp_path)
    (records / "recorded.stdin.json").write_text(
        json.dumps({
            "session_id": "s1",
            "transcript_path": str(tmp_path / "absent.jsonl"),
        }),
        encoding="utf-8",
    )
    result = await ObservationFromLiveHookAssertion().evaluate(
        await _ctx(tmp_path), {"invocations_dir": "hook-invocations"}
    )
    assert result.status == "failed"
    assert "does not exist" in result.message


async def test_passes_on_a_live_harness_payload(tmp_path) -> None:
    records = _records(tmp_path)
    transcript = tmp_path / "session.jsonl"
    transcript.write_text("{}\n", encoding="utf-8")
    (records / "recorded.stdin.json").write_text(
        json.dumps({
            "session_id": "95d1105b",
            "hook_event_name": "PostToolUse",
            "transcript_path": str(transcript),
        }),
        encoding="utf-8",
    )
    result = await ObservationFromLiveHookAssertion().evaluate(
        await _ctx(tmp_path), {"invocations_dir": "hook-invocations"}
    )
    assert result.status == "passed"


def test_shim_records_only_the_recorded_response(tmp_path) -> None:
    """The shim must name the firing that recorded, not the last one."""
    records = tmp_path / "rec"
    stub = tmp_path / "real-logion"
    shim = tmp_path / "logion"
    shim.write_text(_CLI_SHIM.format(cli=stub, records=records))
    shim.chmod(0o755)

    def run(response: str, session: str) -> subprocess.CompletedProcess:
        stub.write_text(f"#!/bin/sh\ncat > /dev/null\necho '{response}'\n")
        stub.chmod(0o755)
        return subprocess.run(
            [str(shim), "usage", "observe", "--harness", "claude-code"],
            input=json.dumps({"session_id": session}),
            capture_output=True,
            text=True,
            env={"PATH": f"{tmp_path}:/usr/bin:/bin", "HOME": str(tmp_path)},
            check=False,
        )

    assert run('{"disposition": "recorded"}', "live").returncode == 0
    # A later `ignored` firing must not overwrite the recorded payload.
    assert run('{"disposition": "ignored"}', "later").returncode == 0

    recorded = json.loads((records / "recorded.stdin.json").read_text())
    assert recorded["session_id"] == "live"
    assert json.loads((records / "recorded.stdout.json").read_text()) == {
        "disposition": "recorded"
    }


def test_shim_passes_the_cli_exit_status_through(tmp_path) -> None:
    records = tmp_path / "rec"
    stub = tmp_path / "real-logion"
    stub.write_text("#!/bin/sh\ncat > /dev/null\nexit 3\n")
    stub.chmod(0o755)
    shim = tmp_path / "logion"
    shim.write_text(_CLI_SHIM.format(cli=stub, records=records))
    shim.chmod(0o755)
    result = subprocess.run(
        [str(shim), "usage", "observe", "--stdin"],
        input="{}",
        capture_output=True,
        text=True,
        env={"PATH": f"{tmp_path}:/usr/bin:/bin", "HOME": str(tmp_path)},
        check=False,
    )
    assert result.returncode == 3


def test_shim_is_valid_posix_shell(tmp_path) -> None:
    shim = tmp_path / "logion"
    shim.write_text(_CLI_SHIM.format(cli="/usr/bin/true", records="/records"))
    check = subprocess.run(
        ["sh", "-n", str(shim)], capture_output=True, text=True, check=False
    )
    assert check.returncode == 0, check.stderr


def test_scenario_never_hardcodes_a_harness_in_its_goals() -> None:
    """A hardcoded harness is why the gate could only ever replay.

    ``--agent-driver`` swaps the driver for every agent, so a goal naming
    one harness installs a hook the running harness will never fire.
    """
    scenario = Path(
        "packages/agent-proving-ground/agent_proving_ground/scenarios"
        "/builtin/native_use_observation_and_feedback.yaml"
    ).read_text(encoding="utf-8")
    goals = re.findall(
        r"    goal: \|\n(.*?)(?=\n    assertions:|\n  - id:)", scenario, re.S
    )
    assert goals
    for goal in goals:
        for harness in ("codex", "claude-code", "opencode", "hermes"):
            assert harness not in goal, f"{harness} hardcoded in a goal"


def test_role_tree_path_prefers_the_installed_cli(tmp_path) -> None:
    """The rig installs the CLI twice; both belong ahead of the host PATH."""
    from agent_proving_ground.api_adapters.local_devrig import _role_tree_path

    (tmp_path / "pipx-bin").mkdir()
    (tmp_path / "npm-prefix" / "bin").mkdir(parents=True)
    result = _role_tree_path(tmp_path).split(":")
    assert result[0] == str(tmp_path / "pipx-bin")
    assert result[1] == str(tmp_path / "npm-prefix" / "bin")


def test_role_tree_path_skips_directories_that_do_not_exist(tmp_path) -> None:
    from agent_proving_ground.api_adapters.local_devrig import _role_tree_path

    (tmp_path / "pipx-bin").mkdir()
    result = _role_tree_path(tmp_path).split(":")
    assert result[0] == str(tmp_path / "pipx-bin")
    assert str(tmp_path / "npm-prefix" / "bin") not in result


def test_stale_cli_is_named_rather_than_looking_like_a_dead_hook(
    tmp_path,
) -> None:
    """A 0.1.x wheel has no `usage` group; say so instead of failing mute."""
    from agent_proving_ground.runner import _cli_cannot_observe

    stale = tmp_path / "logion"
    stale.write_text(
        "#!/bin/sh\necho \"invalid choice: 'usage'\" >&2\nexit 2\n"
    )
    stale.chmod(0o755)
    reason = _cli_cannot_observe(str(stale))
    assert reason is not None
    assert "usage observe" in reason
    assert "dev-rebuild-cli" in reason


def test_current_cli_passes_the_preflight(tmp_path) -> None:
    from agent_proving_ground.runner import _cli_cannot_observe

    ok = tmp_path / "logion"
    ok.write_text("#!/bin/sh\nexit 0\n")
    ok.chmod(0o755)
    assert _cli_cannot_observe(str(ok)) is None


def test_preflight_is_silent_when_there_is_no_cli() -> None:
    from agent_proving_ground.runner import _cli_cannot_observe

    assert _cli_cannot_observe(None) is None


SCENARIO_PATH = Path(
    "packages/agent-proving-ground/agent_proving_ground/scenarios"
    "/builtin/native_use_observation_and_feedback.yaml"
)


def _runner_scenario_var_names() -> set[tuple[bool, str]]:
    """Every binding the runner writes, read off the runner itself.

    Listing them by hand here would be a second copy of the runner's
    vocabulary, and a copy is exactly what this test exists to catch
    drifting: a rename in the runner would sail past a mirror that was
    updated in the same commit as the scenario.
    """
    import re as _re

    source = Path(
        "packages/agent-proving-ground/agent_proving_ground/runner.py"
    ).read_text(encoding="utf-8")
    names = {
        (bool(prefix), name)
        for prefix, name in _re.findall(
            r'scenario_vars\[(f?)"([^"]+)"\]\s*=', source
        )
    }
    assert names, "no scenario_vars assignments found in the runner"
    return names


def test_every_scenario_parameter_has_a_binding() -> None:
    """Catch an orphaned ``${...}`` before a run spends an agent on it.

    The runner raises ``InconclusiveRun`` on an unresolved parameter, which
    is the right behaviour and a slow way to find out. Renaming a binding
    without renaming its uses is the cheap mistake this catches.
    """
    import yaml

    from agent_proving_ground.runner import _PARAMETER_RE

    scenario = yaml.safe_load(SCENARIO_PATH.read_text(encoding="utf-8"))
    provided: set[str] = set()
    for is_fstring, name in _runner_scenario_var_names():
        if not is_fstring:
            provided.add(name)
            continue
        for agent in scenario["agents"]:
            prefix = (
                "AGENT_" + re.sub(r"[^A-Za-z0-9]", "_", agent["id"]).upper()
            )
            provided.add(name.replace("{prefix}", prefix))
    for phase in scenario["phases"]:
        provided.update(phase.get("local_hook_capture_json") or {})

    used: set[str] = set()
    for phase in scenario["phases"]:
        for value in (phase.get("goal"), phase.get("success_hint")):
            used.update(_PARAMETER_RE.findall(value or ""))
        used.update(
            _PARAMETER_RE.findall(json.dumps(phase.get("local_hook_args", [])))
        )
        used.update(
            _PARAMETER_RE.findall(json.dumps(phase.get("assertions", [])))
        )
    used.update(
        _PARAMETER_RE.findall(json.dumps(scenario.get("final_assertions", [])))
    )

    assert not (used - provided), (
        f"unbound parameters: {sorted(used - provided)}"
    )
