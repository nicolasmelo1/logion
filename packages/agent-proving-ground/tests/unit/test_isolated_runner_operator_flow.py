from __future__ import annotations

from pathlib import Path

from agent_proving_ground.scenarios.loader import load_scenario

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = (
    REPO_ROOT / "packages/agent-proving-ground/scripts/run_runner_evidence.py"
)


def test_isolated_runner_uses_prepare_operator_collect_capture_order() -> None:
    scenario = load_scenario("builtin:isolated_runner_node")
    phases = {phase.id: phase for phase in scenario.phases}
    phase_ids = [phase.id for phase in scenario.phases]
    assert (
        phase_ids.index("prepare_runner_operator")
        < phase_ids.index("node_operator_runner_flow")
        < phase_ids.index("collect_runner_evidence")
        < phase_ids.index("capture_runner_evidence")
    )
    assert phases["prepare_runner_operator"].local_hook
    assert phases["prepare_runner_operator"].goal == ""
    assert phases["node_operator_runner_flow"].goal
    assert phases["node_operator_runner_flow"].local_hook is None
    assert phases["capture_runner_evidence"].local_hook is None


def test_runner_evidence_modes_keep_prepare_out_of_product_flow() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert 'sys.argv[1] not in {"prepare", "operator"}' in source
    prepare = source[
        source.index("def _prepare") : source.index("def _operator")
    ]
    operator = source[source.index("def _operator") : source.index("def main")]
    assert "_enroll_and_seed(" not in prepare
    assert "_runner_pass(" not in prepare
    assert "_plant_canaries(" in prepare
    assert "_enroll_and_seed(" in operator
    assert "_runner_pass(" in operator
    assert "raw-outputs" in operator
    assert "run-summary.json" in operator


def test_runner_launcher_is_the_versioned_fixture_with_substituted_paths(
    tmp_path: Path,  # noqa: ARG001 -- pytest signature convention
) -> None:
    fixture = (
        REPO_ROOT
        / "packages/agent-proving-ground/scripts/runner_flow_launcher.sh"
    ).read_text(encoding="utf-8")
    assert "@@OPERATOR_PYTHON@@" in fixture
    assert "@@EVIDENCE_SCRIPT@@" in fixture
    assert "operator" in fixture
    assert "LOGION_PROVING_GROUND_ROLE_KEYS_FILE" not in fixture
